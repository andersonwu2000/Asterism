"""What a diagnostic looks like when it reaches the AGENT.

Every other module in this package answers "what did Lean say"; this one
answers "how much of it fits in a worker's turn". A leaf: it imports
nothing from the package, so `leantext` can re-export `_collapse_repeats`
from here without closing a cycle.

Measured 2026-09-07 over 574 real `apply_edit` responses from one day of
`union_closed` spawns: 9.9 KB average, 62.7 KB worst, and one `errors_at`
came back to the worker as `Warning: truncated output (original token
count: 18055)`. The bytes, by field: diagnostics 2.44 MB,
post_edit_region 1.22 MB, goal_at_edit_start 914 KB, goal_at_edit_end
790 KB, replaced_text 153 KB. Four agents filed the same complaint
independently that morning (10:00, 10:21, 10:52, 11:16) — "large
post-edit goal dumps were repeatedly truncated and obscured the first
real failure". Truncation does not drop the least useful part; it drops
the TAIL, and the tail is where the second error and the closing brace
live.

The fold that already existed keyed on the byte-identical message, so
1739 `unusedSimpArgs` warnings in that same day — one per unused simp
argument, each naming a different argument — all survived it. Category
is the right key: 2106 of 2299 non-error diagnostics carry
`set_option linter.<name> false` in their own text, which is the
linter's own name for what it is.

Nothing here decides WHAT is wrong; it decides what the agent reads
first. `verbose=true` on either tool returns the untrimmed payload, so
no information is destroyed — only deferred.
"""
from __future__ import annotations

import re


#: Lean's own escape hatch, printed at the foot of every linter
#: diagnostic ("Note: This linter can be disabled with `set_option
#: linter.unusedSimpArgs false`"). It is the linter naming ITSELF, so it
#: beats any first-line heuristic — the first lines of the same
#: category differ ("This simp argument is unused:" vs the argument).
_LINTER_OPT_RE = re.compile(r"set_option\s+(linter\.[A-Za-z0-9_.]+)\s+false")

#: A hypothesis in a Lean goal state: `h : T`, `J Z U V : Finset α`,
#: `inst✝ : DecidableEq α` — a binder list at column 0 followed by ` : `.
#: Deliberately NOT "any line before the ⊢": `Note:`/`Hint:` lines and a
#: tactic's quoted pattern are prose the agent needs, and they carry no
#: space before their colon.
_HYP_RE = re.compile(r"^[^\s].*?\s:\s")

#: Errors shown in full-position order before the tail line takes over.
#: Eight is where the fixture stops being readable, and an agent works
#: the FIRST one anyway — the rest usually cascade from it.
MAX_ERRORS = 8

#: Hard ceiling per error message, applied after the hypothesis trim.
#: The trim alone does not bound a multi-`case` `unsolved goals` (the
#: worst real one was 13.6 KB across six cases, each with its own goal),
#: and an unbounded first error is exactly the payload that got
#: truncated. ~1K tokens: enough for the first case's full state.
ERR_MSG_MAX_CHARS = 4000

_VERBOSE_HINT = "errors_at(verbose=true)"

#: ONE note, not one per folded thing: two notes that both end in "ask
#: for verbose" are the duplication this module exists to remove. Only
#: the clauses that actually applied are assembled into it.
_NOTE_WARNINGS = ("warnings never block a proof and are folded to one line "
                  "per linter category")
_NOTE_HYPOTHESES = ("the first error keeps its whole goal state, the rest "
                    "count their binders as `hypotheses_hidden`")
_NOTE_TAIL = f"{_VERBOSE_HINT} returns every diagnostic in full"


def _diag_category(f: dict) -> str:
    """A stable key for "the same kind of complaint"."""
    msg = str(f.get("message", ""))
    named = _LINTER_OPT_RE.search(msg)
    if named:
        return named.group(1)
    head = msg.split("\n", 1)[0].strip()
    return head[:80] if head else "(no message)"


def _collapse_repeats(formatted: "list[dict]",
                      by_category: bool = True) -> "list[dict]":
    """Fold repeating diagnostics into one entry carrying `repeats` +
    `also_lines`. Nothing is hidden — the payload is the same
    information at a fraction of the reading cost (07-29 feedback:
    three identical `push_neg` deprecation warnings on every probe,
    competing with the real ok/error signal).

    Two keys, one pass. ERRORS fold only on the byte-identical message:
    two errors that merely share a linter-less first line are two
    different problems, and merging them would hide one. Everything
    else folds on `_diag_category`, because 1739 of one day's 2299
    warnings were `unusedSimpArgs` differing only in which argument
    they name — the identical-message fold left all 1739 in the payload
    (2026-09-07).

    A folded non-error gets its message REWRITTEN to the category line;
    the entry keeps `category` so a later reader does not have to
    re-derive it from the rewrite.

    `by_category=False` is the pre-09-07 fold EXACTLY — identical
    messages only, and no rewrite — because it is what `verbose` asks
    for: the escape hatch has to return the payload the trim was
    applied to, or it is not an escape hatch.
    """
    out: "list[dict]" = []
    seen: "dict[tuple[str, str], dict]" = {}
    for f in formatted:
        sev = str(f.get("severity"))
        key = ((sev, str(f.get("message")))
               if sev == "error" or not by_category
               else (sev, "\x00category\x00" + _diag_category(f)))
        first = seen.get(key)
        if first is None:
            seen[key] = f
            out.append(f)
            continue
        first["repeats"] = int(first.get("repeats", 1)) + 1
        first.setdefault("also_lines", []).append(f.get("line"))
    for f in out:
        if by_category and str(f.get("severity")) != "error" \
                and f.get("repeats"):
            f["category"] = _diag_category(f)
            f["message"] = (f"{f['category']} \u00d7{f['repeats']} (folded "
                            f"\u2014 {_VERBOSE_HINT} prints each)")
    return out


def _warning_line(f: dict) -> str:
    """One collapsed non-error, as a single line: what the linter is
    called, how many times it fired, and where. The lines are the part
    an agent acts on — a category with no position is unactionable."""
    cat = f.get("category") or _diag_category(f)
    lines = [f.get("line")] + list(f.get("also_lines") or [])
    lines = [n for n in lines if n is not None]
    shown = ", ".join(str(n) for n in lines[:6])
    if len(lines) > 6:
        shown += f" (+{len(lines) - 6} more)"
    sev = str(f.get("severity"))
    label = "" if sev == "warning" else f"[{sev}] "
    return f"{label}{cat} \u00d7{len(lines) or 1} \u2014 line(s) {shown}"


def _cap_message(message: str, limit: int = ERR_MSG_MAX_CHARS) -> str:
    if len(message) <= limit:
        return message
    return (message[:limit] + f"\n\u2026 [{len(message) - limit} more chars "
            f"\u2014 {_VERBOSE_HINT} for the full message]")


def _trim_error(message: str, keep_hypotheses: bool) -> "tuple[str, int]":
    """Drop the hypothesis dump from a goal-state error, keep the goal.

    Returns `(message, hypotheses_hidden)`. A message with no `\u22a2` is
    not a goal state (a type mismatch, a failed rewrite, a heartbeat
    timeout) and comes back untouched but capped — those run 300-500
    chars and every line of them is the diagnosis.

    In a goal state the `\u22a2` line IS the diagnosis; the forty binders
    above it are context the agent already has in the file. They are
    kept for the FIRST error because that is where it will work next,
    and COUNTED for the rest \u2014 as the entry's `hypotheses_hidden`, not
    as a marker line inside every message: eight copies of the same
    "hidden, ask for verbose" sentence is the noise this whole change
    is about. `_terse_report` says it once.
    """
    if "\u22a2" not in message:
        return _cap_message(message), 0

    out: "list[str]" = []
    pending: "list[str]" = []
    hidden = 0
    in_goal = False
    last_was_hyp = False

    def flush() -> int:
        nonlocal pending
        real = [p for p in pending if p.strip()]
        if not real:
            out.extend(pending)
            pending = []
            return 0
        if keep_hypotheses:
            out.extend(pending)
            pending = []
            return 0
        pending = []
        return len(real)

    for ln in message.split("\n"):
        if ln.startswith("\u22a2"):
            hidden += flush()
            out.append(ln)
            in_goal, last_was_hyp = True, False
            continue
        if in_goal and (not ln.strip() or ln[:1].isspace()):
            # A goal wraps onto indented continuation lines, and a blank
            # line separates one `case` from the next.
            out.append(ln)
            continue
        in_goal = False
        if _HYP_RE.match(ln):
            pending.append(ln)
            last_was_hyp = True
            continue
        if pending and last_was_hyp and ln[:1].isspace():
            pending.append(ln)  # a hypothesis wrapped onto a second line
            continue
        hidden += flush()
        out.append(ln)
        last_was_hyp = False
    hidden += flush()
    return _cap_message("\n".join(out)), hidden


def _terse_report(formatted: "list[dict]", converged: bool = True,
                  max_errors: int = MAX_ERRORS) -> dict:
    """The agent-facing view of a diagnostic list.

    Returns the payload keys that replace an uncapped `diagnostics`:
    errors only in source order, a tail line for the ones past the cap,
    and the non-errors as one line per category. `error_count` is None
    when the elaboration never converged — a count is the field every
    reader trusts, so an unfinished run must not own one (the fake-clean
    class, ~150 worker reports 2026-08-29).

    Call it AFTER `_collapse_repeats`, so `error_count` counts distinct
    errors (ten copies of one message are one thing to fix, and the
    entry still carries `repeats` + `also_lines`); the raw total stays
    in the caller's `diagnostic_count` / `count`.
    """
    errors = [f for f in formatted if str(f.get("severity")) == "error"]
    others = [f for f in formatted if str(f.get("severity")) != "error"]
    errors.sort(key=lambda f: (f.get("line") or 0, f.get("col") or 0))
    shown = []
    for i, f in enumerate(errors[:max_errors]):
        msg, hidden = _trim_error(str(f.get("message", "")),
                                  keep_hypotheses=(i == 0))
        entry = {**f, "message": msg}
        if hidden:
            entry["hypotheses_hidden"] = hidden
        shown.append(entry)
    report: dict = {"error_count": len(errors) if converged else None,
                    "diagnostics": shown}
    if len(errors) > max_errors:
        report["more_errors"] = (
            f"and {len(errors) - max_errors} more errors \u2014 "
            f"{_VERBOSE_HINT} for all")
    if others:
        others.sort(key=lambda f: (f.get("line") or 0, f.get("col") or 0))
        report["warnings"] = [_warning_line(f) for f in others]
    clauses = ([_NOTE_WARNINGS] if others else []) + (
        [_NOTE_HYPOTHESES] if any(e.get("hypotheses_hidden")
                                  for e in shown) else [])
    if clauses:
        report["terse_note"] = "; ".join(clauses) + f" \u2014 {_NOTE_TAIL}"
    return report


#: Region echo: how many numbered lines of ONE edited span ride back
#: before the middle is elided. The span is what the agent just wrote —
#: it needs the two ends to re-anchor, not a mirror of its own text (a
#: 60-line replacement echoed 64 lines, and post_edit_region was 1.22 MB
#: of the day's 6 MB).
ECHO_MAX_REGION_LINES = 14
_ECHO_END_LINES = 6


def _cap_region(span: "list[str]") -> "list[str]":
    """Head and tail of one edited region's echo, with the count of what
    sits between them."""
    if len(span) <= ECHO_MAX_REGION_LINES:
        return span
    elided = len(span) - 2 * _ECHO_END_LINES
    return (span[:_ECHO_END_LINES]
            + [f"\u2026 [{elided} more lines of the edited region \u2014 "
               f"apply_edit(verbose=true) echoes them] \u2026"]
            + span[-_ECHO_END_LINES:])
