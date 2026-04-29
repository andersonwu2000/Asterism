"""CLI: asterism init <p> | asterism run [--once].

See architecture.md §9.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import db, dispatcher, manifest


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
        root_lean.write_text(
            f"import Mathlib\n\n"
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

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
