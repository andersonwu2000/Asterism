"""`asterism papers-migrate` — move a workspace-global `Papers/` shelf
into the Project document roots (HID §3.9).

One-shot, per node (each SP7 store is its own workspace, so each runs it
once). It is a MOVE of local data that git never tracked, so the whole
thing is written to be re-runnable and to be inspectable first:

  bound     `problem_papers` says which problems cite the paper; each of
            those problems sits on a Project, and the paper is copied
            onto every one of them before the source is removed. Two
            Projects citing one paper is two copies under one id (§3.9)
            — a decision the shelf itself already makes.
  unbound   NOT guessed. The whole directory moves to
            `.asterism/backups/papers_unfiled_<UTC date>/` and is
            printed: 22 of the 40 papers on the live shelf lost their
            binding to a `reset` (which deletes bindings and leaves the
            directory), and inventing a Project for those would file
            someone's literature under a heading nobody chose. A person
            who wants one back uploads it into the Project they meant.
  residue   `Papers/asterism.db` — a zero-table sqlite file minted by a
            mis-derived workspace in the paper_index spawn (fixed at the
            source; see `papers/index.py`). Removed only when
            `sqlite_master` really is empty: a file with tables in it is
            somebody's database, whatever it is doing there.

An empty `Papers/` is removed at the end. A second run finds nothing to
do and says so — that is what makes it safe to run after a partial one.
"""
from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import shelf
from ..state import projects as _projects

#: The retired root. Named here and nowhere else in this module.
LEGACY_DIRNAME = "Papers"


@dataclass
class Plan:
    """What a run would do, or did. Printed either way — a dry run and a
    real one differ in whether the filesystem changed, never in what the
    operator is told."""
    #: pid -> the Projects it is copied onto (sorted, may be several)
    filed: "dict[str, list[str]]" = field(default_factory=dict)
    #: pid -> its source directory, for papers nothing cites
    unfiled: "dict[str, Path]" = field(default_factory=dict)
    #: pid -> how an unfiled paper READS (title, else source filename).
    #: Captured while planning: the report is printed after the move, and
    #: by then the meta.json it came from is somewhere else.
    unfiled_names: "dict[str, str]" = field(default_factory=dict)
    #: entries under `Papers/` that are not shelf slots at all
    strays: "list[Path]" = field(default_factory=list)
    #: the zero-table sqlite residue, when it is there and really empty
    residue: "Path | None" = None
    #: a non-empty `Papers/asterism.db` — reported, never touched
    residue_kept: "Path | None" = None
    #: where unfiled papers go
    backup_dir: "Path | None" = None
    #: True when `Papers/` itself is gone (or was never there)
    root_removed: bool = False

    @property
    def empty(self) -> bool:
        return not (self.filed or self.unfiled or self.strays
                    or self.residue)


#: A sqlite database is up to four files. The residue was minted by a
#: `db.connect`, which sets `journal_mode = WAL`, so it has sidecars —
#: they belong to it and go with it.
_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _has_tables(path: Path) -> bool:
    """Whether a sqlite file holds anything at all. A file we cannot
    open counts as holding something — the honest answer to "is this
    safe to delete?" for a file this tool did not create.

    `immutable=1`, not a plain read-only open: the residue is in WAL
    mode, and reading a WAL database normally CREATES its `-shm` file.
    A tool whose dry run writes into the directory it is inspecting is
    not a dry run. The cost of immutable is that a commit living only in
    an uncheckpointed `-wal` is invisible here, so a non-empty `-wal`
    counts as content on its own.
    """
    wal = path.with_name(path.name + "-wal")
    try:
        if wal.is_file() and wal.stat().st_size > 0:
            return True
    except OSError:
        return True
    try:
        conn = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)
    except sqlite3.Error:
        return True
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM sqlite_master").fetchone()[0] > 0
    except sqlite3.Error:
        return True
    finally:
        conn.close()


def _bindings(workspace: Path) -> "dict[str, list[str]]":
    """pid -> the Projects whose problems cite it, sorted and unique.

    Read-only, and a workspace with no database has no bindings at all —
    every paper is then unfiled, which is the honest answer rather than
    a crash."""
    db_path = workspace / "asterism.db"
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        out: "dict[str, set[str]]" = {}
        for r in conn.execute(
                "SELECT pp.paper_id AS pid, pp.problem AS problem,"
                "       p.project AS project"
                "  FROM problem_papers pp"
                "  LEFT JOIN problems p ON p.name = pp.problem"):
            pid = str(r["pid"])
            project = r["project"] or str(r["problem"]).split(".", 1)[0]
            if not _projects.NAME_RE.fullmatch(str(project)):
                # A problem whose name is not a legal Project segment
                # cannot address a docs root; treat it as unfiled rather
                # than writing `Problems/<junk>/_docs/`.
                continue
            out.setdefault(pid, set()).add(str(project))
        return {pid: sorted(v) for pid, v in out.items()}
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


def plan(workspace: Path) -> Plan:
    """What a run would do. Pure read — nothing here touches disk."""
    p = Plan()
    root = Path(workspace) / LEGACY_DIRNAME
    db_residue = root / "asterism.db"
    sidecars = {db_residue.with_name(db_residue.name + suf)
                for suf in _SIDECAR_SUFFIXES}
    if db_residue.is_file():
        if _has_tables(db_residue):
            p.residue_kept = db_residue
        else:
            p.residue = db_residue
    if not root.is_dir():
        p.root_removed = True
        return p
    bound = _bindings(workspace)
    for entry in sorted(root.iterdir()):
        # The residue and its sqlite sidecars are one object, reported
        # once — never as loose "strays" a reader would go looking for.
        if entry == db_residue or entry in sidecars:
            continue
        if not entry.is_dir():
            p.strays.append(entry)
            continue
        if not (entry / "meta.json").is_file():
            p.strays.append(entry)
            continue
        projects = bound.get(entry.name)
        if projects:
            p.filed[entry.name] = projects
        else:
            p.unfiled[entry.name] = entry
            p.unfiled_names[entry.name] = _display_name(entry)
    if p.unfiled:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        p.backup_dir = (Path(workspace) / ".asterism" / "backups"
                        / f"papers_unfiled_{stamp}")
    return p


def _display_name(pdir: Path) -> str:
    """How a paper reads to a person: its owner-set title, else the
    filename it came in as."""
    import json
    try:
        meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "?"
    return str(meta.get("title") or meta.get("source_name") or "?")


def _area_of(pdir: Path) -> str:
    """Which sub-root a legacy slot belongs in — the same rule the shelf
    applies to a new one, read off its own `meta.json`."""
    import json
    try:
        meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return shelf.area_for(None)
    return shelf.area_for(meta.get("added_by"))


def run(workspace: Path, *, dry_run: bool = False) -> Plan:
    """Do it (or say what it would do). Returns the plan either way.

    Order matters: every copy lands before any source is removed, so an
    interruption leaves the paper readable in BOTH places rather than in
    neither. That also makes the second run a no-op — the sources it
    already moved are gone, and the ones it did not are still there."""
    workspace = Path(workspace)
    p = plan(workspace)
    if dry_run:
        return p
    root = workspace / LEGACY_DIRNAME
    for pid, projects in p.filed.items():
        src = root / pid
        area = _area_of(src)
        for project in projects:
            dst = shelf.papers_root(workspace, project, area) / pid
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst)
        shutil.rmtree(src)
    if p.unfiled and p.backup_dir is not None:
        p.backup_dir.mkdir(parents=True, exist_ok=True)
        for pid, src in p.unfiled.items():
            dst = p.backup_dir / pid
            if dst.exists():
                shutil.rmtree(src)
            else:
                shutil.move(str(src), str(dst))
    if p.residue is not None:
        p.residue.unlink()
        for suf in _SIDECAR_SUFFIXES:
            sidecar = p.residue.with_name(p.residue.name + suf)
            if sidecar.exists():
                sidecar.unlink()
    # Strays are LEFT: this tool moves papers, and a folder nobody
    # shelved is somebody's, whatever it is doing here. `Papers/` then
    # survives to hold them, which is the honest outcome.
    if root.is_dir() and not any(root.iterdir()):
        root.rmdir()
    p.root_removed = not root.exists()
    return p


def render(p: Plan, *, dry_run: bool) -> "list[str]":
    """The report, one line per fact. Same shape for both modes; the
    verb is the only thing that changes."""
    verb = "would file" if dry_run else "filed"
    out: "list[str]" = []
    for pid, projects in sorted(p.filed.items()):
        out.append(f"[papers-migrate] {verb} {pid} -> "
                   + ", ".join(projects))
    if p.unfiled:
        where = p.backup_dir.as_posix() if p.backup_dir else "(backups)"
        out.append(f"[papers-migrate] {len(p.unfiled)} paper(s) cited by "
                   f"no problem — {'would move' if dry_run else 'moved'} "
                   f"to {where}; upload one from Documents to bring it "
                   f"back:")
        for pid in sorted(p.unfiled):
            out.append(f"  {pid}  {p.unfiled_names.get(pid, '?')}")
    for stray in p.strays:
        out.append(f"[papers-migrate] left {stray.name} — not a shelf "
                   f"slot (no meta.json)")
    if p.residue is not None:
        out.append(f"[papers-migrate] "
                   f"{'would remove' if dry_run else 'removed'} "
                   f"{p.residue.as_posix()} (0 tables)")
    if p.residue_kept is not None:
        out.append(f"[papers-migrate] LEFT {p.residue_kept.as_posix()} — "
                   f"it has tables; look at it before deleting it")
    if p.empty:
        out.append("[papers-migrate] nothing to do — no legacy shelf "
                   "left in this workspace")
    return out
