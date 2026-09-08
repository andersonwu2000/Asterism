"""How a reviewing seat's package reaches it: the bytes ride IN the
prompt.

Two seats project a directory and then have to hand it to their spawn:
the batch judge (`pipeline/adversary.py`) and the theory reviewer
(`pipeline/theorist/review.py`). The four BLOCK shapes are the same for
both, because the question is the same one — the small always-read files
verbatim ("here are the bytes, do not spend a turn opening them"), the
big sparsely-read ones as the map `inspect` would have answered with
("open the one section your ruling turns on").

WHAT IS NOT HERE is which file gets which block. That is each seat's
reading of its OWN projection: the judge inlines a contract, a proposal
and a decision list; the reviewer inlines a request and the document
under review. A shared table would be a third place that has to stay in
step with two projections, and a file added to a projection but not to
its inline order is a file the reader never sees.

WHY IT PAYS. Measured over 332 gpt-era judge sessions (2026-09-07):
47.8 `inspect` reads per session, 31.7 of them on a file the same
session had already read; 10 `outline` calls because the reader has no
map; 14% of all tool-output bytes were whole-file re-reads. A round is
~14 turns and the cached re-send of a growing context is 43% of its
cost, so a file first read on turn 12 has been re-sent eleven times by
the end, while the same bytes placed in the prompt are sent once and
cached. The lab arms measured the same verdicts either way at −30% (the
judge) and −29% (the reviewer), and the two `dossier: files|inline`
flags were retired on 2026-09-08 (owner ruling): the round that names
its files and lets the reader open them no longer exists.
"""
from __future__ import annotations

import re
from pathlib import Path


def fence_for(text: str) -> str:
    """A backtick fence longer than any run inside `text`, so a body
    that quotes code or Lean stays byte-identical inside its block."""
    longest = max((len(r) for r in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def inline_block(name: str, path: Path) -> "list[str]":
    """One dossier file as the reader reads it: its name, then its body
    verbatim in a fence long enough to survive the backticks inside it.

    No line numbers and no banner. The reader quotes this text back in
    its verdict and the author is held to the quotation, so what rides
    has to be the file's own bytes — the numbered, banner-wrapped shape
    `inspect` returns is a rendering, and a rendering quoted as evidence
    is how a citation stops being checkable."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fence = fence_for(text)
    return [f"### {name}", fence, text.rstrip("\n"), fence, ""]


def outline_block(name: str, path: Path) -> "list[str]":
    """One mapped file: its size, then the outline `inspect` answers
    with — the same call, so the map in the prompt and the map the tool
    returns cannot disagree."""
    from ..knowledge import workspace_query as _wq
    try:
        lines = _wq.outline(path)
        size = path.stat().st_size
    except OSError as exc:                       # unreadable, not fatal
        return [f"### {name}", f"(outline unavailable: {exc})", ""]
    return ([f"### {name} — {size:,} bytes"] + list(lines) + [""])


def roster_block(name: str, path: Path) -> "list[str]":
    """A roster-sized file: NO outline. Its map is longer than most of
    the sections anyone wants out of it, so what rides is the way in."""
    try:
        size = f"{path.stat().st_size:,} bytes"
    except OSError:
        size = "size unknown"
    return [f"### {name} — {size}",
            f'A roster — too many sections to map. Name what you want: '
            f'`inspect(queries=[{{"read": "{name}", "outline": true, '
            f'"outline_prefix": "<prefix>"}}])` or `"outline_grep": '
            f'"<regex>"` for the headings, `{{"grep": "<name>", "in": '
            f'"{name}"}}` for one entry\'s text, `{{"decl": "<slug>"}}` '
            f'for the record\'s own answer about a goal.', ""]


def dir_block(label: str, path: Path) -> "list[str]":
    """A directory: how many entries, and the queries that reach into
    it. Never a listing — `{proofs_dir}` is the landed proof files and
    the reader wants the one file a dispute turns on, not their names."""
    if not path.is_dir():
        return [f"### {label} `{path.as_posix()}`",
                "DOES NOT EXIST — do not probe it.", ""]
    n = sum(1 for _ in path.iterdir())
    return [f"### {label} `{path.as_posix()}` — {n} entr(ies)",
            f'Not inlined and not mapped. `inspect(queries=[{{"grep": "<name>", '
            f'"in": "{path.as_posix()}/*.lean"}}])`, `{{"find": '
            f'"*<name>*"}}`, `{{"size": "{path.as_posix()}/*"}}`, or '
            f'`{{"decl": "<slug>"}}` for the record\'s own answer.', ""]


def notes_block(label: str, path: Path, *,
                areas: "tuple[str, ...]") -> "list[str]":
    """A directory of NOTES, listed by name and size, area by area.

    The one directory whose FILENAMES are evidence. `dir_block` refuses
    to list `{proofs_dir}` because the names there are `<slug>.lean` and
    no ruling turns on which of them exist; the document shelf is the
    opposite case — the theory reviewer's first criterion asks whether a
    document says something the record and the notes do not ALREADY
    have, and a reader that cannot see what is on the shelf can only
    take the document's word for it. Names and sizes, never bodies:
    twenty-odd documents at ~40KB each is the whole reason the shelf is
    not inlined."""
    if not path.is_dir():
        return [f"### {label} `{path.as_posix()}`",
                "DOES NOT EXIST — do not probe it.", ""]
    lines: "list[str]" = []
    notes = 0
    for area in areas:
        adir = path / area
        if not adir.is_dir():
            lines.append(f"- `{area}/` — not there")
            continue
        entries = sorted(adir.iterdir(), key=lambda p: p.name)
        if not entries:
            lines.append(f"- `{area}/` — empty")
            continue
        for p in entries:
            if p.is_dir():
                lines.append(f"- `{area}/{p.name}/` — "
                             f"{sum(1 for _ in p.iterdir())} entr(ies)")
                continue
            notes += 1
            try:
                size = f"{p.stat().st_size:,} bytes"
            except OSError:
                size = "size unknown"
            lines.append(f"- `{area}/{p.name}` — {size}")
    return ([f"### {label} `{path.as_posix()}` — {notes} note(s), "
             f"listed by name so you can see what already exists"]
            + lines
            + [f'Bodies are not inlined. `inspect(queries=[{{"read": '
               f'"{path.as_posix()}/<area>/<name>", "outline": true}}])` '
               f'for one note\'s map, `{{"sections": ["<heading>"]}}` for '
               f'a section, `{{"grep": "<term>", "in": '
               f'"{path.as_posix()}/*/*.md"}}` to find where a statement '
               f'already stands.', ""])
