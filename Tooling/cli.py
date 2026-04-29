"""CLI: asterism init <p> | asterism run [--once].

See architecture.md §9.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import db, dispatcher, manifest, prune


def cmd_init(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    problem = args.problem
    pdir = workspace / "Problems" / problem
    mfst_path = pdir / "Manifest.md"
    if not mfst_path.exists():
        print(f"FAIL: {mfst_path} not found", file=sys.stderr)
        return 1

    mfst = manifest.parse(mfst_path)
    if not mfst.statement:
        print(f"FAIL: Manifest.md missing ## Statement section", file=sys.stderr)
        return 1

    proofs_dir = pdir / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    root_lean = pdir / "Root.lean"
    if not root_lean.exists():
        defs_import = (
            f"import Problems.{problem}.Defs\n"
            if (pdir / "Defs.lean").exists() else ""
        )
        root_lean.write_text(
            f"import Mathlib\n{defs_import}\n"
            f"namespace Problems.{problem}\n\n"
            f"theorem main : {mfst.statement} := by sorry\n\n"
            f"end Problems.{problem}\n",
            encoding="utf-8",
        )

    conn = db.connect()
    db.init_schema(conn)

    existing = conn.execute(
        "SELECT 1 FROM problems WHERE name = ?", (problem,)
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
            (problem, str(mfst_path.relative_to(workspace).as_posix()), db.now()),
        )

    existing_goal = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND slug = 'main'",
        (problem,),
    ).fetchone()
    if existing_goal is None:
        rel_root = (pdir / "Root.lean").relative_to(workspace).as_posix()
        gid = db.insert_goal(
            conn, problem=problem, slug="main",
            lean_path=rel_root, statement=mfst.statement,
            difficulty=mfst.difficulty, origin="root", depth=0,
        )
        print(f"OK: init {problem}, root goal id={gid}")
    else:
        print(f"OK: {problem} already initialized (goal id={existing_goal['id']})")
    conn.commit()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    rc = dispatcher.run(workspace, once=getattr(args, "once", False))
    return rc


def cmd_prune(args: argparse.Namespace) -> int:
    """Manual fallback: GC orphan lean files in proofs/. Auto-invoked by
    `run` on success; this CLI exists for partial state (user killed
    daemon mid-run / run hit budget without proving root)."""
    workspace = Path.cwd()
    conn = db.connect()
    if args.problem:
        problems = [args.problem]
    else:
        problems = [r["name"] for r in conn.execute("SELECT name FROM problems")]

    total_removed = 0
    for p in problems:
        # Reconcile first to fix any file/DB drift, then prune orphans.
        # Skip reconcile under --dry-run since reconcile mutates files.
        if not args.dry_run:
            repaired = prune.reconcile_proved_goals(conn, workspace, p)
            if repaired:
                print(f"[reconcile] {p}: repaired {len(repaired)} drifted files")
        removed = prune.prune_problem(conn, workspace, p, dry_run=args.dry_run)
        total_removed += len(removed)
        verb = "would remove" if args.dry_run else "removed"
        if removed:
            print(f"[prune] {p}: {verb} {len(removed)} orphan files")
            for f in removed:
                print(f"  {f.relative_to(workspace).as_posix()}")
        else:
            print(f"[prune] {p}: nothing to remove "
                  f"(root not proved, or already clean)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asterism")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="initialize a Problem")
    p_init.add_argument("problem", help="problem name (Problems/<problem>/)")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="run dispatcher")
    p_run.add_argument("--once", action="store_true",
                       help="exit when queue empties")
    p_run.set_defaults(func=cmd_run)

    p_prune = sub.add_parser(
        "prune",
        help="GC orphan lean files in proofs/ (auto-runs on successful run)",
    )
    p_prune.add_argument("problem", nargs="?",
                         help="optional; default = all problems")
    p_prune.add_argument("--dry-run", action="store_true",
                         help="list files without deleting")
    p_prune.set_defaults(func=cmd_prune)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
