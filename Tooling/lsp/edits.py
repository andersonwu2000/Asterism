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
    hi = origin[min(at + len(target), len(origin)) - 1] + 1
    return content[lo:hi][:CLOSEST_CONTEXT_CHARS]


def _find_unique(content: str, needle: str, index: int, label: str) -> int:
    if not needle:
        raise EditError(index, f"{label} is empty — give the text to match")
    hits = []
    at = content.find(needle)
    while at != -1:
        hits.append(at)
        if len(hits) > MAX_AMBIGUOUS_SHOWN:
            break
        at = content.find(needle, at + 1)
    if not hits:
        closest = _closest_region(content, needle)
        raise EditError(
            index,
            f"{label} does not appear in the file"
            + (". A region differs only in whitespace — resubmit with this "
               "text VERBATIM (indentation is part of the anchor):"
               if closest else
               ". Read the region first, then anchor on text you have "
               "actually seen."),
            **({"closest_region": closest} if closest else {}))
    if len(hits) > 1:
        raise EditError(
            index,
            f"{label} appears {len(hits)}{'+' if len(hits) > MAX_AMBIGUOUS_SHOWN else ''} "
            f"times — extend it until it is unique (include the line above "
            f"or below).",
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
            # The closing anchor need only be unique AFTER the opening
            # one: a proof block routinely ends on a line that recurs
            # elsewhere in the file, and requiring global uniqueness
            # there would push the agent back to quoting the whole span —
            # the transcription failure this form exists to avoid.
            hi = content.find(hi_text, lo + len(lo_text))
            if hi == -1:
                raise EditError(
                    i, "the closing anchor does not appear after the "
                       "opening one — check the order, or that both are "
                       "verbatim.")
            spans.append(Span(lo, hi + len(hi_text),
                              str(e.get("with") or ""),
                              "replace_between", lo_text))
        elif "insert_after" in e:
            anchor = str(e.get("insert_after") or "")
            at = _find_unique(content, anchor, i, "`insert_after` anchor")
            end = at + len(anchor)
            spans.append(Span(end, end, str(e.get("text") or ""),
                              "insert_after", anchor))
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
