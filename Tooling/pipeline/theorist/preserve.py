"""The files a review produced, out of the attempts dir and beside the
document — and the citations that point at them.

A theory review writes on BOTH sides. The reviewer writes
`review_notes.md` with the theorem it proved past the author's stop and
`reviewer_checks.py` with the computation it reproduced; the author
writes `checks.py`, `diagnostics.txt`, `report_before_r3_revision.md`,
`retained_r2_report.md` — the scripts its arithmetic claims are
reproducible from, the tables it quotes, the earlier versions it retains
theorems "by reference" to. Each side then cites the other's files, and
the paths they cite are inside `.attempts/<pid>/`, which is DELETED at
pipeline end — `landing`'s docstring says so out loud.

So the mathematics of an accepted document has been unrecoverable the
moment its pipeline ended. Measured on the flagship, 2026-09-08: 125
`.attempts/` citations across the landed shelf, 125 of them dangling.
The first fix (2026-09-08, `8246e7f0`) preserved half of one side — it
walked `review/r<n>/` and nothing else, and inside those dirs it dropped
the two files the framework had written, one of which is the DOCUMENT
AS THAT ROUND'S REVIEWER RULED ON IT, the version every later revision
cites.

WHAT TRAVELS is everything neither side can reproduce:

  * per round, `review_r<n>/` — what the reviewer wrote, plus
    `report.md` (the document that round ruled on) and `verdict.json`
    (the ruling itself, in its own words rather than the header's
    summary of it);
  * at the attempt root, `author/` — every file there the FRAMEWORK did
    not write, which is the author's own attachments.

WHAT DOES NOT. The dossier the framework built is reproducible from the
DB, the rendered prompt is derivable from the two, and the provider home
holds A COPY OF THE OPERATOR'S CREDENTIAL (`lab.attempt_copy_ignores`,
whose comment already made the argument for one ignore set rather than
one per copier). `review.projection_files` names the framework's own
files in a round dir and `framework_root_files` names them at the root;
everything private leads with `_`; the credential rules come from the
lab's set.

WHERE IT GOES is a sibling of the landed document, one directory per
document: `<papers_dir>/agent/<document-stem>/{review_r<n>,author}/`.
Beside the document rather than under a shared root because a reader who
has the document then has the whole record of how it was written and
reviewed, and because the stem is already unique — `landing._free_name`
made it so.

THE REWRITE IS THE OTHER HALF. Preserving the bytes and leaving the
citation pointing at the dead path buys nothing, so every spelling of a
preserved file in the document body, in the provenance header and in the
verdict the header and the Strategist read becomes the workspace-relative
path of the copy. It runs once, at landing, on text that is about to
become permanent.
"""
from __future__ import annotations

import fnmatch
import re
import shutil
from pathlib import Path

from .verdict import REPORT_BASENAME, VERDICT_BASENAME

#: The attempt ROOT, in the round slot of a preserved key. Rounds are
#: 1-based (`review/r1/` is the first one), so 0 can only mean the dir
#: above them — and an int keeps the map sortable, which `None` would
#: not.
ROOT = 0

#: Where the author's own files land, under the document's directory and
#: inside the reviewer's projection alike (`review` imports this name).
#: One spelling for both, because a document's citation of
#: `author/checks.py` and a reviewer's read of it have to name the same
#: thing.
AUTHOR_DIRNAME = "author"

#: The two files a round dir holds that the FRAMEWORK wrote and that
#: travel anyway.
#:
#: `report.md` is the document as THAT round's reviewer ruled on it. A
#: revision cites its own earlier version constantly ("Theorem 4 is
#: unchanged from the version reviewed in round 2"), and the landed file
#: is the LAST version — without the per-round copies that sentence
#: points at nothing. `verdict.json` is the ruling in the reviewer's own
#: words; the header carries a rendering of it, and a rendering quoted
#: as evidence is how a citation stops being checkable.
KEPT_ROUND_FILES = (REPORT_BASENAME, VERDICT_BASENAME)

#: `r<n>` under `review/`, the same shape `checkpoint.rounds_present`
#: reads.
_ROUND_DIR_RE = re.compile(r"^r(\d+)$")

#: A file name inside a citation: dot-separated chunks, and it NEVER
#: ends on a dot. `[\w.\-]+` would have swallowed the sentence's full
#: stop out of "…is in review/r4/review_math.md." and then looked up a
#: key with the dot on it, leaving the one citation shape a reviewer
#: writes most often unrewritten (2026-09-08, three on the flagship).
_NAME = r"[\w\-]+(?:\.[\w\-]+)*"

#: A citation's PREFIX, matched and discarded rather than enumerated:
#: what identifies a citation is its tail. Landed documents carry three
#: spellings — the absolute `D:/Asterism/.attempts/<pid>/checks.py` the
#: author pastes out of its tool output, its backslash twin (the seat
#: runs on Windows), and the bare `checks.py` a markdown link uses,
#: which is relative to the dir it was written in.
#:
#: LAZY, and that is load-bearing. A greedy prefix swallows
#: `review_r1/` and leaves `report.md` for the root branch to rewrite
#: into the landed document — the preserved round report, pointed at the
#: wrong file, on the second landing of the same run. Lazy means the
#: branches below are tried at every segment boundary, in their own
#: order, and the guard branch wins.
_PREFIX = r"(?:[A-Za-z]:)?(?:[\w.\-]*[\\/])*?"


def _copy_ignores() -> "tuple[str, ...]":
    """The lab's one set of names that must never leave an attempts tree
    (`__pycache__`, `auth.json`, `*.token`, …), plus the provider home
    names it asks the adapters for.

    Imported rather than re-spelled, for the reason that set's own
    comment gives: a copy of a credential list is the copy that keeps
    working for a month after the adapter renamed it. `Tooling/lab/` is
    dev tooling that ships with the framework — only its INPUTS (the lab
    root) are out of production's reach, and nothing here asks for one.
    An import that fails costs the extra names, never the preservation:
    the `_`-prefix rule below already drops every provider home."""
    try:
        from ...lab import attempt_copy_ignores
        return attempt_copy_ignores()
    except Exception:                                      # noqa: BLE001
        return ()


def _not_framework(directory: Path,
                   framework: "frozenset[str]") -> "list[Path]":
    """The files in one directory that `framework` does not name, sorted
    by name — the writing whoever ran there did.

    Top level only, and no directory travels: a spawn writes flat files
    into the dir it was given (`write_file(path, content)` — "full
    overwrite into your attempts dir"), and a directory there is the
    provider's home, which holds the credential."""
    from .review import PROJECTION_NAME_PATTERNS
    numbered = tuple(re.compile(f"^{p}$") for p in PROJECTION_NAME_PATTERNS)
    ignores = _copy_ignores()
    out: "list[Path]" = []
    try:
        entries = sorted(Path(directory).iterdir())
    except OSError:
        return []
    for p in entries:
        if not p.is_file() or p.name.startswith("_"):
            continue
        if p.name in framework or any(rx.match(p.name) for rx in numbered):
            continue
        if any(fnmatch.fnmatch(p.name, pat) for pat in ignores):
            continue
        out.append(p)
    return out


def framework_root_files() -> "frozenset[str]":
    """Every file name the FRAMEWORK puts at the root of a Theorist's
    attempts dir — so that everything else there is the author's.

    Assembled from the rosters the writers keep, never a fourth literal
    list. `checkpoint._CARRY_SKIP_FILES` is the maintained one: its
    members are exactly the files "the process that wrote it" owns, and
    its own comment says every one of them is rewritten by
    `compile_strategist_context`. The round-fresh record files and the
    reviewer's inline order carry the rest (`report.md`, `since.md`,
    `charter.md`, `PROGRAMME.md`), and `dialogue.md` is the checkpoint's
    own brief to a fresh author.

    A name that goes missing here costs a framework file copied into
    `author/` and offered to the next reviewer as an attachment — noise,
    not a leak: the `_`-prefix rule and the lab's ignore set are what
    hold the credential back, and neither is on this list."""
    from ..round_materials import ROUND_FILES
    from .checkpoint import DIALOGUE_BASENAME, _CARRY_SKIP_FILES
    from .review import DOSSIER_INLINE_ORDER
    names = (set(_CARRY_SKIP_FILES) | set(ROUND_FILES)
             | set(DOSSIER_INLINE_ORDER) | {DIALOGUE_BASENAME})
    try:
        from ...agent.context import PAPER_MAP_COMPANION
        names.add(PAPER_MAP_COMPANION)
    except Exception:                                      # noqa: BLE001
        pass
    return frozenset(names)


def reviewer_files(round_dir: Path) -> "list[Path]":
    """Every file in one round dir the REVIEWER wrote, sorted by name."""
    from .review import projection_files
    return _not_framework(round_dir, projection_files())


def round_files(round_dir: Path) -> "list[Path]":
    """Everything one round dir contributes to the record: what the
    reviewer wrote, plus the two framework files that travel anyway (see
    `KEPT_ROUND_FILES`)."""
    kept = [Path(round_dir) / n for n in KEPT_ROUND_FILES]
    return sorted(reviewer_files(round_dir) + [p for p in kept if p.is_file()],
                  key=lambda p: p.name)


def author_files(attempts_dir: Path) -> "list[Path]":
    """Every file at the attempts ROOT the AUTHOR wrote, sorted by name.

    The other half of the record, and the one nothing was preserving:
    the scripts a document says its arithmetic is reproducible from, the
    tables it quotes, and the earlier versions it retains theorems by
    reference to. Same rule as the round dir, one directory up and
    against the root's own framework roster."""
    return _not_framework(attempts_dir, framework_root_files())


def round_dirs(attempts_dir: Path) -> "list[tuple[int, Path]]":
    """(round number, dir) for every round this run has a dossier for."""
    from .review import PROJECTION_DIRNAME
    root = Path(attempts_dir) / PROJECTION_DIRNAME
    out: "list[tuple[int, Path]]" = []
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return []
    for d in entries:
        m = _ROUND_DIR_RE.match(d.name)
        if d.is_dir() and m:
            out.append((int(m.group(1)), d))
    return sorted(out)


def preserve(workspace: Path, *, project: str, attempts_dir: Path,
             doc_stem: str) -> "dict[tuple[int, str], str]":
    """Copy the review's files beside the document; returns the map from
    (round, file name) to the workspace-relative path a citation of that
    file should name. `ROOT` is the attempts dir itself.

    The target is resolved through `project_docs`' own fence — the three
    checks that stop a path leaving the docs root — but written with a
    plain copy rather than `project_docs.write`: that call enforces §3.6's
    EXTENSION whitelist, which is a rule about what a person or a model
    may file as a document, and `checks.py` is neither. What is landing
    here is the evidence a reviewed document rests on.

    ONE ENTRY IS NOT A COPY. `report.md` at the root is the document
    itself, so a citation of it resolves to the landed file rather than
    to a duplicate of it — the name is settled before this runs, which
    is why `landing` calls it after `_free_name` and not before.

    Best-effort per file. A file whose copy fails leaves its citation
    pointing where it always did — which is the state this whole module
    is fixing, so it is a worse landing and not a failed one."""
    from ...state import project_docs as _project_docs
    ws = Path(workspace)

    def _copy(src: Path, rel: str, where: str) -> str:
        try:
            dst = _project_docs.locate(
                ws, project, rel, area=_project_docs.AREA_AGENT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except (OSError, ValueError) as exc:
            print(f"[theorist] could not preserve {src.name} from {where}: "
                  f"{exc} — the document's citation of it will not resolve",
                  flush=True)
            return ""
        return (_project_docs.root(ws, project) / Path(rel)
                ).relative_to(ws).as_posix()

    out: "dict[tuple[int, str], str]" = {}
    for round_no, rdir in round_dirs(Path(attempts_dir)):
        for src in round_files(rdir):
            got = _copy(src, f"agent/{doc_stem}/review_r{round_no}/{src.name}",
                        f"review r{round_no}")
            if got:
                out[(round_no, src.name)] = got
    for src in author_files(Path(attempts_dir)):
        got = _copy(src, f"agent/{doc_stem}/{AUTHOR_DIRNAME}/{src.name}",
                    "the attempt root")
        if got:
            out[(ROOT, src.name)] = got
    out[(ROOT, REPORT_BASENAME)] = (
        _project_docs.root(ws, project) / _project_docs.AREA_AGENT
        / f"{doc_stem}.md").relative_to(ws).as_posix()
    return out


def _citation_re(preserved: "dict[tuple[int, str], str]") -> "re.Pattern":
    """The one pattern every citation of a preserved file matches, built
    from the names that were actually preserved.

    Three branches, tried in this order at every segment boundary:

      1. `review_r<n>/<file>` — a path this function ALREADY produced.
         It is matched so that it is CONSUMED, and returned untouched.
         Without it the third branch would see the bare `report.md` at
         its tail and rewrite a preserved round report into the landed
         document, so a second landing of one run would corrupt what the
         first one got right.
      2. `review/r<n>/<file>` — the round dir, in any prefix spelling.
         Generic in the file name: a name that was not preserved falls
         through the map and is left as written, because the document
         must not claim a path the shelf does not have.
      3. one of the ROOT names, by name. Not generic — the root branch
         matches a BARE file name, and a pattern that took any word
         ending in `.py` would rewrite prose about a file nobody kept.

    The name is fenced on both sides: `(?<![\\w.\\-])` so that
    `review_checks.py` does not match a preserved `checks.py` at its
    tail, and `(?![\\w\\-\\\\/])` so that `checks.pyc` does not match it
    at its head — while a trailing full stop, comma or bracket, which is
    how every real citation ends, still does."""
    root = sorted((name for (rnd, name) in preserved if rnd == ROOT),
                  key=len, reverse=True)
    # An alternation that can never match, when nothing at the root was
    # preserved: `|`-joining an empty list would match the empty string.
    alt = "|".join(re.escape(n) for n in root) or r"(?!)"
    return re.compile(
        r"(?<![\w.\-])" + _PREFIX + r"(?:"
        r"review_r(?P<kept>\d+)[\\/](?P<keptname>" + _NAME + r")"
        r"|review[\\/]r(?P<round>\d+)[\\/](?P<rname>" + _NAME + r")"
        r"|(?P<root>" + alt + r")(?![\w\-\\/])"
        r")")


def rewrite(text: str, preserved: "dict[tuple[int, str], str]") -> str:
    """`text` with every citation of a preserved file pointing at the
    copy. A citation of a file that was NOT preserved is left exactly as
    written — the document must not claim a path the shelf does not
    have."""
    if not preserved:
        return text

    def _one(m: "re.Match") -> str:
        if m.group("kept") is not None:
            return m.group(0)
        if m.group("round") is not None:
            return preserved.get((int(m.group("round")),
                                  m.group("rname"))) or m.group(0)
        return preserved.get((ROOT, m.group("root"))) or m.group(0)

    return _citation_re(preserved).sub(_one, text)


def rewrite_verdict(verdict: "dict | None",
                    preserved: "dict[tuple[int, str], str]") -> "dict | None":
    """The ruling as everything downstream will read it.

    Every string, not only `reservations`: the header renders the
    per-criterion lines too (`verdict.verdict_lines`), and a reviewer
    that says "the check is in review/r2/reviewer_checks.py" inside a
    `clear:` bullet has written the same dangling path. Bullets rendered
    as objects are walked for the same reason `verdict._as_bullet`
    accepts them."""
    if not preserved or verdict is None:
        return verdict
    return _walk(verdict, preserved)


def _walk(value, preserved: "dict[tuple[int, str], str]"):
    if isinstance(value, str):
        return rewrite(value, preserved)
    if isinstance(value, list):
        return [_walk(v, preserved) for v in value]
    if isinstance(value, dict):
        return {k: _walk(v, preserved) for k, v in value.items()}
    return value
