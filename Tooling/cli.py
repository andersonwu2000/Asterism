"""Asterism CLI (P1).

Entry point: python -m Tooling.cli <subcommand> [args]

Subcommands:
  init  --problem <name>
  goal  add  --problem P --slug S --kind K --leaf-strategy FILE
  goal  show <GOAL_ID>
  run   [--once|--daemon]
  db    recover
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Tooling.commit import CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.scheduler import Reactor, ReactorConfig

_DEFAULT_DB = Path("asterism.db")
_DEFAULT_BASE = Path(".")

_META_TEMPLATE = """\
# META

## Axioms

All proved theorems in this problem must reduce to (and only to) the three
foundational axioms accepted by Mathlib / Lean 4:

  - `propext`          - propositional extensionality
  - `Quot.sound`       - quotient soundness
  - `Classical.choice` - classical (non-constructive) choice

Verify with `#print axioms <theorem_name>` after each proof.

## Goals

(Populated automatically as goals are added via `asterism goal add`.)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────
# init
# ──────────────────────────────────────────────────────────────


def cmd_init(args: Any, base_dir: Path | None = None) -> None:
    """Create Problems/<name>/{META.md, Defs.lean, Root.lean}."""
    base = base_dir or _DEFAULT_BASE
    prob_dir = base / "Problems" / args.problem
    prob_dir.mkdir(parents=True, exist_ok=True)

    meta = prob_dir / "META.md"
    if not meta.exists():
        meta.write_text(_META_TEMPLATE, encoding="utf-8")

    defs = prob_dir / "Defs.lean"
    if not defs.exists():
        defs.write_text(f"-- Defs.lean: shared definitions for problem {args.problem}\n",
                        encoding="utf-8")

    root = prob_dir / "Root.lean"
    if not root.exists():
        root.write_text(f"-- Root.lean: root goal import for problem {args.problem}\n",
                        encoding="utf-8")

    print(f"Initialized problem '{args.problem}'")
    print(f"  {meta}")
    print(f"  {defs}")
    print(f"  {root}")


# ──────────────────────────────────────────────────────────────
# goal add
# ──────────────────────────────────────────────────────────────


def cmd_goal_add(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """Insert root Goal + leaf Strategy, mv file, enqueue Builder task.

    Two-phase commit protocol via CommitWriter ensures that a crash at any
    point leaves no partially-committed state: recover_scan will DELETE the
    pending rows (acceptance #3, tested in C8).

    lean_path challenge: auto-increment IDs are unknown before INSERT.
    We insert with a UUID-based placeholder path, get the real ID, then
    finalize with the canonical <id>_<slug> path.
    """
    db = db_path or _DEFAULT_DB
    base = base_dir or _DEFAULT_BASE

    leaf = Path(args.leaf_strategy)
    if not leaf.exists():
        print(f"error: --leaf-strategy file not found: {leaf}", file=sys.stderr)
        sys.exit(1)

    p = args.problem
    slug = args.slug
    kind = args.kind
    tmp_id = str(uuid.uuid4())

    conn = connect(db)
    init_schema(conn)
    writer = CommitWriter(conn)

    # Step 1a: INSERT goals (pending) — placeholder lean_path avoids needing
    # the auto-increment ID up-front. finalize() will set the canonical path.
    tmp_goal_lean = f"Problems/{p}/Goals/_pending_{tmp_id}/{slug}.lean"
    goal_id = writer.begin("goals", "insert", {
        "problem": p,
        "slug": slug,
        "lean_path": tmp_goal_lean,
        "origin": "root",
        "kind": kind,
        "status": "open",
    })

    # Now we know goal_id — compute canonical paths.
    g_folder = f"{goal_id}_{slug}"
    real_goal_lean = f"Problems/{p}/Goals/{g_folder}/{slug}.lean"

    # Step 1b: INSERT strategies (pending)
    tmp_strategy_lean = f"Problems/{p}/Goals/{g_folder}/Strategies/_pending_{tmp_id}.lean"
    strategy_id = writer.begin("strategies", "insert", {
        "goal_id": goal_id,
        "lean_path": tmp_strategy_lean,
        "status": "proposed",
    })

    real_strategy_lean = f"Problems/{p}/Goals/{g_folder}/Strategies/{strategy_id}_{slug}.lean"

    # Create goal directory and goal lean file (empty statement placeholder).
    goal_lean_path = base / real_goal_lean
    goal_lean_path.parent.mkdir(parents=True, exist_ok=True)
    if not goal_lean_path.exists():
        goal_lean_path.write_text(f"-- Goal: {slug}\n", encoding="utf-8")

    # Create strategies directory (stage_file will mkdir parents anyway, but be explicit).
    strategy_lean_path = base / real_strategy_lean
    strategy_lean_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 2: mv leaf-strategy → canonical strategy lean_path.
    writer.stage_file(leaf, strategy_lean_path)

    # Step 3: finalize both rows with canonical lean_paths.
    writer.finalize("goals", goal_id, {"lean_path": real_goal_lean})
    writer.finalize("strategies", strategy_id, {"lean_path": real_strategy_lean})

    # Enqueue Builder task (outside CommitWriter — queue is append-only, no recovery needed).
    with conn:
        conn.execute(
            "INSERT INTO queue (kind, target_id, priority, created_at) VALUES (?, ?, ?, ?)",
            ("Builder", str(strategy_id), 0, _now()),
        )

    print(f"goal add: goal_id={goal_id} slug={slug!r} strategy_id={strategy_id}")
    print(f"  lean_path:          {real_goal_lean}")
    print(f"  strategy lean_path: {real_strategy_lean}")
    print(f"  queued Builder task for strategy {strategy_id}")


# ──────────────────────────────────────────────────────────────
# run
# ──────────────────────────────────────────────────────────────


def cmd_run(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """Start Reactor: recover_scan → queue drain → exit.

    --once and --daemon are P1-equivalent (both exit after queue empties).
    P2+ will implement true daemon blocking on event_bus for --daemon.
    """
    db = db_path or _DEFAULT_DB
    base = str(base_dir or _DEFAULT_BASE)
    cfg = ReactorConfig(base_dir=base)
    Reactor(db, cfg).run()


# ──────────────────────────────────────────────────────────────
# db recover
# ──────────────────────────────────────────────────────────────


def cmd_db_recover(
    args: Any,
    db_path: Path | None = None,
) -> None:
    """Run CommitWriter.recover_scan and report results."""
    db = db_path or _DEFAULT_DB
    conn = connect(db)
    init_schema(conn)
    recovered = CommitWriter(conn).recover_scan()
    total = sum(len(ids) for ids in recovered.values())
    if total == 0:
        print("recover: no pending rows found — DB is clean")
    else:
        for table, ids in recovered.items():
            if ids:
                print(f"recover: {table} rows recovered: {ids}")


# ──────────────────────────────────────────────────────────────
# goal show
# ──────────────────────────────────────────────────────────────


def _parse_goal_id(raw: str) -> int | None:
    """Parse 'G_1', 'G1', or '1' → int. Returns None on failure."""
    s = raw
    if s.upper().startswith("G_"):
        s = s[2:]
    elif s.upper().startswith("G"):
        s = s[1:]
    try:
        return int(s)
    except ValueError:
        return None


def cmd_goal_show(
    args: Any,
    db_path: Path | None = None,
) -> None:
    """Display goal status, answer_data, lean_path, and linked strategies."""
    db = db_path or _DEFAULT_DB
    conn = connect(db)
    init_schema(conn)

    goal_id = _parse_goal_id(args.goal_id)
    if goal_id is None:
        print(f"error: cannot parse goal id {args.goal_id!r} (expected integer or G_N)",
              file=sys.stderr)
        sys.exit(1)

    row = conn.execute(
        "SELECT id, slug, problem, kind, status, answer_data, lean_path, depth "
        "FROM goals WHERE id = ?",
        (goal_id,),
    ).fetchone()

    if row is None:
        print(f"error: goal not found: {args.goal_id!r}", file=sys.stderr)
        sys.exit(1)

    g_id, slug, problem, kind, status, answer_data, lean_path, depth = row
    print(f"goal {g_id} ({slug})")
    print(f"  problem:   {problem}")
    print(f"  kind:      {kind}")
    print(f"  status:    {status}")
    print(f"  lean_path: {lean_path}")
    if depth is not None:
        print(f"  depth:     {depth}")
    if answer_data:
        ad = json.loads(answer_data)
        print(f"  answer_data:")
        for k, v in ad.items():
            print(f"    {k}: {v}")

    strats = conn.execute(
        "SELECT id, lean_path, status, commit_state "
        "FROM strategies WHERE goal_id = ? ORDER BY id",
        (g_id,),
    ).fetchall()
    if strats:
        print(f"  strategies ({len(strats)}):")
        for s_id, s_path, s_status, s_cs in strats:
            print(f"    [{s_id}] status={s_status} commit_state={s_cs}")
            print(f"          {s_path}")


# ──────────────────────────────────────────────────────────────
# Argument parser
# ──────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asterism",
        description="Asterism proof framework (P1 skeleton)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── init ──────────────────────────────────────────────────
    p_init = sub.add_parser("init", help="initialize a new Problem directory")
    p_init.add_argument("--problem", required=True, metavar="NAME",
                        help="problem name (creates Problems/<NAME>/)")

    # ── goal ──────────────────────────────────────────────────
    p_goal = sub.add_parser("goal", help="goal management")
    goal_sub = p_goal.add_subparsers(dest="goal_command", required=True)

    p_add = goal_sub.add_parser("add", help="add a root goal with a leaf strategy")
    p_add.add_argument("--problem", required=True, metavar="NAME")
    p_add.add_argument("--slug", required=True, metavar="SLUG")
    p_add.add_argument("--kind", required=True,
                       choices=["theorem", "conjecture", "construction"])
    p_add.add_argument(
        "--leaf-strategy", required=True, dest="leaf_strategy", metavar="FILE",
        help="[P1 testing-only; P2 removes this flag — Backward will auto-generate leaf strategies]",
    )

    p_show = goal_sub.add_parser("show", help="show goal status and strategies")
    p_show.add_argument("goal_id", metavar="GOAL_ID",
                        help="integer ID or G_N format")

    # ── run ───────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="run the Reactor (drain queue then exit)")
    mode = p_run.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", default=False,
                      help="[P1 default] drain queue then exit")
    mode.add_argument("--daemon", action="store_true", default=False,
                      help="[P2+ only; P1 behavior identical to --once]")

    # ── db ────────────────────────────────────────────────────
    p_db = sub.add_parser("db", help="database utilities")
    db_sub = p_db.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("recover", help="run CommitWriter.recover_scan")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "goal":
        if args.goal_command == "add":
            cmd_goal_add(args)
        elif args.goal_command == "show":
            cmd_goal_show(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "db":
        if args.db_command == "recover":
            cmd_db_recover(args)


if __name__ == "__main__":
    main()
