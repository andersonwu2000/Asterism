"""The reviewer's own files, out of the round dir and beside the
document — and the citations that point at them.

A theory reviewer does not only rule. It writes: `review_notes.md` with
the theorem it proved past the author's stop, `reviewer_checks.py` with
the computation it reproduced. The author then cites those files in the
document it revises, and the reviewer cites them in its own
`reservations`; both name the round dir the reviewer ran in
(`.attempts/<pid>/review/r<n>/`), which is DELETED at pipeline end —
`landing`'s docstring says so out loud. So an accepted document has been
landing with pointers to proofs that no longer exist:
`g694_20260907-1202_t10_remains_open.md` carries four of them, and on
2026-09-07 a Strategist and a Theorist each filed the dangling path
through `feedback` within four minutes of reading it.

WHAT SURVIVES IS WHAT THE REVIEWER WROTE. The round dir also holds the
dossier the framework built for it, its rendered prompt, its tools
config and its provider home. The dossier is reproducible from the DB,
the prompt is derivable from the two, and the home holds A COPY OF THE
OPERATOR'S CREDENTIAL (`lab.attempt_copy_ignores`, whose comment already
made the argument for one ignore set rather than one per copier) — so
none of them travels. `review.projection_files` names the framework's
own files; everything private leads with `_`; the credential rules come
from the lab's set.

WHERE IT GOES is a sibling of the landed document, one directory per
document and one sub-directory per round:
`<papers_dir>/agent/<document-stem>/review_r<n>/<file>`. Beside the
document rather than under a shared `review/` root because a reader who
has the document then has the whole record of how it was reviewed, and
because the stem is already unique — `landing._free_name` made it so.

THE REWRITE IS THE OTHER HALF. Preserving the bytes and leaving the
citation pointing at the dead path buys nothing, so every spelling of
`.../review/r<n>/<file>` in the document body, in the provenance header
and in the verdict the header and the Strategist read becomes the
workspace-relative path of the copy. It runs once, at landing, on text
that is about to become permanent.
"""
from __future__ import annotations

import fnmatch
import re
import shutil
from pathlib import Path

#: A citation of a reviewer's file, in any spelling one has been written
#: in. Landed documents carry two today: the absolute
#: `D:/Asterism/.attempts/<pid>/review/r1/review_notes.md` the author
#: pastes out of its tool output (and its backslash twin — the seat runs
#: on Windows), and the bare `review/r4/review_notes.md` the reviewer
#: writes into `reservations`, which is relative to the dir it ran in.
#: What identifies a citation is the TAIL, so the prefix is matched and
#: discarded rather than enumerated.
#:
#: The preserved path spells the round `review_r<n>`, not `review/r<n>`,
#: so nothing this produces can match it again — that is what makes a
#: re-landing idempotent.
_CITATION_RE = re.compile(r"(?:[A-Za-z]:)?(?:[\w.\-]*[\\/])*"
                          r"review[\\/]r(\d+)[\\/]([\w.\-]+)")

#: `r<n>` under `review/`, the same shape `checkpoint.rounds_present`
#: reads.
_ROUND_DIR_RE = re.compile(r"^r(\d+)$")


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


def reviewer_files(round_dir: Path) -> "list[Path]":
    """Every file in one round dir the REVIEWER wrote, sorted by name.

    Top level only. A reviewer writes flat files into the dir it was
    given (`write_file(path, content)` — "full overwrite into your
    attempts dir"), and `review/r<n>/<file>` is the only citation
    grammar any document has used; a directory here is the provider's
    home, which must not travel."""
    from .review import PROJECTION_NAME_PATTERNS, projection_files
    framework = projection_files()
    numbered = tuple(re.compile(f"^{p}$") for p in PROJECTION_NAME_PATTERNS)
    ignores = _copy_ignores()
    out: "list[Path]" = []
    try:
        entries = sorted(Path(round_dir).iterdir())
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
    """Copy every reviewer-written file beside the document; returns the
    map from (round, file name) to the copy's workspace-relative path.

    The target is resolved through `project_docs`' own fence — the three
    checks that stop a path leaving the docs root — but written with a
    plain copy rather than `project_docs.write`: that call enforces §3.6's
    EXTENSION whitelist, which is a rule about what a person or a model
    may file as a document, and `reviewer_checks.py` is neither. What is
    landing here is evidence the framework itself produced.

    Best-effort per file. A round whose copy fails leaves its citation
    pointing where it always did — which is the state this whole module
    is fixing, so it is a worse landing and not a failed one."""
    from ...state import project_docs as _project_docs
    ws = Path(workspace)
    out: "dict[tuple[int, str], str]" = {}
    for round_no, rdir in round_dirs(Path(attempts_dir)):
        for src in reviewer_files(rdir):
            rel = f"agent/{doc_stem}/review_r{round_no}/{src.name}"
            try:
                dst = _project_docs.locate(
                    ws, project, rel, area=_project_docs.AREA_AGENT)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            except (OSError, ValueError) as exc:
                print(f"[theorist] could not preserve {src.name} from "
                      f"review r{round_no}: {exc} — the document's "
                      f"citation of it will not resolve", flush=True)
                continue
            out[(round_no, src.name)] = (
                _project_docs.root(ws, project) / Path(rel)
            ).relative_to(ws).as_posix()
    return out


def rewrite(text: str, preserved: "dict[tuple[int, str], str]") -> str:
    """`text` with every citation of a preserved file pointing at the
    copy. A citation of a file that was NOT preserved is left exactly as
    written — the document must not claim a path the shelf does not
    have."""
    if not preserved:
        return text

    def _one(m: "re.Match") -> str:
        return preserved.get((int(m.group(1)), m.group(2))) or m.group(0)

    return _CITATION_RE.sub(_one, text)


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
