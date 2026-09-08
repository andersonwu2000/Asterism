"""A line number of `Context.md` is only a line number of ONE Context.md.

A `Theorize` request is written by the Strategist and read by a
Theorist, in two different documents. Both are called `Context.md`, both
come out of the same renderer, and neither has the same length: the
Strategist's wake is compiled from that wake's record, the Theorist's
from the record as it stands when the Theorist starts. So a `situation`
that says "…its p=k+1 continuation retained a polynomial obstruction
(Context.md line 113)" — which the Strategist wrote truthfully about the
document in front of it — reaches the Theorist as a pointer into a file
that ends at line 107. That is exactly what happened on 2026-09-08
(Erdos.p1094, decision 6039 → the theorist's own report of it), and the
seat could do nothing with it but say so.

A LINE NUMBER IS NOT A NAME. What both documents DO share is their
section headings, which the renderer emits from one list and `inspect`
resolves by name (`{"read": "Context.md", "sections": [...]}`). So the
fix is to resolve the reference while the document it was written
against still exists — at commit, in the Strategist's own attempts dir —
and store the SECTION it fell in. What lands in the row, and therefore
in every later reader (the Theorist's `## Trigger`, `BATCHES.md`, the
judge's projection), is a name that resolves wherever it is read.

Only `Context.md` references are rewritten. A citation into a theory
document ("g741, lines 346–354") points at a file on the Project's
shelf that does not change under the reader, and rewriting those would
be taking away a precise pointer for no reason.

Nothing here may raise: a request whose provenance cannot be resolved is
still a request, and losing the wake over a rewrite would be worse than
the pointer it was fixing.
"""
from __future__ import annotations

import re
from pathlib import Path

#: `Context.md line 113`, `Context.md lines 113-114`, `Context.md:21`,
#: `Context.md §line 9`. The separator class covers the hyphen, the en
#: dash and the em dash, because agents write all three.
_REF = re.compile(
    r"Context\.md\s*(?:§\s*)?(?::\s*|\bline[s]?\s*)"
    r"(\d+)(?:\s*[-–—]+\s*(\d+))?",
    re.IGNORECASE)

#: A markdown heading. Same shape `knowledge/workspace_query` reads
#: sections with; spelled here rather than imported because the pipeline
#: layer must not depend on the tools layer for a five-token regex.
_HEADING = re.compile(r"^(#{1,4})\s+(\S.*?)\s*$")

#: Sections named per reference. A range that crosses the whole document
#: would otherwise print a table of contents inside a sentence.
_MAX_SECTIONS = 3


def _headings(text: str) -> "list[tuple[int, str]]":
    """`(1-based line, heading text)` for every heading, in order."""
    out: "list[tuple[int, str]]" = []
    for i, line in enumerate(text.splitlines(), 1):
        m = _HEADING.match(line)
        if m:
            out.append((i, f"{m.group(1)} {m.group(2)}"))
    return out


def _sections_spanning(heads: "list[tuple[int, str]]", a: int, b: int,
                       total: int) -> "list[str]":
    """The headings whose sections the lines `a..b` fall in.

    A line ABOVE the first heading belongs to no section — the document
    opens with its title — and answers empty, which the caller renders
    as the unresolved form rather than inventing a section for it."""
    if a > total:
        return []
    out: "list[str]" = []
    for k, (start, text) in enumerate(heads):
        end = heads[k + 1][0] - 1 if k + 1 < len(heads) else total
        if start <= b and end >= a:
            out.append(text)
    return out


def resolve_context_line_refs(text: str,
                              context_md: "Path | str | None") -> str:
    """`text` with every `Context.md line N` replaced by the SECTION of
    `context_md` that line falls in.

    `context_md` is the document the writer was looking at — the
    Strategist's own `Context.md`, still on disk at commit. A reference
    into it that cannot be resolved (the file is gone, the line is past
    its end, the document has no headings) is not silently kept and is
    not silently dropped: it is rewritten to say whose document the
    number belongs to, which is the one thing the downstream reader
    could not know.

    `context_md=None` means nobody told us WHICH document the writer was
    looking at — the human channel files a `Theorize` through these same
    appliers and has no wake directory. The text then comes back
    untouched: with no candidate document there is no basis for saying
    whose lines these are, and a person's pointer is the person's."""
    if not text or context_md is None or not _REF.search(text):
        return text or ""
    body = ""
    try:
        path = Path(context_md)
        if path.is_file():
            body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        body = ""
    heads = _headings(body)
    total = len(body.splitlines())

    def _one(m: "re.Match[str]") -> str:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if b < a:
            a, b = b, a
        named = _sections_spanning(heads, a, b, total) if heads else []
        if not named:
            # Say what the number IS, since it is not this reader's.
            span = f"line {a}" if a == b else f"lines {a}-{b}"
            return (f"Context.md ({span} of the strategist's own wake — "
                    f"not of this file)")
        shown = named[:_MAX_SECTIONS]
        more = "" if len(named) == len(shown) else " and below"
        return ("Context.md § "
                + " / ".join(f"`{h}`" for h in shown) + more)

    return _REF.sub(_one, text)


def resolve_theory_request(payload: dict,
                           context_md: "Path | str | None") -> dict:
    """`{"objective", "situation"}` with their `Context.md` line
    references resolved. Returns a NEW dict; the caller's is untouched.

    Both fields, because either can carry the pointer: the objective is
    where a Strategist names the statement it wants, and it cites the
    same document to say where the statement stands."""
    out = dict(payload or {})
    for key in ("objective", "situation"):
        if key in out:
            try:
                out[key] = resolve_context_line_refs(
                    str(out[key] or ""), context_md)
            except Exception:  # noqa: BLE001 — never lose the request
                pass
    return out
