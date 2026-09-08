"""A markdown document's STRUCTURE — headings, sections, the roster map.

Split out of `knowledge/workspace_query.py` 2026-09-08 (that file's
watermark note has carried a split promise since 08-29). Everything here
is pure text: no path resolution, no filesystem, no read scope. That is
the seam — `workspace_query` decides WHICH file answers a query, this
module decides what the file's shape is.

Everything moved unchanged.
"""
from __future__ import annotations

import re

#: `outline: true` lists a file whole only up to this many sections.
#: Past it the map IS the roster (CATALOG.md: 1,333 sections, 30-60K
#: chars — owner ruling 2026-08-29) and must be asked for by name:
#: `outline_prefix` / `outline_grep`, answered up to this many hits.
OUTLINE_INLINE_MAX = 120
OUTLINE_MATCH_MAX = 60

#: A markdown heading, which is how a framework document declares its
#: sections. Level 1-4 only: deeper is prose formatting, not structure.
HEADING_RE = re.compile(r"^(#{1,4})\s+(\S.*?)\s*$")

def sections(lines: "list[str]") -> "list[tuple[str, int, int, int]]":
    """(heading text, level, first line, last line) for each section.

    A section runs to the next heading of the SAME OR SHALLOWER level, so
    asking for `## Programme` brings its `###` subsections with it — the
    nesting a reader means when it names a section. Line numbers are
    1-based and inclusive, so they can be handed straight back as
    `lines`."""
    heads = []
    for i, ln in enumerate(lines, 1):
        m = HEADING_RE.match(ln)
        if m:
            heads.append((m.group(2), len(m.group(1)), i))
    out = []
    for k, (text, level, start) in enumerate(heads):
        end = len(lines)
        for text2, level2, start2 in heads[k + 1:]:
            if level2 <= level:
                end = start2 - 1
                break
        out.append((text, level, start, end))
    return out


def numbered(lines: "list[str]", a: int, b: int) -> "list[str]":
    return [f"{n:>5}  {lines[n - 1]}"
            for n in range(max(1, a), min(len(lines), b) + 1)]


def strip_parenthetical(s: str) -> str:
    """`programme (rev 3, judge-passed)` -> `programme` — the dynamic
    annotation is presentation on the same name, dropped on BOTH sides
    so yesterday's `(rev 2)` still names today's section."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()


def heading_key(s: str) -> str:
    """A requested section name, normalized the way readers type it.

    The outline prints `## Programme (rev 3)` and `sections` used to
    accept only the bare heading text — copy-pasting from the outline,
    the obvious workflow, failed (40+ self-reports). Leading heading
    markers and wrapping backticks are presentation, not identity."""
    return str(s).strip().strip("`").lstrip("#").strip().lower()


def outline_roster(secs, spec: str, why: str) -> "list[str]":
    """A roster-sized file's map is the roster itself (CATALOG.md: 1,333
    headings, 30-60K chars), so it is never shipped whole. What ships is
    the way to NAME a slice — heading-prefix counts, short by
    construction — and the two questions a roster actually answers."""
    counts: "dict[str, int]" = {}
    for text, *_ in secs:
        tok = re.split(r"[_\s]", heading_key(text), 1)[0][:24]
        counts[tok] = counts.get(tok, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
    return [
        f'{why} Name what you want: `outline_prefix: "<prefix>"` (case-'
        f"insensitive, up to {OUTLINE_MATCH_MAX} hits) or `outline_grep: "
        f'"<regex>"`; a live goal: {{"decl": "<slug or gNNNN>"}}; one '
        f'entry\'s text: {{"grep": "<name>", "in": {spec!r}}}.',
        f"heading prefixes (token before the first `_`; {len(counts)} "
        f"distinct, top {len(top)}): "
        + ", ".join(f"{k} ({n})" for k, n in top)]
