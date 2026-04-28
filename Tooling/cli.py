"""Asterism CLI (P1+P2+P3+P5+P6).

Entry point: python -m Tooling.cli <subcommand> [args]

Subcommands:
  init       --problem <name>
  goal       add     --problem P --slug S --kind K
                     (--spec STMT | --spec-file PATH | --leaf-strategy FILE)
                     [--imports CSV]                     [P6 C44]
  goal       show    <GOAL_ID>
  goal       unblock <GOAL_ID> (<pipeline_kind> | --all)   [P3 manual rescue]
  run        [--once] [--daemon] [--bypass-startup-check]   [P2 daemon default + P6 C44]
  stop       [--signal pause|resume|shutdown] [--all]       [P2 control IPC]
  db         recover
  agent      test    --provider P --prompt STR              [P5]
  problem    list                                            [P6 C44]
  problem    pause   --problem NAME                         [P6 C44]
  problem    resume  --problem NAME                         [P6 C44]
  library    list                                            [P6 C44]
  library    check-deps                                      [P6 C44]
  library    reindex                                         [P6 C44 stub → C45]
  library    audit                                           [P6 C44 stub]
  scheduler  force-clear [--force]                           [P6 C44]
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from Tooling.commit import CommitFault, CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.scheduler import Reactor, ReactorConfig

_DEFAULT_DB = Path("asterism.db")
_DEFAULT_BASE = Path(".")

_META_TEMPLATE = """\
---
problem_name: {problem_name}
axioms:
  - propext
  - Quot.sound
  - Classical.choice
# models:           # optional: override framework model defaults (architecture §8.3)
#   backward.agent: opus
#   builder.tactic_llm: sonnet
---

# META — {problem_name}

(Goals are managed by the scheduler. Query `asterism goal show <id>` for live state.)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────
# init
# ──────────────────────────────────────────────────────────────


def cmd_init(args: Any, base_dir: Path | None = None) -> None:
    """Create Problems/<name>/{META.md, Defs.lean, Root.lean}.

    P6.x patch 4: after writing the files, kick off `lake build
    Problems.<name>.Defs` so the Defs.olean exists in the Asterism build
    cache. Subsequent `lake env lean Problems/<name>/Goals/...` invocations
    can then resolve `import Problems.<name>.Defs` without first running
    a manual `lake build`. Build failure does not block init (operator
    can debug Defs.lean and re-run `lake build` manually).
    """
    base = base_dir or _DEFAULT_BASE
    prob_dir = base / "Problems" / args.problem
    prob_dir.mkdir(parents=True, exist_ok=True)

    meta = prob_dir / "META.md"
    if not meta.exists():
        meta.write_text(_META_TEMPLATE.format(problem_name=args.problem), encoding="utf-8")

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

    # P6.x patch 4: build Defs.olean so subsequent `lake env lean`
    # invocations can resolve `import Problems.<p>.Defs`.
    import subprocess
    print(f"  building Problems.{args.problem}.Defs ...")
    try:
        result = subprocess.run(
            ["lake", "build", f"Problems.{args.problem}.Defs"],
            cwd=str(base), capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=600,
        )
        if result.returncode == 0:
            print(f"  Defs.olean ready (lake build pass)")
        else:
            tail = (result.stdout or result.stderr or "").splitlines()[-3:]
            print(f"  warning: lake build Defs failed (rc={result.returncode}):"
                  f" {'; '.join(tail)}", file=sys.stderr)
            print(f"  fix Defs.lean and run `lake build "
                  f"Problems.{args.problem}.Defs` manually before adding goals",
                  file=sys.stderr)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"  warning: could not run lake build: {exc}", file=sys.stderr)


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

    spec = getattr(args, "spec", None)
    spec_file = getattr(args, "spec_file", None)
    leaf_arg = getattr(args, "leaf_strategy", None)

    # P3 C26 R3 LOW-2: strip inline --spec for symmetry with --spec-file
    # (which strips read_text() trailing newlines). Avoids surprise
    # whitespace landing in goals.question + the .lean template.
    if spec is not None:
        spec = spec.strip()

    # P3 C26: --spec-file reads --spec contents from file (long statements
    # that don't fit on the CLI). Mutually exclusive with --spec inline.
    # R3 LOW-5: handle directory / non-UTF8 binary gracefully.
    if spec_file is not None:
        spec_file_path = Path(spec_file)
        if not spec_file_path.is_file():
            print(f"error: --spec-file not a regular file: {spec_file_path}",
                  file=sys.stderr)
            sys.exit(1)
        try:
            spec = spec_file_path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError as exc:
            print(f"error: --spec-file not valid UTF-8: {spec_file_path}: {exc}",
                  file=sys.stderr)
            sys.exit(1)
        if not spec:
            print(f"error: --spec-file is empty: {spec_file_path}", file=sys.stderr)
            sys.exit(1)

    if spec is None and leaf_arg is None:
        print("error: must provide either --spec, --spec-file, or --leaf-strategy",
              file=sys.stderr)
        sys.exit(1)
    if spec is not None and leaf_arg is not None:
        print("error: --spec and --leaf-strategy are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    leaf = None
    if leaf_arg is not None:
        leaf = Path(leaf_arg)
        if not leaf.exists():
            print(f"error: --leaf-strategy file not found: {leaf}", file=sys.stderr)
            sys.exit(1)

    p = args.problem
    slug = args.slug
    kind = args.kind
    tmp_id = str(uuid.uuid4())

    conn = connect(db)
    try:
        init_schema(conn)
        writer = CommitWriter(conn)

        # Step 1a: INSERT goals (pending) — placeholder lean_path avoids needing
        # the auto-increment ID up-front. finalize() will set the canonical path.
        tmp_goal_lean = f"Problems/{p}/Goals/_pending_{tmp_id}/{slug}.lean"
        goal_insert = {
            "problem": p,
            "slug": slug,
            "lean_path": tmp_goal_lean,
            "origin": "root",
            "kind": kind,
            "status": "open",
        }
        if spec is not None:
            goal_insert["question"] = spec
        goal_id = writer.begin("goals", "insert", goal_insert)

        # Now we know goal_id — compute canonical paths.
        g_folder = f"{goal_id}_{slug}"
        real_goal_lean = f"Problems/{p}/Goals/{g_folder}/{slug}.lean"

        if spec is not None:
            # ── P2 --spec path: write theorem template, enqueue Backward ──
            goal_lean_path = base / real_goal_lean
            goal_lean_path.parent.mkdir(parents=True, exist_ok=True)
            # P6 C44: --imports prepends extra import lines after the
            # default `import Problems.<p>.Defs` so consumers can pull
            # Library re-exports / cross-Problem deps without editing
            # the .lean file by hand. Comma-separated, whitespace
            # trimmed; empty entries dropped (operator typo tolerance).
            imports_arg = getattr(args, "imports", None) or ""
            extra_imports = [
                imp.strip() for imp in imports_arg.split(",") if imp.strip()
            ]
            import_lines = [f"import Problems.{p}.Defs"]
            import_lines.extend(f"import {imp}" for imp in extra_imports)
            template = (
                "\n".join(import_lines)
                + "\n\n"
                + f"theorem {slug} : {spec} := by sorry\n"
            )
            goal_lean_path.write_text(template, encoding="utf-8")

            writer.finalize("goals", goal_id, {"lean_path": real_goal_lean})

            with conn:
                conn.execute(
                    "INSERT INTO queue (kind, target_id, priority, created_at) VALUES (?, ?, ?, ?)",
                    ("Backward", str(goal_id), 0, _now()),
                )

            print(f"goal add: goal_id={goal_id} slug={slug!r}")
            print(f"  lean_path:    {real_goal_lean}")
            print(f"  kind:         {kind}")
            print(f"  spec:         {spec}")
            print(f"  queued Backward task for goal {goal_id}")
            if kind == "conjecture":
                # P4 C32: structural refill BFS will additionally enqueue
                # Refuter on next tick (architecture.md §6 三線並攻).
                # Counterexample (third line) deferred per task.md ## 延後 cycles.
                print(f"  conjecture mode: Refuter will be enqueued by "
                      f"the next BFS tick; Counterexample line is deferred")
        else:
            # ── P1 legacy --leaf-strategy path: pre-built strategy, enqueue Builder ──
            tmp_strategy_lean = f"Problems/{p}/Goals/{g_folder}/Strategies/_pending_{tmp_id}.lean"
            strategy_id = writer.begin("strategies", "insert", {
                "goal_id": goal_id,
                "lean_path": tmp_strategy_lean,
                "status": "proposed",
            })

            real_strategy_lean = f"Problems/{p}/Goals/{g_folder}/Strategies/{strategy_id}_{slug}.lean"

            goal_lean_path = base / real_goal_lean
            goal_lean_path.parent.mkdir(parents=True, exist_ok=True)
            if not goal_lean_path.exists():
                goal_lean_path.write_text(f"-- Goal: {slug}\n", encoding="utf-8")

            strategy_lean_path = base / real_strategy_lean
            strategy_lean_path.parent.mkdir(parents=True, exist_ok=True)

            writer.stage_file(leaf, strategy_lean_path)

            writer.finalize("goals", goal_id, {"lean_path": real_goal_lean})
            writer.finalize("strategies", strategy_id, {"lean_path": real_strategy_lean})

            with conn:
                conn.execute(
                    "INSERT INTO queue (kind, target_id, priority, created_at) VALUES (?, ?, ?, ?)",
                    ("Builder", str(strategy_id), 0, _now()),
                )

            print(f"goal add: goal_id={goal_id} slug={slug!r} strategy_id={strategy_id}")
            print(f"  lean_path:          {real_goal_lean}")
            print(f"  strategy lean_path: {real_strategy_lean}")
            print(f"  queued Builder task for strategy {strategy_id}")
    except CommitFault as exc:
        # COMMIT_FAULT env injection (test/acceptance path only). Print a friendly
        # message and exit 2 instead of raising a Python traceback. The pending
        # row(s) are intentionally left in 'pending' state so `db recover` can
        # clean them up (acceptance #3 path).
        print(f"goal add: interrupted by COMMIT_FAULT ({exc}); "
              f"run `asterism db recover` to clean up", file=sys.stderr)
        sys.exit(2)
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# run
# ──────────────────────────────────────────────────────────────


def cmd_run(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """Start Reactor in daemon mode (default) or single-shot (--once).

    Default (no flag): run_daemon() — blocks on event_queue, 30s structural
    refill tick, responds to control_signal from `asterism stop`.
    --once: P1 legacy single-shot drain-queue-then-exit.
    """
    db = db_path or _DEFAULT_DB
    base = str(base_dir or _DEFAULT_BASE)
    bypass = getattr(args, "bypass_startup_check", False)
    cfg = ReactorConfig(base_dir=base, bypass_startup_check=bypass)
    reactor = Reactor(db, cfg)
    if getattr(args, "once", False):
        reactor.run()
    else:
        reactor.run_daemon()


# ──────────────────────────────────────────────────────────────
# stop
# ──────────────────────────────────────────────────────────────


def cmd_stop(
    args: Any,
    db_path: Path | None = None,
) -> None:
    """Send a control signal to a running daemon via the DB events table.

    IPC mechanism: INSERT events row with kind='control_signal' and
    payload={'action': <action>, 'source': 'cli'}. The daemon's
    _poll_db_control_signals() picks it up within ~2s and enqueues to
    _event_queue so _handle_control_signal responds within the 5s window.

    If no scheduler row exists in the schedulers table, the daemon is
    not running — print a notice and exit 0 without inserting anything.
    """
    db = db_path or _DEFAULT_DB
    conn = connect(db)
    try:
        init_schema(conn)
        count = conn.execute("SELECT COUNT(*) FROM schedulers").fetchone()[0]
        if count == 0:
            print("no scheduler running")
            return

        action = "shutdown"
        if getattr(args, "all", False):
            action = "shutdown"
        elif getattr(args, "signal", None):
            action = args.signal

        payload = json.dumps({"action": action, "source": "cli"})
        try:
            with conn:
                conn.execute(
                    "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                    ("control_signal", payload, _now()),
                )
        except Exception as exc:
            print(f"error: failed to send control signal: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"sent {action} signal to scheduler")
    finally:
        conn.close()


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
    try:
        init_schema(conn)
        recovered = CommitWriter(conn).recover_scan()
        total = sum(len(ids) for ids in recovered.values())
        if total == 0:
            print("recover: no pending rows found — DB is clean")
        else:
            for table, ids in recovered.items():
                if ids:
                    print(f"recover: {table} rows recovered: {ids}")
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# goal show
# ──────────────────────────────────────────────────────────────


def _parse_goal_id(raw: str) -> int | None:
    """Parse 'G_1', 'G1', or '1' → int. Returns None on failure (including 'root' aliases)."""
    s = raw
    if s.upper().startswith("G_"):
        s = s[2:]
    elif s.upper().startswith("G"):
        s = s[1:]
    try:
        return int(s)
    except ValueError:
        return None


def _resolve_goal_id(raw: str, conn: Any) -> int | None:
    """Resolve raw → goal_id, supporting integer formats and 'root' / 'G_root' alias.

    phase1_skeleton.md ## Demo line 76 uses `asterism goal show G_root` — phase
    doc is read-only, so the CLI must accept this literal. P1 always has exactly
    one root goal per problem (Backward not yet implemented), so the alias maps
    to the unique origin='root' row. With multiple root goals (P2+ multi-Problem
    demo), this should be disambiguated; a warning is emitted in that case.
    """
    parsed = _parse_goal_id(raw)
    if parsed is not None:
        return parsed
    if raw.lower() in ("root", "g_root"):
        rows = conn.execute(
            "SELECT id FROM goals WHERE origin = 'root' ORDER BY id"
        ).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            print(f"warning: multiple root goals exist {[r[0] for r in rows]}; "
                  f"showing earliest (use integer id to disambiguate)",
                  file=sys.stderr)
        return rows[0][0]
    return None


def cmd_goal_unblock(
    args: Any,
    db_path: Path | None = None,
) -> None:
    """[P3] manually remove pipeline_kind(s) from goal's blocked_pipelines.

    Usage:
        asterism goal unblock <goal_id> <pipeline_kind>
        asterism goal unblock <goal_id> --all

    Used as a manual rescue path when an automated block (5 fails / IH-trap)
    fires on a goal the human knows is still salvageable.
    """
    from Tooling.subsystems.blocked_pipelines import (
        get_blocked_pipelines,
        unblock_pipeline,
    )

    db = db_path or _DEFAULT_DB
    conn = connect(db)
    try:
        init_schema(conn)
        goal_id = _resolve_goal_id(args.goal_id, conn)
        if goal_id is None:
            print(f"error: cannot resolve goal id {args.goal_id!r}",
                  file=sys.stderr)
            sys.exit(1)

        before = get_blocked_pipelines(conn, goal_id)
        if getattr(args, "unblock_all", False):
            removed = unblock_pipeline(conn, goal_id, None)
            after = get_blocked_pipelines(conn, goal_id)
            print(f"goal {goal_id}: unblocked all ({removed} entries removed)")
            print(f"  before: {before}")
            print(f"  after:  {after}")
        else:
            kind = args.pipeline_kind
            if kind is None:
                print("error: must provide pipeline_kind or --all", file=sys.stderr)
                sys.exit(1)
            removed = unblock_pipeline(conn, goal_id, kind)
            after = get_blocked_pipelines(conn, goal_id)
            if removed:
                print(f"goal {goal_id}: unblocked {kind!r}")
            else:
                print(f"goal {goal_id}: {kind!r} was not in blocked_pipelines (no-op)")
            print(f"  before: {before}")
            print(f"  after:  {after}")
    finally:
        conn.close()


def cmd_goal_show(
    args: Any,
    db_path: Path | None = None,
) -> None:
    """Display goal status, answer_data, lean_path, twin/silver-gold (P4 C32),
    blocked_pipelines, and linked strategies.

    P4 C32 extensions:
      - twin_of: resolved to G{id} ({slug}) line; from architecture.md §6
        this is set by Refuter pipeline (bidirectional G ↔ ¬G link)
      - silver-or-gold: when answer_data.type ∈ {'witness','construction'}
        the goal is in 'silver' state; type='classical' is 'gold'. Shown as
        an explicit silver/gold tag so operators can spot upgrade candidates
      - blocked_pipelines: surfaced when non-empty so the user can run
        `asterism goal unblock` to release the block
    """
    db = db_path or _DEFAULT_DB
    conn = connect(db)
    try:
        init_schema(conn)

        goal_id = _resolve_goal_id(args.goal_id, conn)
        if goal_id is None:
            print(f"error: cannot resolve goal id {args.goal_id!r} "
                  f"(expected integer, G_N, or 'root' / 'G_root' for the root goal)",
                  file=sys.stderr)
            sys.exit(1)

        row = conn.execute(
            "SELECT id, slug, problem, kind, status, answer_data, lean_path, "
            "depth, twin_of, blocked_pipelines "
            "FROM goals WHERE id = ?",
            (goal_id,),
        ).fetchone()

        if row is None:
            print(f"error: goal not found: {args.goal_id!r}", file=sys.stderr)
            sys.exit(1)

        (g_id, slug, problem, kind, status, answer_data, lean_path, depth,
         twin_of, blocked_pipelines) = row
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
            # Silver / gold tag (architecture.md §6 silver→gold mechanic).
            ad_type = ad.get("type")
            if ad_type == "classical":
                print(f"    verdict_strength: gold (classical proof)")
            elif ad_type in ("witness", "construction"):
                print(f"    verdict_strength: silver ({ad_type}-only — "
                      "upgrade pending)")
        if twin_of is not None:
            twin_row = conn.execute(
                "SELECT slug, status, kind FROM goals WHERE id = ?",
                (twin_of,),
            ).fetchone()
            if twin_row is None:
                print(f"  twin_of:   G{twin_of} <missing>")
            else:
                t_slug, t_status, t_kind = twin_row
                print(f"  twin_of:   G{twin_of} ({t_slug}) "
                      f"[kind={t_kind} status={t_status}]")
        if blocked_pipelines:
            # Loud surface on malformed JSON (silent-failure red line per
            # C29 R3 "same-module exception surface consistency" invariant —
            # answer_data.parse above also raises on malformed; blocked_
            # pipelines must match). DB schema invariant (architecture.md
            # L647): goals.blocked_pipelines is list-of-strings JSON; a
            # parse error implies schema violation that operators should
            # see, not a hidden empty.
            try:
                bp_list = json.loads(blocked_pipelines)
            except json.JSONDecodeError as exc:
                print(
                    f"error: goal {g_id} blocked_pipelines column "
                    f"malformed JSON: {exc}",
                    file=sys.stderr,
                )
                sys.exit(1)
            if bp_list:
                print(f"  blocked:   {', '.join(bp_list)}")

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
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Argument parser
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# problem list / pause / resume (P6 C44)
# ──────────────────────────────────────────────────────────────


def cmd_problem_list(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """List discovered Problems with axiom set + counts + paused state.

    Walks `Problems/*` via meta.scan_all_problems_with_errors so broken
    META.md surfaces as a SKIPPED row instead of crashing the listing.
    Pulls per-Problem goal/strategy counts from the DB. Paused state is
    DB-derivable only when an active scheduler emits
    `control_signal:problem_pause` events; the CLI walks the events
    table for the most recent action per Problem.
    """
    from Tooling.meta import scan_all_problems_with_errors

    db = db_path or _DEFAULT_DB
    base = base_dir or _DEFAULT_BASE
    successes, errors = scan_all_problems_with_errors(base)

    conn = connect(db)
    try:
        init_schema(conn)

        # Compute current paused-Problem set from event history. Walk
        # control_signal events in chronological order; latest action
        # wins per Problem. (Only daemon-applied events are kept; CLI-
        # source pause events represent ops requests not necessarily
        # acted on, so we filter on payload.status='applied'.)
        # C44 R3 HIGH-3 fix: narrow exception + emit stderr warning so
        # query failures (events table corruption / DB lock) are not
        # silently swallowed (silent-failure red line).
        import sqlite3 as _sqlite3
        paused: set[str] = set()
        try:
            event_rows = conn.execute(
                "SELECT payload FROM events "
                "WHERE kind = 'control_signal' "
                "ORDER BY id ASC"
            ).fetchall()
        except _sqlite3.Error as exc:
            print(
                f"warning: events table query failed ({exc}); "
                "paused state may be stale",
                file=sys.stderr,
            )
            event_rows = []
        for (payload_json,) in event_rows:
            try:
                pl = json.loads(payload_json) if payload_json else {}
            except json.JSONDecodeError:
                continue
            action = pl.get("action")
            problem = pl.get("problem")
            status = pl.get("status")
            if status != "applied" or not isinstance(problem, str):
                continue
            if action == "problem_pause":
                paused.add(problem)
            elif action == "problem_resume":
                paused.discard(problem)

        # Goal counts per Problem (use SQL aggregate).
        rows = conn.execute(
            "SELECT problem, status, COUNT(*) FROM goals "
            "WHERE commit_state = 'live' "
            "GROUP BY problem, status"
        ).fetchall()
        counts: dict[str, dict[str, int]] = {}
        for prob, status, n in rows:
            counts.setdefault(prob, {})[status] = n

        if not successes and not errors:
            print("no Problems found under Problems/ directory")
            return

        print(f"{'PROBLEM':<24} {'STATUS':<8} {'AXIOMS':<32} GOALS")
        for name in sorted(successes):
            meta = successes[name]
            axiom_str = ",".join(sorted(meta.axioms))
            if len(axiom_str) > 30:
                axiom_str = axiom_str[:27] + "..."
            status_tag = "paused" if name in paused else "active"
            c = counts.get(name, {})
            goal_str = (
                f"open={c.get('open', 0)} proved={c.get('proved', 0)} "
                f"shelved={c.get('shelved', 0)} refuted={c.get('refuted', 0)}"
            )
            print(f"{name:<24} {status_tag:<8} {axiom_str:<32} {goal_str}")
        for name in sorted(errors):
            err = errors[name]
            print(f"{name:<24} {'SKIPPED':<8} (META.md error: {err})")
    finally:
        conn.close()


def cmd_problem_pause(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """Emit a control_signal event so the running daemon adds the Problem
    to its in-memory paused-set. Returns 0 even if no daemon is running
    (the event row is the request; daemon-side state catches up on next
    startup that polls events). Refuses unknown problem names by
    cross-checking meta.scan_all_problems."""
    from Tooling.meta import scan_all_problems

    db = db_path or _DEFAULT_DB
    base = base_dir or _DEFAULT_BASE
    name = args.problem
    known = scan_all_problems(base)
    if name not in known:
        print(
            f"error: unknown problem {name!r} "
            f"(known: {sorted(known) or 'none'})",
            file=sys.stderr,
        )
        sys.exit(1)
    conn = connect(db)
    try:
        init_schema(conn)
        payload = json.dumps(
            {"action": "problem_pause", "source": "cli", "problem": name}
        )
        with conn:
            conn.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                ("control_signal", payload, _now()),
            )
        print(f"problem pause: queued pause for {name!r}")
    finally:
        conn.close()


def cmd_problem_resume(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """Symmetric of `cmd_problem_pause` — emits problem_resume."""
    from Tooling.meta import scan_all_problems

    db = db_path or _DEFAULT_DB
    base = base_dir or _DEFAULT_BASE
    name = args.problem
    known = scan_all_problems(base)
    if name not in known:
        print(
            f"error: unknown problem {name!r} "
            f"(known: {sorted(known) or 'none'})",
            file=sys.stderr,
        )
        sys.exit(1)
    conn = connect(db)
    try:
        init_schema(conn)
        payload = json.dumps(
            {"action": "problem_resume", "source": "cli", "problem": name}
        )
        with conn:
            conn.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                ("control_signal", payload, _now()),
            )
        print(f"problem resume: queued resume for {name!r}")
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# library list / check-deps / reindex / audit (P6 C44)
# ──────────────────────────────────────────────────────────────


def cmd_library_list(
    args: Any,
    db_path: Path | None = None,
) -> None:
    """List library_index rows (layer, name, source goal, committed_at)."""
    db = db_path or _DEFAULT_DB
    conn = connect(db)
    try:
        init_schema(conn)
        rows = conn.execute(
            "SELECT layer, name, path, source_root_id, committed_at "
            "FROM library_index ORDER BY layer, name"
        ).fetchall()
        if not rows:
            print("library: no entries")
            return
        print(f"{'LAYER':<16} {'NAME':<40} {'SRC_GOAL':<8} COMMITTED_AT")
        for layer, name, path, src_id, committed in rows:
            src_str = f"G{src_id}" if src_id is not None else "-"
            print(f"{layer:<16} {name:<40} {src_str:<8} {committed}")
            print(f"  → {path}")
    finally:
        conn.close()


def cmd_library_check_deps(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """Run check_axiom_coverage and surface violations + skipped Problems."""
    from Tooling.library.check_deps import check_axiom_coverage

    db = db_path or _DEFAULT_DB
    base = base_dir or _DEFAULT_BASE
    conn = connect(db)
    try:
        init_schema(conn)
        result = check_axiom_coverage(conn, base)
        print(
            f"library check-deps: scanned {result.entries_checked} "
            f"library entries × {result.n_problems} Problems"
        )
        if result.skipped_problems:
            print(
                f"  skipped problems: {sorted(result.skipped_problems)} "
                "(broken META.md — fix and rerun)"
            )
        if not result.violations:
            print("  no axiom-coverage violations")
            return
        print(f"  {len(result.violations)} violation(s):")
        for v in result.violations:
            print(
                f"  - {v.consumer_problem} consumes {v.entry_name!r}"
            )
            print(f"      axioms_used:     {sorted(v.axioms_used)}")
            print(f"      consumer_axioms: {sorted(v.consumer_axioms)}")
            print(f"      missing:         {sorted(v.missing)}")
        sys.exit(2)
    finally:
        conn.close()


def cmd_library_reindex(
    args: Any,
    db_path: Path | None = None,
    base_dir: Path | None = None,
) -> None:
    """C45: walk Library/Theorems/proved.lean + INSERT missing
    library_index rows. Per-Problem proved.lean files are NOT indexed
    (they're not framework-global); operator inspection covers them.

    spec phase6_library.md ## In line 58 (CLI binding) + ## 任務序列
    line 249 字面: 「Library reindex migration（跑過 P4/P5 既有 json
    補 INSERT library_index row）」. (C44 R3 MED-2 fix: previous
    citation pointed at line 79 which is the demo bash block.)

    Outputs: inserted / already_indexed / unresolved / unparsed
    counts so operators can spot file-vs-DB drift.
    """
    from Tooling.library.reindex import reindex_library

    db = db_path or _DEFAULT_DB
    base = base_dir or _DEFAULT_BASE
    conn = connect(db)
    try:
        init_schema(conn)
        result = reindex_library(conn, base)
        print(f"library reindex: scanned {result.n_lines_scanned} line(s)")
        print(f"  source: {result.library_file}")
        if result.inserted:
            print(f"  inserted ({len(result.inserted)}):")
            for n in result.inserted:
                print(f"    + {n}")
        if result.already_indexed:
            print(f"  already indexed: {len(result.already_indexed)} entries")
        if result.unresolved:
            print(
                f"  unresolved ({len(result.unresolved)}, no proved "
                f"goal matched):"
            )
            for n in result.unresolved:
                print(f"    ? {n}")
        if result.unparsed:
            print(f"  unparsed ({len(result.unparsed)}, hand-edits?):")
            for line in result.unparsed:
                print(f"    ! {line}")
        if not (result.inserted or result.unresolved or result.unparsed):
            print("  no changes (file ⊆ index)")
    finally:
        conn.close()


def cmd_library_audit(args: Any, db_path: Path | None = None) -> None:
    """C44 stub per phase6_library.md ## In line 62 字面: 「P6 預留
    stub exit 1 + 印『not implemented; tracked in P7+』+ TODO；避免
    P7 忘記」.

    Real implementation: Mathlib upgrade audit (重跑 #print axioms 對
    所有 Library entry 比對 trust_set snapshot) — defer until the
    Mathlib upgrade flow is defined.
    """
    # TODO(P7+): bind lake-driven Mathlib upgrade audit per
    # phase6_library.md:62.
    print(
        "library audit: not implemented; tracked in P7+",
        file=sys.stderr,
    )
    sys.exit(1)


# ──────────────────────────────────────────────────────────────
# scheduler force-clear (P6 C44)
# ──────────────────────────────────────────────────────────────


def cmd_scheduler_force_clear(
    args: Any,
    db_path: Path | None = None,
) -> None:
    """DELETE schedulers rows so a new instance can register.

    Without --force: refuses to delete rows whose last_heartbeat is within
    HEARTBEAT_TTL_SEC (default 90s, per Reactor.HEARTBEAT_TTL_SEC). The
    rationale is to make accidental clears impossible while a daemon is
    actually live; --force overrides the check (operator's risk: if the
    other daemon is alive, both will compete for the queue).
    """
    from Tooling.scheduler import Reactor

    db = db_path or _DEFAULT_DB
    conn = connect(db)
    try:
        init_schema(conn)
        ttl = Reactor.HEARTBEAT_TTL_SEC
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=ttl)
        ).isoformat()
        rows = conn.execute(
            "SELECT id, host, pid, started_at, last_heartbeat FROM schedulers"
        ).fetchall()
        if not rows:
            print("scheduler force-clear: schedulers table empty (no-op)")
            return

        live = [r for r in rows if r[4] > cutoff]
        force = getattr(args, "force", False)
        if live and not force:
            print(
                f"error: refusing to clear: {len(live)} live scheduler "
                f"row(s) (heartbeat within {ttl}s):",
                file=sys.stderr,
            )
            for r in live:
                print(
                    f"  id={r[0]} host={r[1]} pid={r[2]} "
                    f"last_heartbeat={r[4]}",
                    file=sys.stderr,
                )
            print(
                "  pass --force to override (only if you know the daemon "
                "is actually dead).",
                file=sys.stderr,
            )
            sys.exit(1)

        with conn:
            cur = conn.execute("DELETE FROM schedulers")
        print(
            f"scheduler force-clear: deleted {cur.rowcount} row(s)"
            + (f" ({len(live)} were live — --force used)" if live else "")
        )
    finally:
        conn.close()


def cmd_agent_test(args: Any) -> None:
    """P5 C37: invoke a single provider with a one-shot test prompt.

    Used by operators to smoke-test a freshly-installed CLI (e.g. just
    after `npm install gemini` or `pip install codex-cli`). Prints the
    provider's stdout to terminal and exits with the provider's returncode.

    Uses a fresh tempdir as the staging scope; subprocess cwd = tempdir.
    Session id is a fresh UUID. PROVIDER_MOCK_<NAME> env hook applies
    (handled in Provider._maybe_apply_mock; see docs/dev/test_hooks.md
    P5 row) — operators can dry-run with PROVIDER_MOCK_CLAUDE=fail_always
    to verify the env hook plumbing.
    """
    import tempfile
    from Tooling.agent.provider import ProviderError
    provider_name = args.provider
    if provider_name == "claude":
        from Tooling.agent.providers.claude import ClaudeProvider
        provider = ClaudeProvider()
    elif provider_name == "gemini":
        from Tooling.agent.providers.gemini import GeminiProvider
        provider = GeminiProvider()
    elif provider_name == "codex":
        from Tooling.agent.providers.codex import CodexProvider
        provider = CodexProvider()
    else:
        print(f"error: unknown provider {provider_name!r}", file=sys.stderr)
        sys.exit(1)

    session = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix="asterism_agent_test_") as tmp:
        try:
            response = provider.invoke(
                args.model_tier, args.prompt, [tmp], session,
            )
        except ProviderError as exc:
            print(f"agent test: {provider_name} ProviderError: {exc}",
                  file=sys.stderr)
            sys.exit(2)
        print(f"agent test: {provider_name} (model={response.extra.get('model_id', '?')})")
        print(f"  session_id: {session}")
        print(f"  exit_code:  {response.exit_code}")
        print("  output:")
        # Indent output for readability
        for line in response.output.splitlines() or [""]:
            print(f"    {line}")
        sys.exit(response.exit_code)


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

    p_add = goal_sub.add_parser("add", help="add a root goal (--spec for P2 Backward; --leaf-strategy for P1 legacy)")
    p_add.add_argument("--problem", required=True, metavar="NAME")
    p_add.add_argument("--slug", required=True, metavar="SLUG")
    p_add.add_argument("--kind", required=True,
                       choices=["theorem", "conjecture", "construction"])
    spec_group = p_add.add_mutually_exclusive_group(required=True)
    spec_group.add_argument(
        "--spec", default=None, metavar="STMT",
        help="Lean theorem statement (e.g. \"∀ m n : Nat, m + n = n + m\"); enqueues Backward",
    )
    spec_group.add_argument(
        "--spec-file", default=None, dest="spec_file", metavar="PATH",
        help="[P3] read --spec from file (for long statements that don't fit on the CLI)",
    )
    spec_group.add_argument(
        "--leaf-strategy", default=None, dest="leaf_strategy", metavar="FILE",
        help="[P1 legacy] pre-written leaf strategy .lean file; enqueues Builder directly",
    )
    p_add.add_argument(
        "--imports", default=None, metavar="CSV",
        help="[P6 C44] comma-separated extra Lean imports prepended after "
             "`import Problems.<p>.Defs` in the generated theorem template "
             "(e.g. \"Library.Theorems.proved,Problems.A.proved\")",
    )

    p_show = goal_sub.add_parser("show", help="show goal status and strategies")
    p_show.add_argument("goal_id", metavar="GOAL_ID",
                        help="integer ID or G_N format")

    # ── goal unblock ───────────────────────────────────────────
    p_unblock = goal_sub.add_parser(
        "unblock",
        help="[P3] manual rescue: remove pipeline_kind(s) from goal's blocked_pipelines",
    )
    p_unblock.add_argument("goal_id", metavar="GOAL_ID",
                           help="integer ID or G_N format")
    unblock_group = p_unblock.add_mutually_exclusive_group(required=True)
    unblock_group.add_argument(
        "pipeline_kind", nargs="?", default=None,
        choices=["Builder", "Backward", "Refuter", "Forward",
                 "Generalizer", "Counterexample", "ConstructionSearch", "Strategist"],
        help="single pipeline_kind to unblock",
    )
    unblock_group.add_argument(
        "--all", action="store_true", default=False,
        dest="unblock_all",
        help="unblock all pipeline_kinds for this goal",
    )

    # ── run ───────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="run Reactor in daemon mode (default) or --once")
    p_run.add_argument("--once", action="store_true", default=False,
                       help="[P1 legacy] drain queue then exit (default: daemon mode)")
    p_run.add_argument("--daemon", action="store_true", default=False,
                       help="[P1 legacy alias; daemon is default since P2] no-op for forward-compat")
    p_run.add_argument(
        "--bypass-startup-check", action="store_true", default=False,
        dest="bypass_startup_check",
        help="[P6 C44] DELETE all schedulers rows (live or stale) before "
             "registering. Operator escape hatch — emits a startup_bypass "
             "control_signal event for audit trail.",
    )

    # ── stop ──────────────────────────────────────────────────
    p_stop = sub.add_parser("stop", help="send control signal to running daemon")
    p_stop.add_argument(
        "--signal", metavar="ACTION", default="shutdown",
        choices=["pause", "resume", "shutdown"],
        help="control signal to send: pause | resume | shutdown (default: shutdown)",
    )
    p_stop.add_argument(
        "--all", action="store_true", default=False,
        help="stop all schedulers (equivalent to --signal shutdown)",
    )

    # ── db ────────────────────────────────────────────────────
    p_db = sub.add_parser("db", help="database utilities")
    db_sub = p_db.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("recover", help="run CommitWriter.recover_scan")

    # ── agent ─────────────────────────────────────────────────
    # P5 C37: manual provider smoke test, e.g.
    #   asterism agent test --provider claude --prompt "say hi"
    # Sends a single prompt to one provider with a temporary staging dir
    # as scope_dirs[0]; prints the response stdout. Used by operators to
    # verify a freshly-installed CLI (gemini / codex) works before
    # PROVIDER_MOCK fallback testing.
    p_agent = sub.add_parser(
        "agent", help="agent / provider utilities (P5)",
    )
    agent_sub = p_agent.add_subparsers(dest="agent_command", required=True)
    p_test = agent_sub.add_parser(
        "test", help="invoke a single provider with a test prompt",
    )
    p_test.add_argument(
        "--provider", required=True,
        choices=["claude", "gemini", "codex"],
        help="which provider to invoke",
    )
    p_test.add_argument(
        "--prompt", required=True, metavar="STR",
        help="prompt text to send",
    )
    p_test.add_argument(
        "--model-tier", default="sonnet",
        choices=["haiku", "sonnet", "opus"],
        metavar="TIER",
        help="model tier (default: sonnet)",
    )

    # ── problem (P6 C44) ──────────────────────────────────────
    p_problem = sub.add_parser(
        "problem", help="[P6 C44] multi-Problem listing + pause/resume",
    )
    problem_sub = p_problem.add_subparsers(dest="problem_command", required=True)

    problem_sub.add_parser(
        "list",
        help="list Problems with axiom set + goal counts + paused state",
    )

    p_pause = problem_sub.add_parser(
        "pause", help="pause spawning new pipelines for one Problem",
    )
    p_pause.add_argument("--problem", required=True, metavar="NAME")

    p_resume = problem_sub.add_parser(
        "resume", help="resume spawning for a previously paused Problem",
    )
    p_resume.add_argument("--problem", required=True, metavar="NAME")

    # ── library (P6 C44) ──────────────────────────────────────
    p_library = sub.add_parser(
        "library",
        help="[P6 C44] Library re-export inspection / cross-Problem deps check",
    )
    library_sub = p_library.add_subparsers(dest="library_command", required=True)

    library_sub.add_parser(
        "list", help="list library_index rows (layer, name, source goal)",
    )
    library_sub.add_parser(
        "check-deps",
        help="cross-Problem axiom-coverage check (Python-side; exit 2 on violations)",
    )
    library_sub.add_parser(
        "reindex", help="[stub → C45] reindex migration for pre-P6 proved.lean files",
    )
    library_sub.add_parser(
        "audit", help="[stub → C45] lake-driven library audit (Lean exe binding)",
    )

    # ── scheduler (P6 C44) ────────────────────────────────────
    p_scheduler = sub.add_parser(
        "scheduler", help="[P6 C44] scheduler liveness controls",
    )
    scheduler_sub = p_scheduler.add_subparsers(
        dest="scheduler_command", required=True,
    )
    p_force_clear = scheduler_sub.add_parser(
        "force-clear",
        help="DELETE schedulers rows so a new instance can register",
    )
    p_force_clear.add_argument(
        "--force", action="store_true", default=False,
        help="override the live-row safety check (DELETE even if heartbeat fresh)",
    )

    return parser


def _reconfigure_stdio_utf8() -> None:
    """Force stdout/stderr to UTF-8 so unicode (∀, ¬, ⊆, etc.) prints
    cleanly on Windows cp950 / shift_jis / other legacy codepages.

    P6.x patch (Round-1 演習 found): cmd_goal_add printed `∀` and
    UnicodeEncodeError'd on Windows cp950. Lean specs commonly contain
    unicode operators; the CLI must not crash on them.

    Best-effort: TextIOBase.reconfigure exists in Python 3.7+ for
    real streams, may be missing when stdout is redirected to a
    non-text wrapper (e.g. some test runners). On AttributeError we
    silently skip — the original codec stays.
    """
    import sys as _sys
    for stream in (_sys.stdout, _sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> None:
    _reconfigure_stdio_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "goal":
        if args.goal_command == "add":
            cmd_goal_add(args)
        elif args.goal_command == "show":
            cmd_goal_show(args)
        elif args.goal_command == "unblock":
            cmd_goal_unblock(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "db":
        if args.db_command == "recover":
            cmd_db_recover(args)
    elif args.command == "agent":
        if args.agent_command == "test":
            cmd_agent_test(args)
    elif args.command == "problem":
        if args.problem_command == "list":
            cmd_problem_list(args)
        elif args.problem_command == "pause":
            cmd_problem_pause(args)
        elif args.problem_command == "resume":
            cmd_problem_resume(args)
    elif args.command == "library":
        if args.library_command == "list":
            cmd_library_list(args)
        elif args.library_command == "check-deps":
            cmd_library_check_deps(args)
        elif args.library_command == "reindex":
            cmd_library_reindex(args)
        elif args.library_command == "audit":
            cmd_library_audit(args)
    elif args.command == "scheduler":
        if args.scheduler_command == "force-clear":
            cmd_scheduler_force_clear(args)


if __name__ == "__main__":
    main()
