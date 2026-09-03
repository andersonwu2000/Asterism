"""`asterism carry export` / `asterism carry import` — moving ONE
problem's complete state between workspaces.

The shuttle between the flagship, the local 32G box and the SP7 node
had been done by hand four times when this was written, and twice it
left orphan rows behind: a `strategies` row keyed on `goal_id`, a
`dead_attempts` row keyed on a polymorphic `target_kind`/`target_id` —
tables with no `problem` column that a hand-written prune cannot see.
`Tooling/state/carry.py` answers "which rows are the problem's" from
the schema instead; this module owns the two ends of the move: the
bundle on disk, and the target workspace it lands in.

A bundle is a directory:

    carry.db        a `VACUUM INTO` snapshot pruned to P's rows, with
                    `library_*` and `projects` carried whole (global
                    assets, not one problem's)
    files.tar.gz    P's problem directory + the papers bound to P, at
                    workspace-relative paths
    manifest.json   source HEAD, schema user_version, per-table row
                    counts, goal id range, what the tarball holds

Import REPLACES: P's rows go, the bundle's arrive, every other
problem is untouched. Both directions refuse while a daemon holds
`daemon.pid` — a DB being written mid-tick is not a thing to snapshot
or rewrite (CLAUDE.md rule 3).

Rule 10 (DB and files move together) is kept the way `reset` keeps it,
not by routing a tar extraction through `proof_store`: rows and files
land inside one command, in the order that leaves no window
(`recovery.sweep_orphan_proof_files` deletes an untracked proof file
with no DB row at the next daemon start, so the rows go first), and the
command closes by running the real `asterism drift-check` over P —
`proof_store.inventory` is the oracle either way, and here it is asked
rather than assumed.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ...state import carry, db, project_docs, projects as projects_mod
from ...state import satellites
from .run import _utc_log_stamp, daemon_status

#: Run-scoped scratch the tarball leaves behind. Both are keyed by an
#: id (`.presearch/g<goal>.md`, `.drafts/backward_g<goal>.md` AND
#: `.drafts/strategist_plan_g<GROUP>.md` — the same `g` prefix meaning
#: two different id spaces in one directory), and the satellite registry
#: already declares dropping them sanctioned: they are swept at every
#: reset precisely because an id means something else in the next
#: workspace. Carrying them is incident #167 with extra steps.
SCRATCH_DIRS = (".presearch", ".drafts")

#: Never part of a paper (the map spawn's sandbox).
PAPER_EXCLUDE = ".index_attempt"

RC_OK, RC_USAGE, RC_SCHEMA, RC_DAEMON, RC_UNCLEAN = 0, 1, 2, 3, 4


# ---------------------------------------------------------------------
# shared
# ---------------------------------------------------------------------

def _daemon_refusal(workspace: Path, verb: str) -> "str | None":
    st = daemon_status(workspace)
    if not st.get("running"):
        return None
    return (f"a daemon (pid {st.get('pid')}) is working this workspace — "
            f"carry {verb} needs the DB still. Stop it first: "
            f"`asterism daemon stop`.")


def _head_sha(workspace: Path) -> "str | None":
    try:
        out = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def _snapshot(src: Path, dest: Path) -> None:
    """`VACUUM INTO` — a consistent, compact copy that never touches the
    source. autocommit, because VACUUM cannot run inside a transaction."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    conn = sqlite3.connect(str(src), isolation_level=None)
    try:
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _project_of(conn: sqlite3.Connection, problem: str) -> str:
    return (projects_mod.project_of(conn, problem)
            or problem.split(".", 1)[0])


def _drift_counts(conn: sqlite3.Connection, workspace: Path,
                  problem: str) -> "dict[str, int]":
    """The two drift layers `asterism drift-check` reports, as counts.

    Taken at export and re-taken after import so the import can answer
    the only question that is carry's business: did the move INTRODUCE
    a finding, or carry one the problem already had? A problem with a
    live tree-sweep finding is still a problem worth moving, and a tool
    that called every such move a failure would be one nobody reads."""
    from ...state import consistency, proof_store
    rep = proof_store.inventory(conn, workspace, scope=problem)
    sweep = consistency.consistency_sweep(conn, scope=problem)
    return {
        "orphan_files": len(rep.orphan_files),
        "missing_files": len(rep.missing_files),
        "proved_with_sorry": len(rep.proved_with_sorry),
        "tree_findings": sum(len(v) for v in sweep.values()),
    }


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n} B"


# ---------------------------------------------------------------------
# the files a problem owns
# ---------------------------------------------------------------------

def _paper_dirs(workspace: Path, conn: sqlite3.Connection,
                problem: str) -> "list[Path]":
    """The paper directories bound to P. Every bind chokepoint copies
    the paper onto the target project's shelf first, so the project
    lookup is the right one — but a pre-migration row may only exist
    under another project, and a citation the problem carries is worth
    more than tidiness, so fall back to the workspace-wide search."""
    from ...papers import shelf
    project = _project_of(conn, problem)
    out: "list[Path]" = []
    for row in conn.execute(
            "SELECT paper_id FROM problem_papers WHERE problem = ?"
            " ORDER BY paper_id", (problem,)):
        pid = str(row[0])
        try:
            pdir = (shelf.paper_dir(workspace, pid, project=project)
                    or shelf.paper_dir(workspace, pid))
        except (ValueError, OSError):
            pdir = None
        if pdir is not None and pdir.is_dir():
            out.append(pdir)
    return out


def _members(workspace: Path, conn: sqlite3.Connection,
             problem: str) -> "tuple[list[tuple[Path, str]], list[str]]":
    """`[(absolute path, workspace-relative arcname)]` plus the human
    list of what was deliberately left out."""
    pdir = db.problem_dir(workspace, problem)
    project = _project_of(conn, problem)
    try:
        docs_root = project_docs.root(workspace, project)
    except ValueError:
        docs_root = None
    # A single-segment Project's docs root sits INSIDE its problem
    # directory (satellites.py:148). Walking the problem dir blind would
    # ship every unbound paper and every private user document in the
    # project; the papers P actually cites are added back below.
    nested_docs = (docs_root is not None and docs_root.exists()
                   and docs_root.resolve() != pdir.resolve()
                   and str(docs_root.resolve()).startswith(
                       str(pdir.resolve())))

    members: "list[tuple[Path, str]]" = []
    skipped: "list[str]" = []

    def walk(root: Path, *, exclude_names=()) -> None:
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            rel_parts = path.relative_to(root).parts
            if any(p in exclude_names for p in rel_parts):
                continue
            if nested_docs and docs_root is not None:
                try:
                    path.relative_to(docs_root)
                    continue
                except ValueError:
                    pass
            members.append((path, path.relative_to(workspace).as_posix()))

    if pdir.exists():
        for name in SCRATCH_DIRS:
            if (pdir / name).exists():
                skipped.append(f"{name}/")
        walk(pdir, exclude_names=SCRATCH_DIRS)
    if nested_docs:
        skipped.append(f"{project_docs.ROOT_DIRNAME}/ "
                       f"(only the papers bound to {problem} travel)")
    papers = _paper_dirs(workspace, conn, problem)
    for p in papers:
        walk(p, exclude_names=(PAPER_EXCLUDE,))
    return members, skipped


# ---------------------------------------------------------------------
# export
# ---------------------------------------------------------------------

def cmd_carry_export(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    problem = args.problem
    out = Path(args.out)
    refusal = _daemon_refusal(workspace, "export")
    if refusal:
        print(f"FAIL: {refusal}", file=sys.stderr)
        return RC_DAEMON

    src_db = workspace / "asterism.db"
    if not src_db.exists():
        print(f"FAIL: no asterism.db in {workspace}", file=sys.stderr)
        return RC_USAGE
    live = _open(src_db)
    try:
        if live.execute("SELECT 1 FROM problems WHERE name = ?",
                        (problem,)).fetchone() is None:
            print(f"FAIL: unknown problem {problem!r} — `asterism status "
                  f"{problem}` lists what this workspace holds",
                  file=sys.stderr)
            return RC_USAGE
        carry.assert_classified(live)
        project = _project_of(live, problem)
        members, skipped = _members(workspace, live, problem)
        drift = _drift_counts(live, workspace, problem)
    finally:
        live.close()

    out.mkdir(parents=True, exist_ok=True)
    bundle_db = out / "carry.db"
    _snapshot(src_db, bundle_db)
    snap = _open(bundle_db)
    try:
        kept = carry.prune_to_problem(snap, problem)
        left = carry.orphans(snap)
        if left:
            print("FAIL: the pruned snapshot has orphan rows — the prune "
                  "missed a goal-keyed table:", file=sys.stderr)
            for label, n in sorted(left.items()):
                print(f"  ? {label}: {n}", file=sys.stderr)
            return RC_UNCLEAN
        bad = carry.foreign_key_findings(snap)
        if bad:
            print("FAIL: the pruned snapshot fails foreign_key_check:",
                  file=sys.stderr)
            for row in bad[:20]:
                print(f"  ? {row}", file=sys.stderr)
            return RC_UNCLEAN
        version = int(snap.execute("PRAGMA user_version").fetchone()[0])
        rng = snap.execute("SELECT MIN(id), MAX(id) FROM goals"
                           " WHERE problem = ?", (problem,)).fetchone()
        snap.execute("VACUUM")
    finally:
        snap.close()

    tarball = out / "files.tar.gz"
    total = 0
    with tarfile.open(tarball, "w:gz") as tf:
        for path, arc in members:
            tf.add(str(path), arcname=arc)
            total += path.stat().st_size

    manifest = {
        "tool": "asterism carry",
        "format": 1,
        "problem": problem,
        "project": project,
        "exported_at": db.now(),
        "source_workspace": str(workspace),
        "source_head": _head_sha(workspace),
        "schema_user_version": version,
        "row_counts": {t: n for t, n in sorted(kept.items()) if n},
        "goal_id_range": [rng[0], rng[1]] if rng and rng[0] is not None
                         else None,
        "files": {"entries": len(members), "bytes": total,
                  "excluded": skipped},
        "drift_at_export": drift,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"OK: carry export {problem} -> {out}")
    print(f"  schema      v{version}")
    print(f"  rows        {sum(manifest['row_counts'].values())} in "
          f"{len(manifest['row_counts'])} table(s)")
    if manifest["goal_id_range"]:
        lo, hi = manifest["goal_id_range"]
        print(f"  goal ids    {lo}..{hi}")
    print(f"  files       {len(members)} entr(ies), {_fmt_bytes(total)}")
    for note in skipped:
        print(f"  excluded    {note}")
    return RC_OK


# ---------------------------------------------------------------------
# import — the plan
# ---------------------------------------------------------------------

@dataclass
class Plan:
    problem: str
    manifest: dict
    bundle: Path
    workspace: Path
    work_db: Path
    target_version: int
    bundle_version: int
    migrated: bool = False
    kinds: dict = field(default_factory=dict)
    remap: "carry.Remap" = field(default_factory=carry.Remap)
    refs_touched: list = field(default_factory=list)
    deletes: dict = field(default_factory=dict)
    inserts: dict = field(default_factory=dict)
    members: list = field(default_factory=list)
    stamp: str = ""

    @property
    def backup_dir(self) -> Path:
        return (self.workspace / ".asterism" / "backups"
                / f"carry_{self.problem}_{self.stamp}")

    @property
    def backup_db(self) -> Path:
        # NOT `with_suffix`: a problem name has dots in it, so pathlib
        # reads `carry_Erdos.p1_<stamp>` as stem `carry_Erdos` plus a
        # suffix, and the backup of every Erdos problem lands on one
        # file called `carry_Erdos.db`.
        return self.backup_dir.parent / (self.backup_dir.name + ".db")


def _build_plan(workspace: Path, bundle: Path, scratch: Path,
                *, want_problem: "str | None",
                allow_migrate: bool) -> "Plan | int":
    manifest_path = bundle / "manifest.json"
    if not manifest_path.exists() or not (bundle / "carry.db").exists():
        print(f"FAIL: {bundle} is not a carry bundle (needs manifest.json "
              f"+ carry.db + files.tar.gz)", file=sys.stderr)
        return RC_USAGE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problem = str(manifest.get("problem") or "")
    if want_problem and want_problem != problem:
        print(f"FAIL: this bundle carries {problem!r}, not "
              f"{want_problem!r}. `--problem` names the bundle's problem "
              f"as a check; carry does not rename a problem on import "
              f"(its lean paths and module names are built from the "
              f"name). Re-export from the source under the name you "
              f"want, or drop `--problem`.", file=sys.stderr)
        return RC_USAGE

    target_db = workspace / "asterism.db"
    if not target_db.exists() or _open(target_db).execute(
            "SELECT 1 FROM sqlite_master WHERE type='table'"
            " AND name='goals'").fetchone() is None:
        # An empty workspace: minting the schema is creation, not a
        # migration, and carry into a fresh box is the whole point.
        fresh = db.connect(target_db)
        db.init_schema(fresh)
        fresh.close()
    # Deliberately NOT `db.connect`: that auto-migrates a stale DB, and
    # a --dry-run that silently upgraded the workspace's schema would be
    # the one thing a dry run must never do. A behind target is REPORTED
    # by the version check below instead.
    tconn = _open(target_db)
    target_version = int(
        tconn.execute("PRAGMA user_version").fetchone()[0])

    work_db = scratch / "carry.db"
    shutil.copy2(bundle / "carry.db", work_db)
    wconn = _open(work_db)
    bundle_version = int(
        wconn.execute("PRAGMA user_version").fetchone()[0])
    migrated = False
    if bundle_version != target_version:
        if not allow_migrate:
            wconn.close()
            tconn.close()
            print(f"FAIL: bundle schema is v{bundle_version}, this "
                  f"workspace is v{target_version}. Re-run with "
                  f"`--allow-migrate` to migrate a COPY of carry.db "
                  f"first (the bundle itself is never written), or "
                  f"bring this workspace up to the bundle's version.",
                  file=sys.stderr)
            return RC_SCHEMA
        if bundle_version > target_version:
            wconn.close()
            tconn.close()
            print(f"FAIL: bundle schema v{bundle_version} is AHEAD of "
                  f"this workspace's v{target_version} — carry migrates "
                  f"forward only. Update this workspace's code and let "
                  f"it migrate its own DB, then import.", file=sys.stderr)
            return RC_SCHEMA
        wconn.close()
        mig = db.connect(work_db)
        db.init_schema(mig)
        mig.close()
        wconn = _open(work_db)
        migrated = True

    plan = Plan(problem=problem, manifest=manifest, bundle=bundle,
                workspace=workspace, work_db=work_db,
                target_version=target_version,
                bundle_version=bundle_version, migrated=migrated,
                stamp=_utc_log_stamp())
    try:
        plan.kinds = carry.assert_classified(tconn)
        cols_bad = _column_mismatch(wconn, tconn, plan.kinds)
        if cols_bad:
            print("FAIL: bundle and workspace disagree on columns after "
                  "the schema check — " + "; ".join(cols_bad),
                  file=sys.stderr)
            return RC_SCHEMA
        plan.remap = carry.plan_remap(wconn, tconn, problem)
        plan.refs_touched = carry.apply_remap(wconn, plan.remap)

        src_scope = carry.scope_of(wconn, problem)
        tgt_scope = carry.scope_of(tconn, problem)
        for table, kind in sorted(plan.kinds.items()):
            if kind == carry.GLOBAL:
                continue
            where, argv = carry.belongs_to(table, tgt_scope)
            plan.deletes[table] = int(tconn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {where}",
                argv).fetchone()[0])
            where, argv = carry.belongs_to(table, src_scope)
            plan.inserts[table] = int(wconn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {where}",
                argv).fetchone()[0])
        plan.members = _tar_members(bundle / "files.tar.gz")
    finally:
        wconn.close()
        tconn.close()
    return plan


def _column_mismatch(src: sqlite3.Connection, tgt: sqlite3.Connection,
                     kinds: dict) -> "list[str]":
    out: "list[str]" = []
    for table in sorted(kinds):
        a = {r[1] for r in src.execute(f"PRAGMA table_info({table})")}
        b = {r[1] for r in tgt.execute(f"PRAGMA table_info({table})")}
        if a != b:
            out.append(f"{table}: {sorted(a ^ b)}")
    return out


def _tar_members(tarball: Path) -> "list[tarfile.TarInfo]":
    """Every member, checked for escape. A tarball is untrusted input:
    an absolute path or a `..` would write outside the workspace."""
    if not tarball.exists():
        raise ValueError(f"{tarball} missing from the bundle")
    with tarfile.open(tarball, "r:gz") as tf:
        infos = tf.getmembers()
    for info in infos:
        name = info.name.replace("\\", "/")
        if (name.startswith("/") or ".." in name.split("/")
                or not name.startswith("Problems/")
                or info.issym() or info.islnk()):
            raise ValueError(
                f"bundle tarball has an unsafe member {info.name!r} — "
                f"every entry must be a plain file under Problems/")
    return infos


# ---------------------------------------------------------------------
# import — printing the plan
# ---------------------------------------------------------------------

def _print_plan(plan: Plan, *, dry: bool) -> None:
    m = plan.manifest
    head = (m.get("source_head") or "?")[:8]
    print(f"carry import — {plan.problem}" + ("   (dry run)" if dry else ""))
    print(f"  bundle    {plan.bundle}")
    print(f"  source    HEAD {head} · schema v{plan.bundle_version}"
          f" · exported {m.get('exported_at')}")
    print(f"  target    {plan.workspace} · schema v{plan.target_version}"
          + ("  (bundle copy migrated)" if plan.migrated else ""))
    print()

    counts: "dict[str, int]" = {}
    for kind in plan.kinds.values():
        counts[kind] = counts.get(kind, 0) + 1
    print(f"  classification ({len(plan.kinds)} tables)")
    print("    " + " · ".join(
        f"{k} {counts.get(k, 0)}" for k in (
            carry.PROBLEM_KEYED, carry.GOAL_KEYED, carry.GLOBAL,
            carry.REFUSED)))
    print()

    print("  collisions")
    if plan.remap.collisions:
        for table, n in sorted(plan.remap.collisions.items()):
            print(f"    {table:<24} {n} of "
                  f"{plan.remap.considered.get(table, 0)} imported id(s) "
                  f"already used by another problem")
    else:
        print("    none — every imported id is free in this workspace")
    print()

    print("  remap")
    if plan.remap.any():
        for table, mapping in sorted(plan.remap.maps.items()):
            fresh = sorted(mapping.values(), key=str)
            span = (f"{fresh[0]}..{fresh[-1]}" if len(fresh) > 1
                    else f"{fresh[0]}")
            print(f"    {table:<24} {len(mapping)} id(s) -> {span}")
        print(f"    {'references rewritten':<24} "
              + (", ".join(plan.refs_touched) or "none"))
        strat = plan.remap.maps.get("strategies") or {}
        for old, new in sorted(strat.items()):
            print(f"    {'lean':<24} _strategy_s{old}.lean"
                  f" -> _strategy_s{new}.lean")
        grp = plan.remap.maps.get("groups") or {}
        for old, new in sorted(grp.items()):
            print(f"    {'projection':<24} .groups/{old}/ -> .groups/{new}/")
    else:
        print("    none — ids are carried unchanged")
    print()

    print("  rows")
    print(f"    {'table':<28}{'delete':>8}{'insert':>8}")
    td = ti = 0
    for table in sorted(set(plan.deletes) | set(plan.inserts)):
        d, i = plan.deletes.get(table, 0), plan.inserts.get(table, 0)
        td, ti = td + d, ti + i
        if d or i:
            print(f"    {table:<28}{d:>8}{i:>8}")
    print(f"    {'TOTAL':<28}{td:>8}{ti:>8}")
    print()

    pdir = db.problem_dir(plan.workspace, plan.problem)
    rel = pdir.relative_to(plan.workspace).as_posix()
    size = sum(i.size for i in plan.members)
    print("  files")
    if pdir.exists():
        print(f"    move      {rel} -> "
              f"{plan.backup_dir.relative_to(plan.workspace).as_posix()}/")
    else:
        print(f"    create    {rel}")
    print(f"    extract   {len(plan.members)} entr(ies), {_fmt_bytes(size)}")
    for note in plan.manifest.get("files", {}).get("excluded", []):
        print(f"    excluded  {note} — not in the bundle")
    print()

    print("  backups")
    print(f"    db        "
          f"{plan.backup_db.relative_to(plan.workspace).as_posix()}")
    print(f"    files     "
          f"{plan.backup_dir.relative_to(plan.workspace).as_posix()}/")
    print()
    if dry:
        print("  DRY RUN — nothing changed.")


# ---------------------------------------------------------------------
# import — applying it
# ---------------------------------------------------------------------

def _apply_rows(plan: Plan) -> None:
    tconn = db.connect(plan.workspace / "asterism.db")
    wconn = _open(plan.work_db)
    try:
        # Bulk restore: FKs off for the swap, then the WHOLE-file
        # `foreign_key_check` afterwards — stronger than the incremental
        # one, and the only way a delete/insert order can be right for a
        # schema where two tables point at each other.
        tconn.execute("PRAGMA foreign_keys = OFF")
        from .problems import wipe_problem_rows
        wipe_problem_rows(tconn, plan.problem)
        # `librarian_fail_counts` is a declared reset SURVIVOR, so the
        # wipe leaves it — but carry REPLACES, and a surviving row would
        # collide with the bundle's on the text PK.
        pred, argv = carry.belongs_to(
            "librarian_fail_counts",
            carry.Scope(plan.problem))
        tconn.execute(
            f"DELETE FROM librarian_fail_counts WHERE {pred}", argv)
        left = satellites.db_leftovers(tconn, plan.problem)
        if left:
            raise RuntimeError(
                f"the wipe left rows behind for {plan.problem}: {left}")

        scope = carry.scope_of(wconn, plan.problem)
        # `projects` is global: merged, never replaced. Without the
        # project row the problem's FK dangles and the problem has no
        # docs root.
        for row in wconn.execute(
                "SELECT * FROM projects WHERE name IN"
                " (SELECT project FROM problems WHERE name = ?)",
                (plan.problem,)):
            cols = row.keys()
            tconn.execute(
                f"INSERT OR IGNORE INTO projects ({','.join(cols)})"
                f" VALUES ({','.join('?' * len(cols))})", tuple(row))
        for table, kind in sorted(plan.kinds.items()):
            if kind == carry.GLOBAL:
                continue
            where, argv = carry.belongs_to(table, scope)
            rows = wconn.execute(
                f"SELECT * FROM {table} WHERE {where}", argv).fetchall()
            if not rows:
                continue
            cols = rows[0].keys()
            tconn.executemany(
                f"INSERT INTO {table} ({','.join(cols)})"
                f" VALUES ({','.join('?' * len(cols))})",
                [tuple(r) for r in rows])
        tconn.commit()
    finally:
        wconn.close()
        tconn.close()


def _apply_files(plan: Plan) -> None:
    pdir = db.problem_dir(plan.workspace, plan.problem)
    if pdir.exists():
        if plan.backup_dir.exists():
            # `shutil.move` onto an existing directory moves the source
            # INSIDE it — the displaced problem would nest one level
            # deeper on every retry, silently.
            raise RuntimeError(
                f"{plan.backup_dir} already exists — move it aside; "
                f"carry never writes into an existing backup")
        plan.backup_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pdir), str(plan.backup_dir))
    pdir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(plan.bundle / "files.tar.gz", "r:gz") as tf:
        # `filter="data"` is the second fence (the first is
        # `_tar_members`): no absolute paths, no links, no escapes.
        tf.extractall(str(plan.workspace), members=plan.members,
                      filter="data")
    _follow_remap_on_disk(plan, pdir)


def _follow_remap_on_disk(plan: Plan, pdir: Path) -> None:
    """The two id kinds that live in a NAME, not only in a row.

    Half of this would be worse than none: `recovery.sweep_orphan_proof_
    files` deletes an untracked `_strategy_s*.lean` with no matching DB
    row at the next daemon start, and `prune.reconcile_proved_goals`
    rewrites every proved goal's alias from the DB's current strategy
    id. A file left at the old name loses the proof; a row left at the
    old id loses the file."""
    for old, new in sorted((plan.remap.maps.get("groups") or {}).items()):
        src = pdir / ".groups" / str(old)
        if src.is_dir():
            dst = pdir / ".groups" / str(new)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))

    strat = plan.remap.maps.get("strategies") or {}
    if not strat:
        return
    ns = f"Problems.{plan.problem}"
    for old, new in sorted(strat.items()):
        src = pdir / "proofs" / f"_strategy_s{old}.lean"
        if src.exists():
            src.replace(pdir / "proofs" / f"_strategy_s{new}.lean")
    subs = []
    for old, new in strat.items():
        subs += [
            # module name / import line, and the file name inside text
            (re.compile(rf"_strategy_s{old}(?![0-9])"),
             f"_strategy_s{new}"),
            # `def <slug> := @Problems.<p>.s<id>` — fully qualified, so
            # it can never collide with an ordinary `s1` in a proof
            (re.compile(rf"@{re.escape(ns)}\.s{old}(?![0-9A-Za-z_])"),
             f"@{ns}.s{new}"),
            # the strategy file's own declaration head
            (re.compile(rf"\b(theorem|lemma|def|abbrev|instance)"
                        rf"\s+s{old}(?![0-9A-Za-z_])"),
             rf"\1 s{new}"),
        ]
    for lean in sorted(pdir.rglob("*.lean")):
        text = lean.read_text(encoding="utf-8", errors="surrogateescape")
        new_text = text
        for pattern, repl in subs:
            new_text = pattern.sub(repl, new_text)
        if new_text != text:
            lean.write_text(new_text, encoding="utf-8",
                            errors="surrogateescape")


def _post_checks(plan: Plan, baseline: "set[tuple]") -> int:
    from ...state import tree
    conn = db.connect(plan.workspace / "asterism.db")
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        # Delta against the pre-import baseline: a workspace may already
        # carry findings that are none of this import's business, and an
        # auditor that indicts them is one nobody reads (the 1,063-row
        # lesson in state/satellites.py).
        found = set(carry.foreign_key_findings(conn)) - baseline
        if found:
            print("  [FAIL] foreign_key_check gained findings:")
            for row in sorted(found)[:20]:
                print(f"    ? {row}")
            return RC_UNCLEAN
        print("  [  OK] foreign_key_check clean "
              "(library_decls cross-problem rows excepted)")
        # TREE.md renders the rows, and its `[gNNNN]` labels are exactly
        # the ids a remap just moved.
        tree.write(conn, plan.workspace, plan.problem)
        now = _drift_counts(conn, plan.workspace, plan.problem)
    finally:
        conn.close()

    from .diagnose import cmd_drift_check
    rc = cmd_drift_check(argparse.Namespace(scope=plan.problem))
    if rc == 0:
        return RC_OK
    was = plan.manifest.get("drift_at_export") or {}
    worse = {k: (int(was.get(k, 0)), v)
             for k, v in now.items() if v > int(was.get(k, 0))}
    if worse:
        print("  [FAIL] the import INTRODUCED drift:")
        for key, (before, after) in sorted(worse.items()):
            print(f"    ? {key}: {before} at export -> {after} here")
        print(f"    the target's pre-import state is in "
              f"{plan.backup_db.name} + {plan.backup_dir.name}/")
        return RC_UNCLEAN
    print("  [ NOTE] drift-check is not clean, but every finding was "
          "already there at export — the problem's own state travelled "
          "faithfully. Nothing here was introduced by the move.")
    return RC_OK


def cmd_carry_import(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    bundle = Path(args.bundle)
    dry = bool(getattr(args, "dry_run", False))
    refusal = _daemon_refusal(workspace, "import")
    if refusal:
        print(f"FAIL: {refusal}", file=sys.stderr)
        return RC_DAEMON

    scratch = Path(tempfile.mkdtemp(prefix="asterism-carry-"))
    try:
        try:
            plan = _build_plan(
                workspace, bundle, scratch,
                want_problem=getattr(args, "problem", None),
                allow_migrate=bool(getattr(args, "allow_migrate", False)))
        except ValueError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return RC_USAGE
        if isinstance(plan, int):
            return plan
        _print_plan(plan, dry=dry)
        if dry:
            return RC_OK

        target_db = workspace / "asterism.db"
        base_conn = _open(target_db)
        try:
            baseline = set(carry.foreign_key_findings(base_conn))
        finally:
            base_conn.close()
        _snapshot(target_db, plan.backup_db)
        print(f"  backed up target DB -> "
              f"{plan.backup_db.relative_to(workspace).as_posix()}")
        try:
            # Rows BEFORE files: a crash between the two then leaves
            # rows whose file is missing, which `proof_store.inventory`
            # names and nothing destroys. The other order leaves
            # untracked proof files with no row, which
            # `recovery.sweep_orphan_proof_files` DELETES at the next
            # daemon start — the same half-state, one of them lossy.
            _apply_rows(plan)
            _apply_files(plan)
        except Exception as exc:
            print(f"FAIL: the import died part-way ({exc}). Nothing is "
                  f"lost — restore with:\n"
                  f"  copy {plan.backup_db} over asterism.db\n"
                  f"  move {plan.backup_dir} back to "
                  f"{db.problem_dir(workspace, plan.problem)}\n"
                  f"then fix the cause and re-run.", file=sys.stderr)
            raise
        print(f"OK: carry import {plan.problem}")
        return _post_checks(plan, baseline)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def cmd_carry(args: argparse.Namespace) -> int:
    action = getattr(args, "carry_action", None)
    if action == "export":
        return cmd_carry_export(args)
    if action == "import":
        return cmd_carry_import(args)
    print(f"FAIL: unknown carry action {action!r}", file=sys.stderr)
    return RC_USAGE
