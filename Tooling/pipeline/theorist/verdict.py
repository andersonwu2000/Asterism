"""The theory review's verdict: its rubric, its parser, and what
happens to one the parser refuses.

Ported from `Tooling/experiments/theory_wake.py` (arm 3/5F, 2026-09-04),
which is where every rule below was paid for. It is deliberately NOT
`pipeline.adversary.parse_verdict`: that parser's contract is the batch
judge's criteria "1".."5" plus criterion 2's naming rule, held level
with `prompts/adversary/adversary.md` by its own test. Bending it to
admit a four-criterion review would move the batch judge's contract to
serve another rubric — and the batch judge is the one gate on the
argument layer that has no second opinion.

THE RULE THAT COST TWO WHOLE RUNS. A criterion is clear iff EVERY
bullet in it is a clear. "clear takes exactly one entry" is the batch
judge's rule, and it is right there: its criteria rule on a single
proposal. A theory document carries several theorems and several leads,
so a criterion that asks about them is answered one bullet per item —
and the inherited rule ended BOTH arm5F runs as `judge_no_verdict` on
verdicts that were entirely clear (runs/arm5F_r1 criterion 4,
runs/arm5F_r2 criterion 2). Multi-clear is legal here; MIXED clear and
fired in one criterion is not, because a criterion is one ruling.

What is never tolerated is a BARE `clear` — in any rendering. The
prompt says "No criterion takes a bare `clear`" and this is the
enforcement half, per BULLET so a bare one cannot hide behind a
reasoned neighbour.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

#: The document the author hands in and the ruling the reviewer hands
#: back. Bare names in both prompts, resolved by each spawn's own write
#: fence into its own directory.
REPORT_BASENAME = "report.md"
VERDICT_BASENAME = "verdict.json"

#: `prompts/theorist/review.md`'s rubric: Worth / Rigour / Load-bearing
#: work / Leads.
CRITERIA_KEYS: "tuple[str, ...]" = ("1", "2", "3", "4")

#: The rubric DECLARATION dropped beside the reviewer's verdict, so
#: `validate_json` checks the hand-in against the keys this rubric
#: actually has. Without it the generic branch assumes the batch
#: judge's 1-5 and tells a complete four-criterion verdict that it is
#: "missing criterion 5" — a framework fault worded as the reviewer's
#: mistake, on a criterion the rubric has no way to add.
RUBRIC_BASENAME = "_verdict_rubric.json"

#: Reviewer re-spawns on a missing or malformed verdict, per round.
#: Same number and same reason as `adversary.VERDICT_TRIES`: a reviewer
#: that produced no usable ruling twice is a pipeline-level failure, and
#: one malformed file must not cost the author's document.
VERDICT_TRIES = 2


def write_rubric(target_dir: Path) -> Path:
    """Declare this rubric in the review dir. `multi_clear` rides with
    the key set because the two are one contract: a rubric whose
    criteria are answered one bullet per item is exactly the rubric
    whose clears come in plural."""
    path = Path(target_dir) / RUBRIC_BASENAME
    path.write_text(
        json.dumps({"criteria_keys": list(CRITERIA_KEYS),
                    "multi_clear": True}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# what a bullet may look like
# ---------------------------------------------------------------------

#: A reviewer that renders a bullet as an OBJECT names the ruling and
#: the prose with one of these. Not a guess: `validate_json` used to
#: mis-route a short verdict into the AUDITOR's schema check and told
#: arm3h_r2's reviewer, twice, to re-render its bullets as
#: `{"goal_id", "verdict", "reason"}` — and both runs died on the
#: RENDERING of a ruling that was otherwise exactly right. The contract
#: is one bullet per objection; the bullet's SHAPE is not the contract,
#: the same reason the batch parser still takes a legacy bare string.
_BULLET_HEAD_KEYS = ("verdict", "ruling", "status", "result")
_BULLET_TEXT_KEYS = ("reason", "text", "objection", "bullet", "detail",
                     "note", "comment", "message")


def _as_bullet(entry) -> "str | None":
    """One criterion entry as the `"<head>: <prose>"` line the rest of
    the parser reads, or None if it is no rendering of a bullet at all.

    An object whose ruling is `clear` and whose prose is empty comes
    back as the bare word — so the bare-clear refusal fires on this
    rendering exactly as it does on the string one."""
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None

    def _pick(keys):
        for k in keys:
            v = entry.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    head, body = _pick(_BULLET_HEAD_KEYS), _pick(_BULLET_TEXT_KEYS)
    if not head:
        # No ruling key: the prose may already carry it ("fired: …").
        # If it does not, the head check below refuses it, which is right.
        return body or None
    return f"{head}: {body}" if body else head


def _bullets(val) -> "list[str] | None":
    """A criterion's value as a flat list of bullet lines: a bare string
    (one bullet), a list of strings, a list of objects, or a list nested
    one level deeper."""
    if isinstance(val, str):
        return [val]
    if not isinstance(val, list) or not val:
        return None
    out: "list[str]" = []
    for entry in val:
        if isinstance(entry, list):
            inner = _bullets(entry)
            if inner is None:
                return None
            out += inner
            continue
        line = _as_bullet(entry)
        if line is None:
            return None
        out.append(line)
    return out or None


def describe_verdict_shape(text: str) -> str:
    """What the reviewer actually wrote, per criterion, as one log line.

    A refused verdict is the evidence for why it was refused, and
    arm3h_r2 had to be recovered from the provider rollout because the
    log carried only the refusal. Types and key names, never values —
    the raw file kept beside it carries those."""
    try:
        v = json.loads(text, strict=False)
    except ValueError as e:
        return f"not JSON ({e})"
    if not isinstance(v, dict):
        return f"top level is {type(v).__name__}, not an object"

    def shape(x) -> str:
        if isinstance(x, dict):
            return "dict{" + ",".join(sorted(map(str, x))) + "}"
        if isinstance(x, list):
            inner = sorted({shape(i) for i in x})
            return f"list[{'|'.join(inner) or 'empty'}]({len(x)})"
        return type(x).__name__

    criteria = v.get("criteria")
    if not isinstance(criteria, dict):
        return (f"top-level keys {sorted(map(str, v))}; "
                f"`criteria` is {shape(criteria)}")
    return ("criteria " + ", ".join(
        f'"{k}"={shape(criteria[k])}' for k in sorted(map(str, criteria)))
        + f"; reservations={shape(v.get('reservations'))}")


def keep_rejected_verdict(vpath: Path, *, round_no: int) -> Path:
    """Move a refused `verdict.json` aside instead of deleting it.

    It leaves the contract path — the next try must not be read as a
    verdict this reviewer did not write — and lands as
    `verdict_r<n>_raw.json` beside it. A second refusal in the same
    round takes `…_raw2.json`, so no refused file is ever overwritten by
    a later one."""
    raw = vpath.read_bytes()
    dst = vpath.with_name(f"verdict_r{round_no}_raw.json")
    for i in range(1, 100):
        dst = vpath.with_name(
            f"verdict_r{round_no}_raw{'' if i == 1 else i}.json")
        if not dst.exists():
            break
    dst.write_bytes(raw)
    vpath.unlink(missing_ok=True)
    return dst


def parse_theory_verdict(text: str, criteria_keys=CRITERIA_KEYS
                         ) -> "tuple[dict | None, str]":
    """Validate the reviewer's `verdict.json` and derive the ruling.

    A list per criterion, each bullet `"clear: <reason>"` or
    `"fired: <objection>"`; any fired makes the verdict a rebut.
    `strict=False` for the same reason the batch parser uses it: a
    literal newline inside a string value is not structural damage and
    has killed a wake over it.

    Returns `({"verdict", "criticisms", "reservations", "criteria"},
    "")`, or `(None, <what to tell the reviewer>)`. The criticisms are
    the objection text VERBATIM with only a criterion label added — they
    go back to the author as they were written."""
    try:
        v = json.loads(text, strict=False)
    except ValueError as e:
        return None, f"verdict.json is not valid JSON: {e}"
    if not isinstance(v, dict):
        return None, "verdict.json must be a JSON object"
    criteria = v.get("criteria")
    if not isinstance(criteria, dict):
        return None, ("verdict.json needs a `criteria` object "
                      "adjudicating every criterion "
                      + ", ".join(f'"{k}"' for k in criteria_keys))
    missing = [k for k in criteria_keys if k not in criteria]
    if missing:
        return None, (f"verdict.json `criteria` missing criterion "
                      f"{', '.join(missing)} — every criterion gets a "
                      f"line, `\"clear: <reason>\"` or "
                      f"`\"fired: <objection>\"`")
    fired: "list[str]" = []
    for k in criteria_keys:
        vals = _bullets(criteria[k])
        if vals is None:
            return None, (f"criterion {k} must be a list of strings "
                          f"(one bullet per objection) or a single "
                          f"string")
        heads = [("clear" if re.match(r"clear\b", x.strip(), re.IGNORECASE)
                  else "fired" if re.match(r"fired\b", x.strip(),
                                           re.IGNORECASE)
                  else "?") for x in vals]
        if "?" in heads:
            return None, (f"criterion {k}: every bullet must start "
                          f"\"clear\" or \"fired: <objection>\"")
        if "clear" in heads and "fired" in heads:
            return None, (f"criterion {k} mixes \"clear\" and \"fired\" "
                          f"bullets — a criterion is one or the other")
        if heads[0] == "clear":
            for x in vals:
                if not x.strip()[len("clear"):].strip(" -—–:"):
                    return None, (
                        f"criterion {k} never takes a bare \"clear\" — "
                        f"say why it holds for THIS document: "
                        f"`\"clear: <one concrete reason>\"`")
            continue
        for x in vals:
            xs = x.strip()
            reason = (xs.split(":", 1)[1].strip() if ":" in xs
                      else xs[len("fired"):].strip(" -—–:"))
            if not reason:
                return None, (f"criterion {k} is fired but carries no "
                              f"objection — `\"fired: <objection>\"`")
            fired.append(f"[criterion {k}] {reason}")
    reservations = v.get("reservations", [])
    if not (isinstance(reservations, list)
            and all(isinstance(x, str) for x in reservations)):
        return None, "verdict.json `reservations` must be a list of strings"
    return {
        "verdict": "rebut" if fired else "pass",
        "criticisms": fired,
        "reservations": reservations,
        "criteria": {k: criteria[k] for k in criteria_keys},
    }, ""


def verdict_lines(verdict: "dict | None") -> "list[str]":
    """One line per criterion, for the landed document's header.

    The reviewer's own sentence is the only durable record of what was
    checked — the verdict file lives in an attempts dir that is deleted
    at pipeline end. EVERY bullet, on both roads: a refused document
    lands too (owner ruling 2026-09-06), and its header's whole job is
    to carry the ruling that refused it. Rendering only the clears
    would land a rejection reading as a pass on the criteria that
    fired."""
    out: "list[str]" = []
    for k in CRITERIA_KEYS:
        vals = _bullets((verdict or {}).get("criteria", {}).get(k)) or []
        text = " / ".join(" ".join(str(v).split()) for v in vals)
        out.append(f"criterion {k}: {text}" if text
                   else f"criterion {k}: (no line recorded)")
    return out


#: Which criterion of `prompts/theorist/review.md`'s rubric is Rigour.
#: The one that decides whether the document's theorems are RESULTS: the
#: reviewer clears it by re-deriving them, so a document it cleared may
#: be cited whatever the other three said, and one it fired on carries
#: attempts however well the rest reads (owner ruling 2026-09-06).
RIGOUR_CRITERION = "2"

#: The flag a rigour-defective document carries, verbatim, everywhere a
#: reader could otherwise cite it: the landed header, the Notes roster
#: and the outcome the Strategist reads. ONE spelling, because the three
#: surfaces are read by three different seats and a paraphrase is a
#: fourth rule they would each have to learn.
RIGOUR_DEFECTIVE = f"rigour: defective — see criterion {RIGOUR_CRITERION}"


def fired_criteria(verdict: "dict | None") -> "list[str]":
    """The criterion keys whose ruling FIRED, in rubric order.

    `parse_theory_verdict` already refuses a criterion that mixes clear
    and fired bullets, so one fired bullet is the whole criterion's
    ruling."""
    out: "list[str]" = []
    for k in CRITERIA_KEYS:
        vals = _bullets((verdict or {}).get("criteria", {}).get(k)) or []
        if any(re.match(r"fired\b", str(v).strip(), re.IGNORECASE)
               for v in vals):
            out.append(k)
    return out


def rigour_is_defective(verdict: "dict | None") -> bool:
    """Whether this ruling leaves the document's theorems unestablished."""
    return RIGOUR_CRITERION in fired_criteria(verdict)
