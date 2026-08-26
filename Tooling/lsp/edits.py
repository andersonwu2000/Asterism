"""Resolving anchored edits against a file's actual content.

WHY THE ADDRESS IS THE CONTENT. `apply_edit` took line numbers for a
year, and 42 of the 597 agent reports filed in the week to 2026-08-10
were one shape: the tool executed a splice on a coordinate the agent
remembered and the file no longer agreed with. It dropped a trailing
`end`, duplicated a proof body, targeted a region that had shifted under
an earlier edit — silently, every time, because a line number carries no
redundancy. Any range inside the file is "valid"; there is nothing for
the tool to check it against.

Four rounds of fixes each added a better DESCRIPTION of the outcome —
an echo of the edited region, a scope-balance warning, an end-of-file
sentinel, a clearer out-of-range message — and none of them removed the
trust in the address, so the class regenerated. Descriptions also arrive
one round-trip AFTER the damage, when the agent understands the file
less than it did before.

An anchor is redundant by construction: the text either is there,
exactly once, or it is not. A stale mental model becomes a refusal
before anything is elaborated, instead of a corruption discovered later.

Everything here is pure — no session, no LSP, no I/O — so the resolution
rules are testable without a Lean toolchain.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: How much of the file to quote back when an anchor does not match. Big
#: enough to re-anchor from, small enough not to flood the next turn.
CLOSEST_CONTEXT_CHARS = 400
#: Cap on match locations listed for an ambiguous anchor.
MAX_AMBIGUOUS_SHOWN = 6

#: What continues a Lean name. NOT `\w`: the incident this exists for is
#: an anchor `end Problems` binding inside
#: `end Problems.Combinatorics.union_closed`, where the character on the
#: boundary is a DOT. An ASCII word boundary lets the dot through and
#: the bug survives its own fix. Lean identifiers also carry `_`, `'`,
#: `!`, `?`, subscripts and Greek letters, so the test is "does the
#: character continue a name", not "is it alphanumeric".
_NAME_CHAR = re.compile(r"[^\W]|['ʼ_.!?₀-₉ₐ-ₜͰ-Ͽᴀ-ᵿ]",
                        re.UNICODE)


def _continues_a_name(ch: str) -> bool:
    return bool(ch) and bool(_NAME_CHAR.match(ch))


def _splits_a_name(content: str, at: int, needle: str) -> "str | None":
    """The full name an anchor edge lands inside, or None.

    A match is only the text the agent named if neither end sits in the
    middle of an identifier. When one does, the tool used to edit a span
    the agent never described AND REPORT SUCCESS — `end Problems`
    resolved against `end Problems.Combinatorics.union_closed`, the span
    stopped 13 characters early, and `.Combinatorics.union_closed` was
    left dangling in the file with a clean verdict on top of it.

    Returns the offending whole name so the refusal can quote it: a
    refusal that says only "no" costs the same round trip as a wrong
    edit and teaches less."""
    lo, hi = at, at + len(needle)
    left_bad = (_continues_a_name(content[lo - 1:lo])
                and _continues_a_name(needle[:1]))
    right_bad = (_continues_a_name(content[hi:hi + 1])
                 and _continues_a_name(needle[-1:]))
    if not (left_bad or right_bad):
        return None
    s = lo
    while s > 0 and _continues_a_name(content[s - 1]):
        s -= 1
    e = hi
    while e < len(content) and _continues_a_name(content[e]):
        e += 1
    return content[s:e]


@dataclass(frozen=True)
class Span:
    """A resolved character range plus what replaces it."""
    start: int
    end: int
    new_text: str
    kind: str
    anchor: str

    @property
    def is_insert(self) -> bool:
        return self.start == self.end


class EditError(Exception):
    """A refusal, carrying the report the agent needs to fix it."""

    def __init__(self, index: int, message: str, **extra) -> None:
        super().__init__(message)
        self.index = index
        self.message = message
        self.extra = extra

    def as_dict(self) -> dict:
        # `edit_index`, not `edit`: the gateway response already uses
        # `edit` for its outcome line, and the `**`-merge silently
        # overwrote that string with this integer — a refusal came back
        # reading as a successful edit numbered 2. Caught by its own
        # test on the first run (2026-08-10).
        return {"edit_index": self.index, "error": self.message,
                **self.extra}


def line_of(content: str, offset: int) -> int:
    """1-indexed line containing `offset`. Line numbers are OUTPUT only —
    ground truth the tool measured, never something the caller has to
    have remembered."""
    return content.count("\n", 0, offset) + 1


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _closest_region(content: str, needle: str) -> "str | None":
    """A whitespace-insensitive match, quoted VERBATIM.

    Never applied automatically: this is Lean, where indentation carries
    meaning, so a fuzzy match is a guess about the proof. Returning the
    exact text instead makes the corrected retry mechanical — round two
    always succeeds."""
    target = _norm(needle)
    if not target:
        return None
    # Collapse runs of whitespace, remembering where each surviving
    # character came from, so a hit maps back to VERBATIM source. A
    # line-window comparison (the first attempt) only matched when the
    # anchor happened to be whole lines; the common slip is an anchor
    # that is a fragment of one.
    flat: "list[str]" = []
    origin: "list[int]" = []
    prev_ws = True
    for i, ch in enumerate(content):
        if ch.isspace():
            if prev_ws:
                continue
            flat.append(" ")
            origin.append(i)
            prev_ws = True
        else:
            flat.append(ch)
            origin.append(i)
            prev_ws = False
    at = "".join(flat).find(target)
    if at == -1:
        return None
    lo = origin[at]
    # Back to the start of the line: the error text tells the agent
    # "indentation is part of the anchor", so the VERBATIM quote it
    # offers must CARRY the leading indentation — it used to start at
    # the first non-whitespace character, and copying it verbatim
    # failed exactly as instructed (~35 reports, 2026-08-26).
    lo = content.rfind("\n", 0, lo) + 1
    hi = origin[min(at + len(target), len(origin)) - 1] + 1
    return content[lo:hi][:CLOSEST_CONTEXT_CHARS]


def _find_unique(content: str, needle: str, index: int, label: str,
                 *, start: int = 0, scope: str = "the file") -> int:
    """The one offset `needle` names, or an error naming the rivals.

    `start` restricts the search to `content[start:]` while keeping the
    offsets (and therefore the reported line numbers) absolute — that is
    how `replace_between`'s closing anchor stays REGIONAL: it must be
    unique after the opening anchor, never in the whole file.
    """
    if not needle:
        raise EditError(index, f"{label} is empty — give the text to match")
    hits = []
    at = content.find(needle, start)
    while at != -1:
        hits.append(at)
        if len(hits) > MAX_AMBIGUOUS_SHOWN:
            break
        at = content.find(needle, at + 1)
    if len(hits) == 1:
        whole = _splits_a_name(content, hits[0], needle)
        if whole is not None:
            raise EditError(
                index,
                f"{label} matches inside `{whole}` — the edit would take a "
                f"span you did not name. Anchor on the whole name.")
    if not hits:
        closest = _closest_region(content[start:], needle)
        raise EditError(
            index,
            f"{label} does not appear in {scope}"
            + (". A region differs only in whitespace — resubmit with this "
               "text VERBATIM (indentation is part of the anchor):"
               if closest else
               ". Read the file first — `inspect` can read your working "
               'file live (`[{"read": "<your file>", "raw": true}]`; '
               "apply_edit writes through to disk) — then anchor on "
               "text you have actually seen."),
            **({"closest_region": closest} if closest else {}))
    if len(hits) > 1:
        raise EditError(
            index,
            f"{label} appears {len(hits)}{'+' if len(hits) > MAX_AMBIGUOUS_SHOWN else ''} "
            f"times in {scope} — extend it until it is unique (include the "
            f"line above or below).",
            match_lines=[line_of(content, h)
                         for h in hits[:MAX_AMBIGUOUS_SHOWN]])
    return hits[0]


def resolve(content: str, edits: "list") -> "list[Span]":
    """Resolve every edit against ONE snapshot, or raise.

    All anchors resolve against the same pre-state, which is what makes
    the batch order-independent and the retry safe: a failed batch
    changes nothing, so the anchors that did resolve are still valid on
    resubmission. (They would not be under line ranges — the reason
    partial application is refused below.)"""
    if not isinstance(edits, list) or not edits:
        raise EditError(0, "give a list of edits, e.g. "
                           '[{"replace": "<old text>", "with": "<new>"}]')
    spans: "list[Span]" = []
    for i, e in enumerate(edits, 1):
        if not isinstance(e, dict):
            raise EditError(i, f"not an edit object: {e!r}")
        if "replace" in e:
            old = str(e.get("replace") or "")
            at = _find_unique(content, old, i, "`replace` text")
            spans.append(Span(at, at + len(old), str(e.get("with") or ""),
                              "replace", old))
        elif "replace_between" in e:
            pair = e.get("replace_between")
            if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
                raise EditError(i, "`replace_between` takes exactly two "
                                   "anchors: [<from>, <to>]")
            lo_text, hi_text = str(pair[0] or ""), str(pair[1] or "")
            lo = _find_unique(content, lo_text, i, "the opening anchor")
            # The closing anchor is REGIONAL, not global: a proof block
            # routinely ends on a line that recurs elsewhere in the file
            # (`omega`, `rfl`), and demanding global uniqueness would
            # push the agent back to quoting the whole span — the
            # transcription failure this form exists to avoid. So it must
            # be unique only in what follows the opening anchor.
            #
            # It used to take the FIRST match after `lo` and say nothing,
            # which made it the one address in this API that could bind
            # silently to the wrong place. When the intended occurrence
            # failed to match verbatim (one space of indentation is
            # enough), the anchor bound to a LATER one and the span
            # swallowed everything in between — reported 2026-08-11 as
            # "deleted the e1/e2 have-blocks that followed, leaving a
            # dangling `intro h`". Ambiguity is now refused the same way
            # the opening anchor refuses it, so a wrong address costs a
            # rejection instead of a corrupted file: `resolve` is
            # all-or-nothing, and a refused batch changes nothing.
            hi = _find_unique(content, hi_text, i, "the closing anchor",
                              start=lo + len(lo_text),
                              scope="the text after the opening anchor")
            spans.append(Span(lo, hi + len(hi_text),
                              str(e.get("with") or ""),
                              "replace_between", lo_text))
        elif "insert_after" in e:
            anchor = str(e.get("insert_after") or "")
            at = _find_unique(content, anchor, i, "`insert_after` anchor")
            end = at + len(anchor)
            text = str(e.get("text") or "")
            # LINE-BOUNDARY GUARD. A verbatim splice after an anchor
            # that ends its line glues two tokens across the boundary:
            # `insert_after: "…false in", text: "-- note"` produced
            # `in-- note`, and an import inserted after `import Mathlib`
            # produced `import Mathlibimport …` — both real repairs paid
            # by agents (2026-08-16). When the anchor ends at a line
            # boundary (or at EOF) and the text does not bring its own
            # newline, the new content starts on its own line. A
            # MID-line anchor keeps the verbatim splice — that is the
            # inline use, and it is the caller's own spacing.
            if (text and not text.startswith(("\n", "\r"))
                    and not anchor.endswith("\n")
                    and (end >= len(content) or content[end] == "\n")):
                text = "\n" + text
            spans.append(Span(end, end, text, "insert_after", anchor))
        else:
            raise EditError(
                i, f"no known edit key in {sorted(e)}. Use `replace` (+ "
                   f"`with`), `replace_between` (+ `with`), or "
                   f"`insert_after` (+ `text`).")

    ordered = sorted(range(len(spans)), key=lambda k: spans[k].start)
    for a, b in zip(ordered, ordered[1:]):
        sa, sb = spans[a], spans[b]
        if sb.start < sa.end:
            raise EditError(
                b + 1,
                f"this edit's region overlaps edit {a + 1}'s "
                f"(lines {line_of(content, sa.start)}–"
                f"{line_of(content, sa.end)} and "
                f"{line_of(content, sb.start)}–{line_of(content, sb.end)}). "
                f"Split them, or merge into one `replace`.")
    return spans


def apply_spans(content: str, spans: "list[Span]") -> str:
    """Splice back-to-front so earlier offsets stay valid."""
    out = content
    for s in sorted(spans, key=lambda x: x.start, reverse=True):
        out = out[:s.start] + s.new_text + out[s.end:]
    return out
