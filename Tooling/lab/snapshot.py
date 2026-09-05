"""`asterism lab snapshot` — the SLICE: one problem's state, taken out
of a live workspace, optionally rewound to a historical instant.

A slice is a `carry` bundle and deliberately nothing else:

    carry.db             the DB pruned to this problem's rows, with
                         `library_*` / `projects` carried whole
    files.tar.gz         the problem directory, the papers bound to it,
                         and the Project's `_docs/{user,agent}`
    manifest.json        carry's manifest plus the lab's four questions:
                         when it was taken, off which framework commit,
                         at which Programme revision, over how many goals
    source.db            (rewound slices only) the pruned copy BEFORE the
                         rewind — what a judge replay re-judges
    _rewind_ledger.json  (rewound slices only) per directory: kept,
                         dropped, and which provenance signal decided

Reusing carry's bundle rather than inventing a second one is the point:
`lab build` lands the slice with `carry import`, so "which rows are this
problem's" has exactly one answer (`state/carry.py`), the one that was
paid for by two hand-shuttle leaks.

THREE THINGS THE LAB NEEDS THAT `carry export` DOES NOT DO.

  1. It runs while a daemon writes. `carry export` refuses on
     `daemon.pid` because it is about to REPLACE rows somewhere; a
     snapshot only reads, and the live board never stops. The copy is
     taken with `mode=ro` plus the sqlite backup API — WAL-safe, no
     write lock, one atomic step. Never `shutil.copyfile`: in WAL mode
     the committed state lives partly in `-wal`.
  2. It carries the Project's `_docs/`. `carry export` leaves that tree
     behind on purpose — it moves a problem into a workspace that
     already has the Project's shelf. A lab workspace is built EMPTY, so
     nothing will ever supply it, and `_docs/user/` is the owner's notes
     the Context renders while `_docs/agent/` is the theory shelf the
     reviewer reads.
  3. `--rewind` moves the rows and the files in ONE action. The 2026-09-04
     replay paid for the alternative twice: the rewind was a DB tool and
     the files came from the live tree, so a judge rewound to 23:31Z
     read a proof that landed eleven hours later, then fired twice
     citing an owner's note written 10.4 hours later.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import LabError, REPO, snapshots_dir
from . import rewind as _rewind
from ..state import carry as _carry

#: The bundle's four files. `source.db` and the ledger appear only on a
#: rewound slice — see the module docstring.
CARRY_DB = "carry.db"
FILES_TAR = "files.tar.gz"
MANIFEST = "manifest.json"
SOURCE_DB = "source.db"


@dataclass(frozen=True)
class Slice:
    """One slice on disk: its id, its directory and its manifest."""
    id: str
    path: Path
    manifest: dict

    @property
    def problem(self) -> str:
        return str(self.manifest.get("problem") or "")

    @property
    def cutoff(self) -> "str | None":
        rw = self.manifest.get("rewind") or {}
        return str(rw.get("cutoff")) if rw.get("cutoff") else None

    @property
    def source_db(self) -> Path:
        """The DB a replay reads a HISTORICAL row out of: the pre-rewind
        copy when there is one, otherwise the slice's own DB (an
        un-rewound slice already holds every row it ever had)."""
        p = self.path / SOURCE_DB
        return p if p.is_file() else self.path / CARRY_DB


# ---------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------

def _stamp(iso: str) -> str:
    """An instant as a filename component — `20260826-041105Z`."""
    dt = _rewind._parse_iso(iso)
    if dt is None:
        raise LabError(f"{iso!r} is not an ISO-8601 instant")
    return dt.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S") + "Z"


def slice_id(problem: str, *, cutoff: "str | None" = None,
             taken: "str | None" = None) -> str:
    """The slice's directory name.

    A REWOUND slice is named for its cutoff and nothing else, because it
    is reproducible: the same problem at the same instant is the same
    scene however many times it is taken, so a `rewind:` block in
    lab.yaml can name the directory it wants without having taken it
    yet (`ensure_slice`). An un-rewound one is named for the instant the
    copy was taken, because that is the only thing that distinguishes it
    from the next one — the live board never stops.
    """
    if cutoff:
        return f"{problem}@{_stamp(cutoff)}"
    return f"{problem}_{_stamp(taken or _now_iso())}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _code_commit() -> str:
    """The framework commit this snapshot was taken at — the answer to
    "which carry / rewind code produced these rows". `git describe`'s
    dirty flag rides along: a slice taken off an unsaved working tree is
    one nobody can reproduce, and the manifest should say so."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "describe", "--always", "--dirty",
             "--abbrev=12"],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


# ---------------------------------------------------------------------
# the copy
# ---------------------------------------------------------------------

def snapshot_db(live_db: Path, dst: Path) -> None:
    """One consistent copy of a DB that is being written underneath.

    `mode=ro` plus the backup API: the read side takes no write lock and
    the copy is a single atomic step, so the daemon's own transactions
    neither block it nor bleed into it. Never `shutil.copyfile` — in WAL
    mode the committed state lives partly in `-wal`, and a bare file
    copy silently loses it.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    src = sqlite3.connect(f"file:{Path(live_db).as_posix()}?mode=ro",
                          uri=True)
    try:
        out = sqlite3.connect(str(dst))
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _members(workspace: Path, conn: sqlite3.Connection,
             problem: str) -> "tuple[list[tuple[Path, str]], list[str]]":
    """Everything the slice carries, as `(absolute, workspace-relative)`.

    `carry`'s own member list (the problem directory minus the run-scoped
    scratch, plus the papers bound to P) plus the Project's two document
    areas — reason 2 in the module docstring. Asking carry for its half
    rather than re-walking the tree keeps the exclusions (`.presearch`,
    `.drafts`, `.index_attempt`) in one place.
    """
    from ..core.cli import carry as _carry_cli
    from ..state import project_docs as _project_docs
    from ..state import projects as _projects

    members, skipped = _carry_cli._members(workspace, conn, problem)
    seen = {arc for _, arc in members}
    project = (_projects.project_of(conn, problem)
               or problem.split(".", 1)[0])
    try:
        root = _project_docs.root(workspace, project)
    except ValueError:
        return members, skipped
    for area in _project_docs.AREAS:
        adir = root / area
        if not adir.is_dir():
            continue
        for path in sorted(adir.rglob("*")):
            if not path.is_file():
                continue
            arc = path.relative_to(workspace).as_posix()
            if arc not in seen:
                seen.add(arc)
                members.append((path, arc))
    # carry's exclusion note is about ITS bundle, not this one.
    skipped = [s for s in skipped
               if not s.startswith(_project_docs.ROOT_DIRNAME)]
    return members, skipped


def _write_tar(tarball: Path, members: "list[tuple[Path, str]]") -> int:
    total = 0
    if tarball.exists():
        tarball.unlink()
    with tarfile.open(tarball, "w:gz") as tf:
        for path, arc in members:
            tf.add(str(path), arcname=arc)
            total += path.stat().st_size
    return total


def _stage_members(stage: Path) -> "list[tuple[Path, str]]":
    return [(p, p.relative_to(stage).as_posix())
            for p in sorted(stage.rglob("*")) if p.is_file()]


# ---------------------------------------------------------------------
# taking one
# ---------------------------------------------------------------------

def take(workspace: Path, root: Path, *, problem: str,
         cutoff: "str | None" = None) -> Slice:
    """Take one slice of `problem` out of `workspace` into `<root>/
    snapshots/<id>/`. Refuses an id that already exists — reuse is
    `ensure_slice`'s decision, made before any bytes are written."""
    workspace = Path(workspace).resolve()
    live_db = workspace / "asterism.db"
    if not live_db.is_file():
        raise LabError(f"no asterism.db in {workspace}")
    taken = _now_iso()
    dest = snapshots_dir(root) / slice_id(problem, cutoff=cutoff, taken=taken)
    if dest.exists() and any(dest.iterdir()):
        raise LabError(
            f"{dest} already holds a slice — a half-overwritten bundle "
            f"is one whose manifest describes rows it no longer has. "
            f"Delete it, or let `lab run` reuse it.")
    dest.mkdir(parents=True, exist_ok=True)

    bundle_db = dest / CARRY_DB
    snapshot_db(live_db, bundle_db)
    snap = _open(bundle_db)
    try:
        if snap.execute("SELECT 1 FROM problems WHERE name = ?",
                        (problem,)).fetchone() is None:
            raise LabError(
                f"unknown problem {problem!r} in {workspace} — "
                f"`asterism status {problem}` lists what it holds")
        _carry.assert_classified(snap)
        members, skipped = _members(workspace, snap, problem)
        kept = _carry.prune_to_problem(snap, problem)
        orphans = _carry.orphans(snap)
        if orphans:
            raise LabError(
                f"the pruned slice has orphan rows — the prune missed a "
                f"goal-keyed table: {orphans}")
        bad = _carry.foreign_key_findings(snap)
        if bad:
            raise LabError(
                f"the pruned slice fails foreign_key_check: {bad[:5]}")
        version = int(snap.execute("PRAGMA user_version").fetchone()[0])
        goal_count = int(snap.execute(
            "SELECT COUNT(*) FROM goals WHERE problem = ?",
            (problem,)).fetchone()[0])
        project = str(snap.execute(
            "SELECT project FROM problems WHERE name = ?",
            (problem,)).fetchone()[0] or "")
        snap.execute("VACUUM")
    finally:
        snap.close()

    total = _write_tar(dest / FILES_TAR, members)
    rewound: "dict | None" = None
    if cutoff:
        rewound = _rewind_in_place(dest, workspace=workspace,
                                   problem=problem, cutoff=cutoff)
        total = rewound.pop("_bytes")
    programme_rev, goal_count = _scene(dest / CARRY_DB, problem, goal_count)

    manifest = {
        "tool": "asterism carry",
        "format": 1,
        "problem": problem,
        "project": project,
        "exported_at": taken,
        "taken_utc": taken,
        "source_workspace": str(workspace),
        "source_head": _head_sha(workspace),
        "code_commit": _code_commit(),
        "schema_user_version": version,
        "row_counts": {t: n for t, n in sorted(kept.items()) if n},
        "goal_count": goal_count,
        "programme_rev": programme_rev,
        "files": {"entries": len(members), "bytes": total,
                  "excluded": skipped},
    }
    if rewound is not None:
        manifest["rewind"] = rewound
    (dest / MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return Slice(dest.name, dest, manifest)


def _head_sha(workspace: Path) -> "str | None":
    try:
        out = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def _scene(bundle_db: Path, problem: str,
           fallback_goals: int) -> "tuple[int | None, int]":
    """The Programme revision and goal count the slice actually carries,
    read back out of the bundle. Read AFTER any rewind, because that is
    the scene a run starts from — a manifest quoting the pre-rewind
    numbers describes a workspace nobody will ever open."""
    c = sqlite3.connect(f"file:{bundle_db.as_posix()}?mode=ro", uri=True)
    try:
        rev = c.execute(
            "SELECT MAX(rev) FROM programme_revisions"
            " WHERE problem = ? AND status = 'passed'", (problem,)
        ).fetchone()[0]
        goals = c.execute("SELECT COUNT(*) FROM goals WHERE problem = ?",
                          (problem,)).fetchone()[0]
    except sqlite3.OperationalError:
        return None, fallback_goals
    finally:
        c.close()
    return (int(rev) if rev is not None else None), int(goals)


def _rewind_in_place(dest: Path, *, workspace: Path, problem: str,
                     cutoff: str) -> dict:
    """Move the slice — both planes — back to `cutoff`.

    The tarball is staged, the rows are rewound, the file rules run over
    the staging tree, and the tarball is written again from what
    survives. The pruned PRE-rewind DB is kept as `source.db`: the file
    rules compare against it (a proof is late iff it is proved there and
    not here), and a judge replay re-judges a proposal the rewind
    deleted, which nothing in `carry.db` can supply any more.

    `git_root` is the LIVE workspace, not the staging tree: the bytes
    are staged but the git history of the same workspace-relative path
    is where the commits are, and `_docs/user/` — the owner's own
    writing — has no other authoritative signal.
    """
    shutil.copy2(dest / CARRY_DB, dest / SOURCE_DB)
    stage = Path(tempfile.mkdtemp(prefix="asterism-lab-slice-"))
    try:
        with tarfile.open(dest / FILES_TAR, "r:gz") as tf:
            tf.extractall(str(stage), filter="data")
        conn = _rewind.open_copy_for_rewind(dest / CARRY_DB)
        try:
            rep = _rewind.rewind(conn, problem=problem, cutoff=cutoff)
            ledger = _rewind.rewind_files(
                conn, snapshot_db=dest / SOURCE_DB, workspace=stage,
                problem=problem, cutoff=cutoff, git_root=workspace)
        finally:
            conn.close()
        led_path = stage / _rewind.LEDGER_BASENAME
        if led_path.is_file():
            shutil.move(str(led_path), str(dest / _rewind.LEDGER_BASENAME))
        total = _write_tar(dest / FILES_TAR, _stage_members(stage))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"cutoff": cutoff, "source_db": SOURCE_DB,
            "ledger": _rewind.LEDGER_BASENAME, "rows": rep,
            "directories": {k: {"kept": v["kept"], "dropped": v["dropped"],
                                "provenance": v["provenance"]}
                            for k, v in ledger["directories"].items()},
            "undated": ledger["undated"], "_bytes": total}


# ---------------------------------------------------------------------
# reading and reusing
# ---------------------------------------------------------------------

def load(root: Path, slice_id_: str) -> Slice:
    path = snapshots_dir(root) / slice_id_
    mpath = path / MANIFEST
    if not mpath.is_file():
        raise LabError(
            f"no slice {slice_id_!r} under {snapshots_dir(root)} — take "
            f"one with `asterism lab snapshot --scope <problem>`")
    return Slice(slice_id_, path,
                 json.loads(mpath.read_text(encoding="utf-8")))


def ensure_slice(root: Path, *, workspace: Path, problem: str,
                 cutoff: "str | None" = None) -> Slice:
    """The slice a `rewind:` block names, taken only if it is not there.

    A rewound slice is reproducible — same problem, same instant, same
    scene — so re-taking it would be a second copy of the same bytes
    under a name that already exists. An UN-rewound slice is not: it is
    named for the moment it was taken, so this always takes a new one.
    """
    if cutoff:
        want = slice_id(problem, cutoff=cutoff)
        if (snapshots_dir(root) / want / MANIFEST).is_file():
            return load(root, want)
    return take(workspace, root, problem=problem, cutoff=cutoff)


def list_slices(root: Path) -> "list[Slice]":
    base = snapshots_dir(root)
    if not base.is_dir():
        return []
    out: "list[Slice]" = []
    for d in sorted(base.iterdir()):
        if (d / MANIFEST).is_file():
            out.append(load(root, d.name))
    return out
