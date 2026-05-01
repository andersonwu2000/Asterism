"""CLI: asterism init <p> | asterism run [--once] | asterism reset <p>
       | asterism status <p> [--json] | asterism prune [<p>] [--dry-run].

See architecture.md §9.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db, dispatcher, manifest, prune


# F28 — daemon log lifecycle.
LOG_DIR = Path(".asterism") / "logs"
LOG_RETENTION_KEEP = 20  # most-recent N logs kept; older deleted on startup


class _Tee:
    """Write to multiple text streams. Used so the daemon's stdout
    appears on the operator's terminal AND in the per-run log file."""
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            st.write(s)
            st.flush()
        return len(s)

    def flush(self):
        for st in self._streams:
            st.flush()

    def isatty(self):
        # Some downstream tools query isatty; report based on the
        # primary (terminal) stream.
        return getattr(self._streams[0], "isatty", lambda: False)()


def _log_filename(workspace: Path) -> str:
    """`<problem>_<model>_<UTC ts>.log` — `<problem>` falls back to
    `daemon` when the DB has no problems yet (e.g. first run before
    init), or `multi` when more than one problem is registered."""
    problem = "daemon"
    try:
        conn = db.connect()
        names = [r[0] for r in conn.execute(
            "SELECT name FROM problems ORDER BY name").fetchall()]
        conn.close()
        if len(names) == 1:
            problem = names[0]
        elif len(names) > 1:
            problem = "multi"
    except Exception:
        # DB missing / unreadable: keep 'daemon' default
        pass
    model = os.environ.get("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    # Strip path-unsafe chars from model (just in case env carries them)
    model = re.sub(r"[^\w.-]", "_", model)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{problem}_{model}_{ts}.log"


def _open_run_log(workspace: Path) -> Path:
    """Ensure `.asterism/logs/` exists, prune oldest beyond retention,
    and return the new log file's path. Caller is responsible for
    actually opening + redirecting."""
    log_dir = workspace / LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    _retain_recent_logs(log_dir, keep=LOG_RETENTION_KEEP)
    return log_dir / _log_filename(workspace)


def _retain_recent_logs(log_dir: Path, *, keep: int) -> list[Path]:
    """Delete .log files beyond the most-recent `keep` count
    (sorted by mtime). Returns the deleted paths for tests."""
    if not log_dir.exists():
        return []
    logs = sorted(log_dir.glob("*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    deleted: list[Path] = []
    for old in logs[keep:]:
        try:
            old.unlink()
            deleted.append(old)
        except OSError:
            pass
    return deleted


# Root.lean lifecycle (F15):
#  initial state — auto-written by `init`: `theorem main : <stmt> := by sorry`
#  during run    — framework writes proofs/_strategy_sNN.lean files;
#                  Root.lean unchanged.
#  on root proved — `prune.reconcile_proved_goals` rewrites Root.lean to
#                   wrap form: `import Problems.X.proofs._strategy_sNN`
#                   then `theorem main : <stmt> := sNN`.
#  Manual editing of Root.lean is not expected. The init guard below
#  rejects anything that doesn't match these two shapes (sorry stub or
#  wrap form) unless `--force` is given.

# Lazy match between `theorem main` and the first `:=` so statements
# containing colons (`∀ p : ℕ, ...`) don't break the regex.
_SORRY_BODY_RE = re.compile(
    r"theorem\s+main\b.*?:=\s*by\s+sorry\b", re.DOTALL)
# Wrap form: bound to a strategy term `s\d+`. The promote-to-Root step
# always uses this exact shape.
_WRAP_BODY_RE = re.compile(
    r"theorem\s+main\b.*?:=\s*s\d+\b", re.DOTALL)


def _classify_root_body(text: str) -> str:
    """Classify Root.lean's `theorem main` body as one of:
    - 'sorry' : `:= by sorry`  (initial state, auto-created)
    - 'wrap'  : `:= s<N>`      (post-prove wrap form)
    - 'unknown': anything else (user-written sketch or in-progress)
    """
    if _SORRY_BODY_RE.search(text):
        return "sorry"
    if _WRAP_BODY_RE.search(text):
        return "wrap"
    return "unknown"


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
    else:
        # F15 — guard: reject manually-written or in-progress Root.lean
        # so a fresh init never silently wraps non-canonical state.
        # 'sorry' (auto-shape) and 'wrap' (post-prove) are both fine;
        # anything else is operator confusion until --force overrides.
        body_kind = _classify_root_body(
            root_lean.read_text(encoding="utf-8"))
        if body_kind == "unknown" and not args.force:
            print(
                f"FAIL: {root_lean} has a non-sorry, non-wrap proof body.\n"
                f"  Asterism manages Root.lean's lifecycle: it should be\n"
                f"  `:= by sorry` initially, and gets rewritten to the\n"
                f"  wrap form `:= sNN` automatically when root_proved.\n"
                f"  If you wrote a hand sketch intentionally, re-run\n"
                f"  with `--force` to bypass this check; otherwise reset\n"
                f"  Root.lean to `:= by sorry` (or delete it and let\n"
                f"  init recreate it).",
                file=sys.stderr,
            )
            return 1

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
    # F28 — auto-tee daemon stdout/stderr into .asterism/logs/<...>.log
    # so post-run forensics + post-compact handoffs always have a
    # canonical artifact, while the operator still sees real-time
    # output on the terminal.
    log_path = _open_run_log(workspace)
    log_file = log_path.open("w", encoding="utf-8")
    print(f"[cli] log → {log_path.relative_to(workspace).as_posix()}",
          flush=True)
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = _Tee(orig_stdout, log_file)
    sys.stderr = _Tee(orig_stderr, log_file)
    try:
        rc = dispatcher.run(workspace, once=getattr(args, "once", False))
        return rc
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        try:
            log_file.close()
        except OSError:
            pass


def cmd_reset(args: argparse.Namespace) -> int:
    """Wipe one Problem's DB rows + on-disk proof files + Root.lean back
    to sorry-stub form. Manifest.md / Defs.lean / lean files outside
    `Problems/<p>/proofs/` untouched. Idempotent — running on a clean
    Problem yields the same `OK` output without errors.

    Does NOT touch `.attempts/` (per-pipeline ephemeral state, possibly
    in-flight when other Problems are running). If the problem's daemon
    is dead, the operator can `rm -rf .attempts/` separately.

    Refuses to reset if no Manifest.md exists (signals user typo).
    """
    workspace = Path.cwd()
    problem = args.problem
    pdir = workspace / "Problems" / problem
    if not pdir.exists():
        print(f"FAIL: Problems/{problem}/ not found", file=sys.stderr)
        return 1
    mfst_path = pdir / "Manifest.md"
    if not mfst_path.exists():
        print(f"FAIL: {mfst_path} not found", file=sys.stderr)
        return 1

    conn = db.connect()
    db.init_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")

    gids = [r[0] for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ?", (problem,)).fetchall()]
    sids: list[int] = []
    if gids:
        ph = ",".join("?" * len(gids))
        sids = [r[0] for r in conn.execute(
            f"SELECT id FROM strategies WHERE goal_id IN ({ph})",
            gids).fetchall()]

    # Delete in FK-safe order: leaf tables first.
    if sids:
        ph = ",".join("?" * len(sids))
        conn.execute(
            f"DELETE FROM strategy_subgoals WHERE strategy_id IN ({ph})",
            sids)
        conn.execute(
            f"DELETE FROM dead_attempts WHERE target_kind='Strategy' "
            f"AND target_id IN ({ph})", sids)
        conn.execute(
            f"DELETE FROM queue WHERE kind='Verify' AND target_id IN ({ph})",
            [str(s) for s in sids])
        conn.execute(f"DELETE FROM strategies WHERE id IN ({ph})", sids)
    if gids:
        ph = ",".join("?" * len(gids))
        conn.execute(
            f"DELETE FROM dead_attempts WHERE target_kind='Goal' "
            f"AND target_id IN ({ph})", gids)
        conn.execute(
            f"DELETE FROM queue WHERE kind!='Verify' AND target_id IN ({ph})",
            [str(g) for g in gids])
        conn.execute(f"DELETE FROM goals WHERE id IN ({ph})", gids)
    conn.execute("DELETE FROM problems WHERE name = ?", (problem,))
    conn.commit()

    # Filesystem cleanup. Only inside Problems/<p>/proofs/, never higher.
    proofs_dir = pdir / "proofs"
    deleted_files: list[str] = []
    if proofs_dir.exists():
        for pattern in ("L_*.lean", "_strategy_*.lean"):
            for f in proofs_dir.glob(pattern):
                try:
                    f.unlink()
                    deleted_files.append(f.name)
                except OSError:
                    pass

    # Restore Root.lean to sorry stub (same template as cmd_init).
    mfst = manifest.parse(mfst_path)
    root_lean = pdir / "Root.lean"
    if mfst.statement:
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

    print(f"OK: reset {problem}")
    print(f"  DB rows: {len(gids)} goals, {len(sids)} strategies cleared")
    print(f"  Files: {len(deleted_files)} proof file(s) removed; Root.lean reset")
    attempts_dir = workspace / ".attempts"
    if attempts_dir.exists():
        att_n = sum(1 for _ in attempts_dir.iterdir())
        if att_n:
            print(f"  Note: .attempts/ has {att_n} dir(s) — untouched. "
                  f"Kill any running daemon then `rm -rf .attempts/` for "
                  f"full cleanup.")
    return 0


def _status_payload(conn, problem: str) -> dict:
    """Pure data: collect status info for one problem. Shared between
    text and --json output paths so both see the same shape."""
    goals = [dict(r) for r in conn.execute(
        "SELECT id, slug, status, attempts, depth FROM goals "
        "WHERE problem = ? ORDER BY id", (problem,)).fetchall()]
    if not goals:
        return {"problem": problem, "exists": False}

    gids = [g["id"] for g in goals]
    ph_g = ",".join("?" * len(gids))
    strategies = [dict(r) for r in conn.execute(
        f"SELECT id, goal_id, status FROM strategies "
        f"WHERE goal_id IN ({ph_g}) ORDER BY id", gids).fetchall()]
    sids = [s["id"] for s in strategies]

    # Recent dead_attempts targeting this problem's goals or strategies.
    deads = []
    if gids and sids:
        ph_s = ",".join("?" * len(sids))
        deads = [dict(r) for r in conn.execute(
            f"SELECT id, target_kind, target_id, failure_reason, ts "
            f"FROM dead_attempts "
            f"WHERE (target_kind='Goal' AND target_id IN ({ph_g})) "
            f"   OR (target_kind='Strategy' AND target_id IN ({ph_s})) "
            f"ORDER BY id DESC LIMIT 50",
            list(gids) + list(sids)).fetchall()]
    elif gids:
        deads = [dict(r) for r in conn.execute(
            f"SELECT id, target_kind, target_id, failure_reason, ts "
            f"FROM dead_attempts "
            f"WHERE target_kind='Goal' AND target_id IN ({ph_g}) "
            f"ORDER BY id DESC LIMIT 50", gids).fetchall()]

    fr_counts: dict[str, int] = {}
    for d in deads:
        fr_counts[d["failure_reason"]] = fr_counts.get(
            d["failure_reason"], 0) + 1

    # Recent pipelines (filtered to this problem). pipelines.target_id is TEXT,
    # so compare against str() of our int ids.
    gid_strs = {str(g) for g in gids}
    sid_strs = {str(s) for s in sids}
    pipes_recent = [dict(r) for r in conn.execute(
        "SELECT id, kind, target_id, target_kind, status, outcome, "
        "started_at, finished_at FROM pipelines "
        "ORDER BY finished_at DESC LIMIT 50").fetchall()]
    pipes_recent = [
        p for p in pipes_recent
        if (p["target_kind"] == "Goal" and p["target_id"] in gid_strs)
        or (p["target_kind"] == "Strategy" and p["target_id"] in sid_strs)
    ][:10]

    queue_count = conn.execute(
        f"SELECT count(*) FROM queue "
        f"WHERE (kind!='Verify' AND target_id IN ({ph_g}))"
        + (f" OR (kind='Verify' AND target_id IN ({','.join('?'*len(sids))}))"
           if sids else ""),
        list(map(str, gids)) + list(map(str, sids)),
    ).fetchone()[0] if gids else 0

    return {
        "problem": problem,
        "exists": True,
        "goals": goals,
        "strategies": strategies,
        "live_strategies_count": sum(
            1 for s in strategies if s["status"] == "proposed"),
        "queue_count": queue_count,
        "recent_failure_reasons": fr_counts,
        "recent_pipelines": pipes_recent,
        "dead_attempts_window": len(deads),
    }


def cmd_status(args: argparse.Namespace) -> int:
    """Show one Problem's current state: goal table, live strategies,
    queue depth, recent dead_attempts grouped by failure_reason, recent
    pipelines. Replaces the ad-hoc `python -c 'import sqlite3; ...'`
    one-liners. `--json` emits the same data structure for piping."""
    conn = db.connect()
    db.init_schema(conn)
    payload = _status_payload(conn, args.problem)

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("exists") else 1

    if not payload.get("exists"):
        print(f"problem '{args.problem}' not initialized "
              f"(run `asterism init {args.problem}`)")
        return 1

    print(f"=== {payload['problem']} ===")
    print(f"\nGoals ({len(payload['goals'])}):")
    for g in payload["goals"]:
        print(f"  [{g['id']:>3}] depth={g['depth']} {g['status']:<11}"
              f" attempts={g['attempts']} {g['slug']}")
    print(f"\nLive strategies: {payload['live_strategies_count']} "
          f"of {len(payload['strategies'])} total")
    for s in payload["strategies"]:
        if s["status"] == "proposed":
            print(f"  [{s['id']:>3}] goal={s['goal_id']} {s['status']}")
    print(f"\nQueue depth: {payload['queue_count']}")

    fr = payload["recent_failure_reasons"]
    if fr:
        print(f"\nFailure reasons (last {payload['dead_attempts_window']} "
              f"dead_attempts):")
        for reason, count in sorted(fr.items(), key=lambda x: -x[1]):
            print(f"  {count:>3}  {reason}")

    pipes = payload["recent_pipelines"]
    if pipes:
        print(f"\nRecent pipelines (last {len(pipes)}):")
        for p in pipes:
            print(f"  {p['kind']:<8} {p['target_kind']}={p['target_id']:<3}"
                  f" {p['status']:<10} {p['outcome']}")
    return 0


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
    p_init.add_argument(
        "--force", action="store_true",
        help="bypass the Root.lean-shape guard (allows hand-written sketches)",
    )
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="run dispatcher")
    p_run.add_argument("--once", action="store_true",
                       help="exit when queue empties")
    p_run.set_defaults(func=cmd_run)

    p_reset = sub.add_parser(
        "reset",
        help="wipe a Problem's DB rows + proof files + Root.lean stub",
    )
    p_reset.add_argument("problem", help="problem name")
    p_reset.set_defaults(func=cmd_reset)

    p_status = sub.add_parser(
        "status",
        help="show goals / strategies / dead_attempts / pipelines for a Problem",
    )
    p_status.add_argument("problem", help="problem name")
    p_status.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of human-readable text",
    )
    p_status.set_defaults(func=cmd_status)

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
