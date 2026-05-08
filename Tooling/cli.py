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

from . import brief, db, dispatcher, manifest, prune, tree


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
    # P1-#8: resolve via the same chain as the actual workers (F39
    # per-pipeline provider/model), not the legacy ASTERISM_AGENT_MODEL
    # env which lies when builder/backward use different models. Use
    # the builder's resolved model as the canonical label; combine
    # with backward's model when they differ so a mixed-model run is
    # visible from the filename.
    try:
        from .llm import claude_cli as _cc
        b_model = _cc.resolve_model("builder")
        w_model = _cc.resolve_model("backward")
        model = b_model if b_model == w_model else f"{b_model}+{w_model}"
    except Exception:
        # Provider import failed (very early init / corrupt config):
        # fall back to legacy env so log filename always succeeds.
        model = os.environ.get("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    # Strip path-unsafe chars from model (just in case env carries them)
    model = re.sub(r"[^\w.+-]", "_", model)
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
            origin="root", depth=0, entry_kind=mfst.entry_kind,
        )
        print(f"OK: init {problem}, root goal id={gid} "
              f"entry_kind={mfst.entry_kind}")
    else:
        print(f"OK: {problem} already initialized (goal id={existing_goal['id']})")
    conn.commit()
    # Initial TREE.md so readers see structure right after init.
    tree.write(conn, workspace, problem)
    # Initial BRIEF.md — framework-rendered cross-spawn stable context
    # (sandbox / forbidden lemmas / mathlib hints / library / strategic
    # notes). Refreshed at daemon startup if Manifest changes.
    brief.write(workspace, mfst)
    # Seed LESSONS.md — agent-curated cross-spawn experience surface,
    # populated by reflection spawns at successful pipeline terminals.
    # The seed line ensures the Edit tool has an anchor: appending to a
    # 0-byte file via Edit fails (no `old_string` match). Reflection
    # prompt instructs the agent to insert new lessons after the seed
    # divider line.
    lessons_path = pdir / "LESSONS.md"
    if not lessons_path.exists():
        lessons_path.write_text(
            "<!-- Lessons learned across spawns on this problem.\n"
            "     One sentence per `- ` bullet. Reflection spawn appends\n"
            "     below this header; the divider line below is the\n"
            "     anchor Edit tool relies on. -->\n"
            "\n"
            "<!-- LESSONS_BEGIN -->\n",
            encoding="utf-8",
        )
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


def _soft_reset(problem: str) -> int:
    """P2-#6: undo the cascade caused by spawn_fast_fail bursts (F46
    detected provider-quota exhaustion as <10s rc=1 spam). The hard
    reset wipes everything; soft reset is surgical:

      1. Find dead_attempts on this problem with failure_reason in
         the spurious-failure set ('spawn_fast_fail').
      2. Delete those rows + matching pipelines rows.
      3. Recompute goals.attempts from surviving dead_attempts.
      4. Revive goals shelved purely from the cascade (no real
         Backward / Builder failure left).

    Doesn't touch proof files / Root.lean / Manifest. Operator runs
    after fixing the underlying provider issue (e.g. switching model
    after quota exhaust) to recover state without re-doing real work.
    """
    workspace = Path.cwd()
    pdir = workspace / "Problems" / problem
    if not pdir.exists():
        print(f"FAIL: Problems/{problem}/ not found", file=sys.stderr)
        return 1
    conn = db.connect()
    db.init_schema(conn)
    SPURIOUS = ("spawn_fast_fail",)

    # Goals belonging to this problem
    gids = [r[0] for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ?", (problem,)).fetchall()]
    if not gids:
        print(f"OK: soft-reset {problem} (no goals to clean)")
        return 0
    ph = ",".join("?" * len(gids))
    sph = ",".join("?" * len(SPURIOUS))
    spurious_pids = [r[0] for r in conn.execute(
        f"SELECT pipeline_id FROM dead_attempts "
        f"WHERE failure_reason IN ({sph}) "
        f"  AND ((target_kind='Goal' AND target_id IN ({ph})) "
        f"   OR  (target_kind='Strategy' AND target_id IN ("
        f"        SELECT id FROM strategies WHERE goal_id IN ({ph}))))",
        (*SPURIOUS, *gids, *gids)).fetchall()]
    if not spurious_pids:
        print(f"OK: soft-reset {problem} (no spurious dead_attempts found)")
        return 0
    pidph = ",".join("?" * len(spurious_pids))
    n_da = conn.execute(
        f"DELETE FROM dead_attempts WHERE pipeline_id IN ({pidph})",
        spurious_pids).rowcount
    n_pl = conn.execute(
        f"DELETE FROM pipelines WHERE id IN ({pidph})",
        spurious_pids).rowcount
    # Recompute goals.attempts = number of remaining (real) Goal-kind
    # dead_attempts on each goal in this problem.
    n_recomp = 0
    for gid in gids:
        n = conn.execute(
            "SELECT COUNT(*) FROM dead_attempts WHERE target_kind='Goal' "
            "AND target_id = ?", (gid,)).fetchone()[0]
        cur = conn.execute(
            "SELECT attempts, status FROM goals WHERE id = ?",
            (gid,)).fetchone()
        if cur is None:
            continue
        if cur["attempts"] != n:
            new_status = cur["status"]
            # If we're freeing a shelve cascaded from spurious failures,
            # revive the goal so the next dispatch can resume.
            from .dispatcher import SHELVE_THRESHOLD as _ST
            if cur["status"] == "shelved" and n < _ST:
                new_status = "open"
            conn.execute(
                "UPDATE goals SET attempts = ?, status = ?, updated_at = ?"
                " WHERE id = ?", (n, new_status, db.now(), gid))
            n_recomp += 1
    conn.commit()
    print(f"OK: soft-reset {problem}")
    print(f"  deleted {n_da} spurious dead_attempts + {n_pl} pipelines")
    print(f"  recomputed attempts on {n_recomp} goal(s)")
    return 0


def _robust_unlink(path: Path, retries: int = 5,
                   backoff_s: float = 0.5) -> bool:
    """Unlink with retry-on-OSError. Windows file locks (orphan
    lean/lake/claude holding handles after a kill) usually clear
    within 1-2s; we retry up to ~5×0.5s = 2.5s before giving up.
    Returns True on success, False on persistent failure."""
    import time
    for attempt in range(retries):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            if attempt + 1 < retries:
                time.sleep(backoff_s)
    # Final attempt — let the exception escape so caller sees it
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _robust_rmtree(path: Path, retries: int = 5,
                   backoff_s: float = 0.5) -> bool:
    """Like _robust_unlink but for directories. shutil.rmtree on
    Windows can hit transient locks too (especially if files inside
    are still being written by a dying process)."""
    import shutil
    import time
    for attempt in range(retries):
        try:
            shutil.rmtree(path, ignore_errors=False)
            return True
        except OSError:
            if attempt + 1 < retries:
                time.sleep(backoff_s)
    try:
        shutil.rmtree(path, ignore_errors=False)
        return True
    except OSError:
        return False


def cmd_reset(args: argparse.Namespace) -> int:
    """Wipe one Problem's DB rows + on-disk proof files + Root.lean back
    to sorry-stub form. Manifest.md / Defs.lean / lean files outside
    `Problems/<p>/proofs/` untouched. Idempotent — running on a clean
    Problem yields the same `OK` output without errors.

    Does NOT touch `.attempts/` (per-pipeline ephemeral state, possibly
    in-flight when other Problems are running). If the problem's daemon
    is dead, the operator can `rm -rf .attempts/` separately.

    `--soft`: skip the file/DB wipe; just clear spurious dead_attempts
    (spawn_fast_fail bursts) + revive cascade victims. Use after an
    F46 quota-exhaust incident.

    Refuses to reset if no Manifest.md exists (signals user typo).
    """
    if getattr(args, "soft", False):
        return _soft_reset(args.problem)

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
    # dead_attempts.pipeline_id has an FK to pipelines, so dead_attempts
    # must be wiped before the matching pipelines rows.
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
    # Clean pipelines targeting this problem's now-deleted goals /
    # strategies. Without this, pipelines accumulates orphan rows
    # whose target_id no longer resolves — confuses forensics queries
    # and any future pipeline → strategy / goal joins.
    if gids:
        ph = ",".join("?" * len(gids))
        conn.execute(
            f"DELETE FROM pipelines WHERE target_kind='Goal' "
            f"AND target_id IN ({ph})", [str(g) for g in gids])
    if sids:
        ph = ",".join("?" * len(sids))
        conn.execute(
            f"DELETE FROM pipelines WHERE target_kind='Strategy' "
            f"AND target_id IN ({ph})", [str(s) for s in sids])
    conn.execute("DELETE FROM problems WHERE name = ?", (problem,))
    conn.commit()

    # Filesystem cleanup. Robust against Windows file locks (orphan
    # claude/lean process tree from a previously-killed daemon may
    # still hold handles for a few seconds). Two failure modes from the
    # original try/except OSError: pass:
    #   1. silent: user sees "0 proof file(s) removed" but stale L_*.lean
    #      / _strategy_*.lean stay → next dispatch sees inconsistent state
    #   2. ambiguous: same message regardless of whether deletion really
    #      happened or was blocked
    # Fix: retry with backoff (file locks usually clear in 1-2s after
    # holder dies), then RAISE on persistent failure so the operator
    # knows to kill the holder rather than silently inheriting stale
    # state. See docs/CLAUDE.md rule 9 (root-cause vs patch-around).
    proofs_dir = pdir / "proofs"
    deleted_files: list[str] = []
    failed_files: list[str] = []
    if proofs_dir.exists():
        for pattern in ("L_*.lean", "_strategy_*.lean"):
            for f in proofs_dir.glob(pattern):
                if _robust_unlink(f):
                    deleted_files.append(f.name)
                else:
                    failed_files.append(f.name)

    # Sweep workspace-root gateway artifacts (Phase 1+ gateway leaves
    # `_gateway_slot_<i>.lean` per worker, `_gateway_smoke_*.lean` from
    # cold start, `_axiom_probe_*.lean` from in-flight axiom checks).
    # When the daemon dies hard these stay; reset is the canonical
    # cleanup point.
    for pattern in ("_gateway_slot_*.lean", "_gateway_smoke_*.lean",
                     "_axiom_probe_*.lean"):
        for f in workspace.glob(pattern):
            if _robust_unlink(f):
                deleted_files.append(f.name)
            else:
                failed_files.append(f.name)

    # Drop per-problem artifacts that aren't in proofs/:
    #   - TREE.md: live tree rendering; goal rows gone → render
    #     would say "no root goal" anyway
    #   - LESSONS.md: Phase 7 reflection cache (accumulated
    #     Builder/Backward postmortems). Reset wipes the goal tree,
    #     so lessons from a structurally-different prior decomposition
    #     would pre-bias the next agent's reasoning
    #   - Root.lean.backup: spawn-side snapshot from in-pipeline retry
    #     path; only an unclean shutdown leaves it behind
    # BRIEF.md is intentionally NOT swept — it's auto-regenerated at
    # daemon startup from Manifest+Library.
    for name in ("TREE.md", "LESSONS.md", "Root.lean.backup"):
        p = pdir / name
        if p.exists():
            if _robust_unlink(p):
                deleted_files.append(name)
            else:
                failed_files.append(name)

    # Drop .drafts/ (F55 — postmortem progress notes from prior
    # timed-out spawns). Reset is meant to wipe state for a clean
    # baseline run; carrying over partial sketches would pre-bias a
    # clean reset.
    drafts_dir = pdir / ".drafts"
    if drafts_dir.exists():
        if not _robust_rmtree(drafts_dir):
            failed_files.append(".drafts/")

    if failed_files:
        print(f"FAIL: reset {problem}: could not remove "
              f"{len(failed_files)} file(s) after retries:",
              file=sys.stderr)
        for name in failed_files:
            print(f"  - {name}", file=sys.stderr)
        print("Cause is usually a stale claude/lean/lake process "
              "holding the file. Kill any running daemon and orphan "
              "lake/lean process tree, then retry.",
              file=sys.stderr)
        return 2

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

    # Post-reset verification: scan the directories we cleaned and
    # raise loudly if anything we expected gone is still there. This
    # catches both "_robust_unlink reported success but file came
    # back" (race against a process still spawning) and any pattern
    # we forgot to sweep.
    leftovers: list[str] = []
    if proofs_dir.exists():
        for pattern in ("L_*.lean", "_strategy_*.lean"):
            for f in proofs_dir.glob(pattern):
                leftovers.append(f"proofs/{f.name}")
    for name in ("LESSONS.md", "Root.lean.backup", "TREE.md"):
        if (pdir / name).exists():
            leftovers.append(name)
    for pattern in ("_gateway_slot_*.lean", "_gateway_smoke_*.lean",
                     "_axiom_probe_*.lean"):
        for f in workspace.glob(pattern):
            leftovers.append(f.name)
    if leftovers:
        print(f"FAIL: reset {problem}: cleanup verified, but these "
              f"files reappeared / weren't matched:",
              file=sys.stderr)
        for name in leftovers:
            print(f"  - {name}", file=sys.stderr)
        return 2

    print(f"OK: reset {problem}")
    print(f"  DB rows: {len(gids)} goals, {len(sids)} strategies cleared")
    print(f"  Files: {len(deleted_files)} file(s) removed; Root.lean reset")
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


def cmd_doctor(args: argparse.Namespace) -> int:
    """Pre-flight diagnostic. Checks the toolchain (claude / gemini /
    lake), the Asterism.yaml config, every initialized Problem's
    Manifest, and on-disk state (`.attempts/` zombies + log retention).
    Output is icon-prefixed lines (`OK / FAIL / WARN`) the operator —
    or a future Claude session — can scan top to bottom.

    Exits 0 if every check is OK or WARN; 1 if any FAIL fired."""
    import shutil
    import subprocess

    workspace = Path.cwd()
    fails = 0

    def line(status: str, msg: str) -> None:
        nonlocal fails
        if status == "FAIL":
            fails += 1
        print(f"  [{status:>4}] {msg}")

    print("\n=== External tools ===")
    # Claude CLI
    if shutil.which("claude"):
        try:
            r = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"claude  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"claude --version timed out or errored: {exc}")
    else:
        line("WARN", "claude CLI not on PATH (Claude provider unavailable)")

    # Gemini CLI — use the same Windows-aware resolver the provider does
    # (npm ships gemini as a bash shim + gemini.cmd; subprocess.run on
    # Windows can only launch the .cmd).
    from .llm.gemini_cli import resolve_gemini_executable
    gemini_exe = resolve_gemini_executable()
    if gemini_exe:
        try:
            r = subprocess.run(
                [gemini_exe, "--version"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"gemini  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"gemini --version timed out or errored: {exc}")
    else:
        line("WARN", "gemini CLI not on PATH (Gemini provider unavailable)")

    # Lake (Lean build tool)
    if shutil.which("lake"):
        try:
            r = subprocess.run(
                ["lake", "env", "lean", "--version"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"lake env lean  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"lake env lean errored: {exc}")
    else:
        line("FAIL", "lake not on PATH — cannot build Lean (mandatory)")

    # Asterism.yaml
    print("\n=== Asterism.yaml ===")
    cfg_path = workspace / "Asterism.yaml"
    if not cfg_path.exists():
        line("WARN", f"{cfg_path.name} absent — using built-in defaults "
                     f"(see docs/architecture.md §10 for schema)")
    else:
        try:
            from . import config as _config
            _config._reset_cache()
            data = _config.load(workspace)
            keys = []
            for top in ("dispatch", "builder", "backward"):
                if top in data and isinstance(data[top], dict):
                    keys.append(f"{top}({len(data[top])})")
            line("OK", f"{cfg_path.name}: " + ", ".join(keys)
                       if keys else f"{cfg_path.name}: empty / no known sections")
        except Exception as exc:
            line("FAIL", f"{cfg_path.name} parse error: {exc}")

    # Problems
    print("\n=== Problems ===")
    conn = db.connect()
    db.init_schema(conn)
    rows = conn.execute(
        "SELECT name, manifest_path FROM problems ORDER BY name"
    ).fetchall()
    if not rows:
        line("WARN", "no problems initialized — run `asterism init <p>`")
    for r in rows:
        name = r["name"]
        mfst_path = workspace / r["manifest_path"]
        if not mfst_path.exists():
            line("FAIL", f"{name}: Manifest.md missing at {r['manifest_path']}")
            continue
        try:
            mfst = manifest.parse(mfst_path)
            if not mfst.statement:
                line("FAIL", f"{name}: Manifest.md has no `## Statement` section")
                continue
        except Exception as exc:
            line("FAIL", f"{name}: Manifest parse error: {exc}")
            continue
        # Root goal status
        root = conn.execute(
            "SELECT id, status, attempts FROM goals "
            "WHERE problem = ? AND slug = 'main'", (name,)
        ).fetchone()
        if root:
            line("OK", f"{name}: root goal id={root['id']} "
                       f"status={root['status']} attempts={root['attempts']}")
        else:
            line("WARN", f"{name}: registered but no root goal "
                         f"(re-run `asterism init {name}`)")

    # Filesystem state
    print("\n=== Filesystem state ===")
    attempts_dir = workspace / ".attempts"
    if attempts_dir.exists():
        n = sum(1 for _ in attempts_dir.iterdir())
        if n > 5:
            line("WARN", f".attempts/ has {n} dirs — likely zombies, "
                         f"`rm -rf .attempts/` after killing daemon")
        elif n:
            line("OK", f".attempts/ has {n} dir(s) — possibly live or recent")
        else:
            line("OK", ".attempts/ empty")
    else:
        line("OK", ".attempts/ does not exist (clean state)")

    log_dir = workspace / LOG_DIR
    if log_dir.exists():
        logs = list(log_dir.glob("*.log"))
        total = sum(p.stat().st_size for p in logs) if logs else 0
        line("OK", f".asterism/logs/  {len(logs)} file(s), "
                   f"{total // 1024} KB")

    print()
    print(f"=== Summary: {fails} FAIL ===" if fails else
          "=== Summary: all checks passed (some WARN OK) ===")
    return 0 if fails == 0 else 1


def cmd_logs(args: argparse.Namespace) -> int:
    """P2-#5: list / tail framework run logs from `.asterism/logs/`.
    Default: list with sizes, mtime, sorted newest first.
    `--tail N`: print the last N lines of the most recent log.
    """
    workspace = Path.cwd()
    log_dir = workspace / LOG_DIR
    if not log_dir.exists():
        print(f"no log dir at {log_dir}")
        return 0
    logs = sorted(log_dir.glob("*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print(f"no logs in {log_dir}")
        return 0
    if args.tail:
        latest = logs[0]
        print(f"# {latest.name}  ({latest.stat().st_size:,} bytes)")
        with latest.open("r", encoding="utf-8", errors="replace") as f:
            tail_lines = f.readlines()[-args.tail:]
        sys.stdout.writelines(tail_lines)
        return 0
    print(f"# {log_dir} ({len(logs)} logs)")
    for p in logs:
        st = p.stat()
        ts = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {st.st_size:>8,} B  {ts}  {p.name}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """P2-#5: print the resolved Asterism config — what `dispatch.*`,
    `builder.*`, `backward.*` actually evaluate to right now (env >
    Asterism.yaml > legacy env > built-in default). Eliminates
    "what's actually active?" confusion when env vars + yaml + defaults
    interact.
    """
    from . import config as _cfg
    from .llm import claude_cli as _cc
    rows = [
        ("dispatch.pool",
         _cfg.get("dispatch.pool", env_var="ASTERISM_POOL", default=12, cast=int)),
        ("dispatch.budget_sec",
         _cfg.get("dispatch.budget_sec", env_var="ASTERISM_BUDGET_SEC",
                  default=1800, cast=int)),
        ("dispatch.shelve_threshold",
         _cfg.get("dispatch.shelve_threshold",
                  env_var="ASTERISM_SHELVE_THRESHOLD", default=8, cast=int)),
        ("builder.threshold",
         _cfg.get("builder.threshold",
                  legacy_env=("ASTERISM_BUILDER_THRESHOLD",),
                  default=_cfg.get("dispatch.builder_threshold", default=3, cast=int),
                  cast=int)),
        ("builder.model", _cc.resolve_model("builder")),
        ("backward.model", _cc.resolve_model("backward")),
    ]
    for k, v in rows:
        print(f"  {k:<30} = {v}")
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
    p_reset.add_argument(
        "--soft", action="store_true",
        help="surgical: only clear spurious dead_attempts + revive "
             "cascade victims (use after F46 quota-exhaust incident)",
    )
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

    p_doctor = sub.add_parser(
        "doctor",
        help="pre-flight: tools / Asterism.yaml / Manifests / .attempts state",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    p_prune = sub.add_parser(
        "prune",
        help="GC orphan lean files in proofs/ (auto-runs on successful run)",
    )
    p_prune.add_argument("problem", nargs="?",
                         help="optional; default = all problems")
    p_prune.add_argument("--dry-run", action="store_true",
                         help="list files without deleting")
    p_prune.set_defaults(func=cmd_prune)

    p_logs = sub.add_parser(
        "logs",
        help="list / tail framework run logs (.asterism/logs/)",
    )
    p_logs.add_argument("--tail", type=int, metavar="N",
                        help="print last N lines of the most recent log "
                             "instead of listing")
    p_logs.set_defaults(func=cmd_logs)

    p_config = sub.add_parser(
        "config",
        help="print resolved Asterism config (env > yaml > legacy > default)",
    )
    p_config.set_defaults(func=cmd_config)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
