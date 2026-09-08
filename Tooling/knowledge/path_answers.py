"""What a wrong path costs should be nothing — the answer to a miss.

Split out of `knowledge/workspace_query.py` 2026-09-08, the second half
of the split that file's watermark has been promising since 08-29. One
subject: when a query names a path that does not answer, what does the
reader get back instead — the listing of what IS there, the resolution
clause, and the rules about when a same-named file found elsewhere may
be handed over as THE answer.

The names stay private-by-convention on the consuming side:
`workspace_query` re-exports them under the `_`-prefixed spellings its
readers and tests already use.
"""
from __future__ import annotations

from pathlib import Path

def resolution_note(spec: str, cwd: Path) -> str:
    """The "relative paths resolve against …" clause — for RELATIVE
    paths only.

    An absolute `in:` is used exactly as given (`_resolve` returns it
    untouched), so appending this clause to an absolute miss described a
    resolution that never happened. On an empty-but-granted directory
    the two halves read as one sentence — "Library is empty" plus
    "relative paths resolve against …/even_sum_subsets" — and the
    presearch seat concluded the framework had silently re-pointed its
    absolute path at the problem dir and shipped an empty block
    (g3, 2026-09-06). A message that misdescribes its own mechanism is
    one an agent cannot act on correctly."""
    if Path(spec).is_absolute():
        return ""
    return f" (relative paths resolve against {cwd})"


def dir_listing(d: Path) -> "list[str]":
    """Up to 20 entry names of `d`, directories marked with a slash."""
    try:
        return sorted(x.name + ("/" if x.is_dir() else "")
                      for x in d.iterdir())[:20]
    except OSError:
        return []


def nearest_dir_note(p: Path) -> str:
    """The deepest existing ancestor of `p`, and what is in it."""
    for d in p.parents:
        if d.is_dir():
            names = dir_listing(d)
            listing = ", ".join(names) if names else "(empty)"
            return f"nearest existing directory is {d} — it holds: {listing}"
    return "no existing parent directory"


def may_prescribe(spec: "str | None", p: Path, found: Path) -> bool:
    """Whether a same-named file found elsewhere may be handed over as
    THE answer ("use that path"), rather than merely named.

    Yes in two cases, and they are the two the basename search was built
    for:

      * the spec named no directory at all (`CATALOG.md`) — it asked
        "where is this file", and anywhere is where it is;
      * the spec's directories are a suffix of the found path, so the
        hit is under exactly what was asked for;
      * the directory the spec named does not EXIST — a mistyped
        `prooofs/L_a.lean` is one document, misspelled, and the file of
        that name is what was meant (2026-08-15).

    No when the directory the spec named is real and the file simply is
    not in it. Then a same-named file under other directories is a
    different document: a reviewer asked for
    `…/54c1fb01…/review/r2/report.md` and was told, imperatively, "but a
    file of that name is at …/4fea01b9…/review/r1/report.md — use that
    path". Another attempt, another round; every segment that identified
    the document had been dropped by the basename search, and the answer
    was phrased as an instruction (2026-09-08 field reading).
    """
    if spec is None:
        return True
    want = [s for s in Path(str(spec).replace("\\", "/")).parts
            if s not in (".", "/", "")]
    if len(want) <= 1:
        return True
    if list(found.parts)[-len(want):] == want:
        return True
    try:
        return not p.parent.is_dir()
    except OSError:
        return False


def glob_miss_note(prefix: Path, pattern: str) -> str:
    """A glob that matched nothing: the directory the pattern ran under,
    and what is in it.

    Not `nearest_existing`: that one answers about a PATH, and a glob's
    glob-free prefix is a directory every time, so it always came back
    "that path IS a directory … the path was used exactly as given" —
    a sentence about a path nobody typed (the pattern had been cut off
    it) which never mentioned that a pattern had matched nothing. The
    two questions have two answers."""
    if not prefix.is_dir():
        return (f"{prefix} is not a directory — {nearest_dir_note(prefix)}")
    names = dir_listing(prefix)
    where = f"{pattern!r} was matched under {prefix}, which "
    return where + (f"holds: {', '.join(names)}" if names else "is EMPTY")


def nearest_existing(p: Path, cwd: "Path | None" = None,
                      spec: "str | None" = None) -> str:
    """What a wrong path costs should be nothing.

    Before this, a mistyped path cost a whole round-trip: the agent got
    "no such file" and spent its next turn on `ls` to find out what was
    actually there. Answer both at once.

    `spec` is the path AS TYPED, and it is what decides whether a
    same-named file found elsewhere may be handed over as the answer —
    see `_asked_for_this_place`."""
    if p.is_dir():
        # Reading a directory as a file used to answer with the PARENT
        # listing, so telling "empty dir" from "wrong path" cost an
        # extra probe (feedback, 2026-08-25). The path exists — list
        # its own contents.
        names = dir_listing(p)
        if not names:
            # "it holds: (empty)" beside a resolution note read as "your
            # path was re-pointed somewhere empty". Say the one fact
            # that settles it: the path you named is the path that was
            # looked at, and it has nothing in it.
            return ("that path IS a directory and it is EMPTY — the path "
                    "was used exactly as given; there is nothing under it")
        return f"that path IS a directory — it holds: {', '.join(names)}"
    if cwd is not None:
        # Lazily, and deliberately: the basename walk belongs to the
        # resolver (it knows the spawn's roots and the skip list),
        # while what to SAY about its hit belongs here. The import
        # runs at call time so the two modules can point at each
        # other without an import cycle.
        from .workspace_query import _find_by_basename
        found = _find_by_basename(p.name, cwd)
        if found is not None:
            if may_prescribe(spec, p, found):
                return f"but a file of that name is at {found} — use that path"
            # Named, never prescribed: the reader asked about one
            # attempt / one round and this is another one's document.
            return (f"a same-named file exists elsewhere ({found}) but it "
                    f"is a different attempt/round — cite it only if you "
                    f"mean that one; {nearest_dir_note(p)}")
    return nearest_dir_note(p)
