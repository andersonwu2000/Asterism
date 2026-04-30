"""Main dispatcher loop. Cascade in main thread, pipelines in pool.

See architecture.md §7-§8.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

from . import agent, db, manifest, pipeline, playbook, prune


# Per-model defaults (F31). Empirically:
#   Sonnet/Opus rarely succeed at attempts ≥3 — 97% of proves happen
#                in ≤3 Builder fails. Tighten to 3/7 to skip the
#                wasted attempts 4-5 (each costs claude thinking +
#                potentially a 600s CLI timeout).
#   Haiku       iterates productively across more attempts (its
#                training memory of Mathlib API specifics is thinner;
#                F20 + F22 + retries lets it converge given enough
#                budget). Keep 5/8.
#
# Semantics:
#   BUILDER_THRESHOLD = N → first N attempts (0..N-1) dispatch Builder,
#                          attempts >= N dispatch Backward.
#   SHELVE_THRESHOLD = M  → goal shelves once attempts hits M.
# Both env-overridable: ASTERISM_BUILDER_THRESHOLD / ASTERISM_SHELVE_THRESHOLD.
_STRONG_DEFAULTS = (3, 7)
_WEAK_DEFAULTS = (5, 8)


def _model_aware_thresholds() -> tuple[int, int]:
    """Pick (BUILDER, SHELVE) defaults based on ASTERISM_AGENT_MODEL.
    Substring 'haiku' (case-insensitive) selects weak-tier defaults;
    everything else (sonnet, opus, future strong models, unset) gets
    strong-tier."""
    model = os.environ.get("ASTERISM_AGENT_MODEL", "").lower()
    if "haiku" in model:
        return _WEAK_DEFAULTS
    return _STRONG_DEFAULTS


# Module-level mutable knobs — read at use sites so env override
# (set in `run`) takes effect.
BUILDER_THRESHOLD, SHELVE_THRESHOLD = _model_aware_thresholds()

TICK_TIMEOUT = 30  # seconds
OR_FANOUT_DEFAULT = 2  # max concurrent Backwards per open goal (env override)


# ---------------------------------------------------------------------
# Startup recovery
# ---------------------------------------------------------------------

def _recover_at_startup(conn: sqlite3.Connection,
                        workspace: Path | None = None) -> None:
    """Sweep transient state left by a crashed prior daemon.

    Five classes of stale state, each restored to a consistent baseline:

      1. queue rows         — live dispatch state, never persists across
                              daemon lifetimes; clear unconditionally.
      2. half-baked strategies — INSERTed by run_backward then crashed
                              before UPDATE scratch_path; status stayed
                              'proposed' with empty path. Mark 'dead'.
      3. stuck-attempting goals — Backward succeeded last run, but no
                              'proposed' strategy survives now (all dead/
                              superseded). Reset to 'open' so bfs_refill
                              can dispatch a fresh Backward.
      4. orphan .attempts/<pid>/ dirs — daemon SIGKILL bypasses
                              WorkArea.__exit__, and child claude
                              subprocesses can keep writing to a dead
                              parent's sandbox.
      5. orphan .lean.{backup,verify_backup,tmp} files — Builder/Verify
                              died mid-write, leaving the original next
                              to a half-applied patch (or vice versa).
                              Restore from backup unless DB shows the
                              corresponding goal already proved (race
                              window between lake-build success and
                              backup.unlink); then just delete.

    Skip filesystem sweeps if workspace is None (test fixtures call
    DB-only). Orphan lean files placed by killed Backward in proofs/
    are NOT touched here — they're handled by the post-success
    reconcile + prune path.
    """
    queue_cleared = conn.execute("DELETE FROM queue").rowcount

    strategies_killed = conn.execute(
        "UPDATE strategies SET status = 'dead'"
        " WHERE status = 'proposed' AND scratch_path = ''"
    ).rowcount

    goals_reopened = conn.execute(
        "UPDATE goals SET status = 'open', updated_at = ?"
        " WHERE status = 'attempting'"
        "   AND NOT EXISTS ("
        "     SELECT 1 FROM strategies"
        "     WHERE goal_id = goals.id AND status = 'proposed'"
        "   )",
        (db.now(),),
    ).rowcount

    conn.commit()

    attempts_cleared = 0
    backups_handled = 0
    tmps_removed = 0
    if workspace is not None:
        attempts_root = workspace / ".attempts"
        if attempts_root.exists():
            for d in attempts_root.iterdir():
                if d.is_dir():
                    try:
                        shutil.rmtree(d)
                        attempts_cleared += 1
                    except OSError:
                        pass  # claude subprocess may still hold a handle

        backups_handled, tmps_removed = _sweep_lean_backups(conn, workspace)

    if (queue_cleared or strategies_killed or goals_reopened
            or attempts_cleared or backups_handled or tmps_removed):
        print(f"[dispatcher] recovery: cleared {queue_cleared} queue rows, "
              f"killed {strategies_killed} half-baked strategies, "
              f"reopened {goals_reopened} stuck goals, "
              f"removed {attempts_cleared} orphan attempts dirs, "
              f"handled {backups_handled} lean backups, "
              f"removed {tmps_removed} stale .tmp files",
              flush=True)


def _sweep_lean_backups(conn: sqlite3.Connection,
                        workspace: Path) -> tuple[int, int]:
    """Restore or discard `*.lean.{backup,verify_backup}` and remove
    `*.lean.tmp` files left by killed Builder/Verify pipelines.

    Decision per backup file:
      - If the corresponding goal in DB is already 'proved', the daemon
        died in the microsecond window between lake-build success and
        backup.unlink. The current .lean is the validated proof; just
        unlink the backup (do NOT restore — would discard the proof).
      - Otherwise (goal still 'open' / 'attempting' / 'shelved'), the
        pipeline did not commit success. Restore .lean from backup,
        then unlink the backup.

    .tmp files (Verify's atomic-write candidate) are always removed
    unread — partial content, never safe to use.
    """
    backups_handled = 0
    tmps_removed = 0
    problems_root = workspace / "Problems"
    if not problems_root.exists():
        return 0, 0

    # Build (lean_path → goal status) map for quick lookup
    goal_status = {
        r["lean_path"]: r["status"]
        for r in conn.execute("SELECT lean_path, status FROM goals")
    }

    for ext in (".backup", ".verify_backup"):
        for backup in problems_root.glob(f"**/*.lean{ext}"):
            original = backup.with_suffix("")  # strips just last suffix
            try:
                rel = original.relative_to(workspace).as_posix()
            except ValueError:
                rel = ""
            status = goal_status.get(rel)
            try:
                if status == "proved":
                    # Lake-build success was committed; backup is leftover
                    # from the race window. Just discard.
                    backup.unlink()
                else:
                    # Pipeline didn't commit success; restore safe state.
                    shutil.copy2(backup, original)
                    backup.unlink()
                backups_handled += 1
            except OSError:
                pass

    for tmp in problems_root.glob("**/*.lean.tmp"):
        try:
            tmp.unlink()
            tmps_removed += 1
        except OSError:
            pass

    return backups_handled, tmps_removed


def _propagate_shelve(conn: sqlite3.Connection, goal_id: int) -> None:
    """Cascade a goal-shelve event in two directions:

    Upward (F12): every parent strategy that still depends on this goal
    as a sub-goal can never become ready_for_verify (requires all
    sub-goals 'proved'). Kill those proposed strategies; for each
    affected parent goal, if no live strategy survives, reopen it
    (mirrors W4 reopen rule).

    Inward (F16): strategies for proving the just-shelved goal are now
    moot. Kill them as well. Their sub-goals become orphans — `open_goals`
    walks the alive-strategy DAG and excludes them from dispatch, so no
    further cleanup is required.

    Iterative — a re-opened parent goal may shelve later via its own
    increment_goal_attempts path; we don't recurse here.
    """
    # F12 — kill strategies USING this goal as a sub-goal
    parent_strategies = conn.execute(
        "SELECT s.id, s.goal_id FROM strategies s "
        "JOIN strategy_subgoals ss ON ss.strategy_id = s.id "
        "WHERE ss.subgoal_id = ? AND s.status = 'proposed'",
        (goal_id,),
    ).fetchall()

    for s in parent_strategies:
        db.update_strategy_status(conn, int(s["id"]), "dead")

    # For each affected parent goal, mirror the W4 reopen rule: if no
    # 'proposed' strategy survives, transition 'attempting' → 'open'.
    affected_parent_goals = {int(s["goal_id"]) for s in parent_strategies}
    for gid in affected_parent_goals:
        has_live = conn.execute(
            "SELECT 1 FROM strategies WHERE goal_id = ?"
            " AND status = 'proposed' LIMIT 1",
            (gid,),
        ).fetchone()
        if has_live is None:
            row = conn.execute(
                "SELECT status FROM goals WHERE id = ?", (gid,),
            ).fetchone()
            if row and row["status"] == "attempting":
                db.update_goal_status(conn, gid, "open")

    # F16 — kill strategies whose parent goal IS this shelved goal
    conn.execute(
        "UPDATE strategies SET status='dead' "
        "WHERE goal_id = ? AND status='proposed'",
        (goal_id,),
    )


def next_worker_kind(goal: sqlite3.Row) -> str:
    """Pure-ish: input goal row → 'Builder' or 'Backward'.

    `BUILDER_THRESHOLD` is module-level so test/env overrides are
    visible without re-importing.
    """
    if int(goal["difficulty"]) >= 4:
        return "Backward"
    if int(goal["attempts"]) < BUILDER_THRESHOLD:
        return "Builder"
    return "Backward"


# ---------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------

def cascade_one(conn: sqlite3.Connection, *, pipeline_id: str,
                kind: str, target_id: str, target_kind: str,
                outcome: str,
                workspace: Path | None = None) -> None:
    """Apply state transitions for one finished pipeline.

    Each worker_kind has a fixed target_kind:
      Builder  → Goal   (fresh sorry-stub closure)
      Backward → Goal   (decompose into sub-goals)
      Verify   → Strategy (re-run lake build after sub-goals proved)

    No-op entry: if the target's underlying goal is already proved or
    its strategy is already 'superseded', skip the transition. This
    catches loser strategies / orphan sub-goals whose workers finish
    after a sibling has won (OR parallelism).

    `workspace` enables the F22 playbook hook on Verify=proved. Tests
    that don't care about file-side effects pass None.
    """
    if target_kind == "Strategy":
        row = conn.execute(
            "SELECT s.status, g.status AS goal_status FROM strategies s"
            " JOIN goals g ON g.id = s.goal_id WHERE s.id = ?",
            (int(target_id),),
        ).fetchone()
        if row:
            if row["status"] == "superseded":
                return
            if row["goal_status"] == "proved":
                # Sibling won the OR race; finalize this strategy as
                # superseded so bfs_refill stops considering it ready.
                if row["status"] == "proposed":
                    db.update_strategy_status(conn, int(target_id),
                                              "superseded")
                return
            if row["goal_status"] == "shelved":
                # F24 — parent goal was shelved while this strategy's
                # pipeline was in flight. Strategy is moot; mark dead so
                # invariant `proposed → parent alive` holds.
                if row["status"] == "proposed":
                    db.update_strategy_status(conn, int(target_id),
                                              "dead")
                return
    elif target_kind == "Goal":
        row = conn.execute(
            "SELECT status FROM goals WHERE id = ?", (int(target_id),),
        ).fetchone()
        # F24 — once a goal reaches a terminal state (proved/shelved),
        # late cascades from in-flight pipelines must not mutate it.
        # Without the 'shelved' guard, a Backward 'success' that races
        # past the shelve transition would unconditionally flip status
        # back to 'attempting' (observed: goal stuck at attempts=N with
        # status='attempting' instead of 'shelved').
        if row and row["status"] in ("proved", "shelved"):
            return

    if kind == "Builder":
        if outcome == "proved":
            db.update_goal_status(conn, int(target_id), "proved")
            return
        if outcome in ("exhausted", "failed"):
            n = db.increment_goal_attempts(conn, int(target_id))
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, int(target_id), "shelved")
                _propagate_shelve(conn, int(target_id))
            return

    if kind == "Backward":
        if outcome == "success":
            db.update_goal_status(conn, int(target_id), "attempting")
            return
        # exhausted / failed
        n = db.increment_goal_attempts(conn, int(target_id))
        if n >= SHELVE_THRESHOLD:
            db.update_goal_status(conn, int(target_id), "shelved")
            _propagate_shelve(conn, int(target_id))
        return

    if kind == "Verify":
        row = conn.execute(
            "SELECT goal_id FROM strategies WHERE id = ?",
            (int(target_id),),
        ).fetchone()
        goal_id = int(row["goal_id"]) if row else None
        if outcome == "proved":
            db.update_strategy_status(conn, int(target_id), "succeeded")
            if goal_id is not None:
                db.update_goal_status(conn, goal_id, "proved")
                # OR parallelism: sibling strategies of this goal lose;
                # mark them superseded so their orphan sub-goals stop
                # being dispatched (open_goals filter).
                db.mark_other_strategies_superseded(
                    conn, goal_id=goal_id, winner_id=int(target_id),
                )
            # F22 — capture the just-proven idiom into the per-problem
            # playbook. Synchronous (~30-60s LLM call) but only fires
            # on Verify=proved, which is rare. Failures are logged and
            # never propagate.
            if workspace is not None:
                playbook.maybe_record_idiom(
                    int(target_id), conn, workspace)
            return
        # exhausted / failed
        db.update_strategy_status(conn, int(target_id), "dead")
        if goal_id is not None:
            n = db.increment_goal_attempts(conn, goal_id)
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, goal_id, "shelved")
                _propagate_shelve(conn, goal_id)
                return
            # Re-open the goal if no live strategy remains, so bfs_refill
            # can dispatch a new Backward attempt. Without this the goal
            # is stuck in 'attempting' forever after the last verify fails.
            has_live = conn.execute(
                "SELECT 1 FROM strategies WHERE goal_id = ?"
                " AND status = 'proposed' LIMIT 1",
                (goal_id,),
            ).fetchone()
            if has_live is None:
                db.update_goal_status(conn, goal_id, "open")
        return


# ---------------------------------------------------------------------
# BFS queue refill
# ---------------------------------------------------------------------

def bfs_refill(conn: sqlite3.Connection,
               running: set[tuple[str, str, str]],
               *, or_fanout: int = OR_FANOUT_DEFAULT) -> None:
    """Enqueue dispatchable tasks. `running` is the in-memory live set
    (target_id, kind, pipeline_id) of pipelines currently executing in
    this daemon — pipeline_id makes each entry unique under OR parallelism
    (multiple Backwards on the same goal). Daemon crash → set vanishes;
    pipelines table only holds finished rows so restart is clean.

    OR parallelism: per (goal, Backward) pair we allow up to `or_fanout`
    concurrent attempts (running + queued). Builder/Verify keep cap=1.
    """
    def in_flight(tid: str, kind: str) -> int:
        running_n = sum(1 for (t, k, _) in running if t == tid and k == kind)
        return running_n + db.queue_count(conn, target_id=tid, kind=kind)

    # Strategies with all sub-goals proved → enqueue Verify (cap 1)
    for s in db.strategies_ready_for_verify(conn):
        sid = str(s["id"])
        if in_flight(sid, "Verify") == 0:
            db.enqueue(conn, kind="Verify", target_id=sid, priority=10)

    # Open goals → fill up to per-kind cap
    for g in db.open_goals(conn):
        gid = str(g["id"])
        kind = next_worker_kind(g)
        cap = or_fanout if kind == "Backward" else 1
        slots = cap - in_flight(gid, kind)
        priority = 5 if kind == "Builder" else 2
        for _ in range(max(0, slots)):
            db.enqueue(conn, kind=kind, target_id=gid, priority=priority)


# ---------------------------------------------------------------------
# Worker thread body
# ---------------------------------------------------------------------

def _run_pipeline(workspace: Path, manifests: dict[str, manifest.Manifest],
                  task_kind: str, target_id: str, target_kind: str,
                  pipeline_id: str) -> tuple[str, str, str, str, str]:
    """Run one pipeline in worker thread. Returns (pipeline_id, kind, target_id,
    target_kind, outcome).

    Side effects:
      - INSERT one finished pipeline row (succeeded/failed)
      - On failure: INSERT dead_attempt row with full artifacts JSON
      - Always rmtree .attempts/<pid>/ + .attempts/_backup_<pid>/ via WorkArea

    NB: opens its own DB conn (sqlite3 thread safety)."""
    import json as _json
    conn = db.connect()
    started_at = db.now()
    try:
        with agent.WorkArea(workspace, pipeline_id) as wa:
            attempts_dir = wa.attempts

            # Resolve which goal this task concerns. Verify targets a
            # Strategy whose parent goal supplies the problem name.
            if target_kind == "Strategy":
                row = conn.execute(
                    "SELECT goal_id FROM strategies WHERE id = ?",
                    (int(target_id),),
                ).fetchone()
                goal_id = int(row["goal_id"]) if row else 0
            else:
                goal_id = int(target_id)

            goal = db.get_goal(conn, goal_id)
            if goal is None:
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status="failed", outcome="failed",
                    started_at=started_at,
                )
                return (pipeline_id, task_kind, target_id, target_kind, "failed")

            mfst = manifests[goal["problem"]]

            if task_kind == "Verify":
                r = pipeline.run_verify(
                    conn, strategy_id=int(target_id), workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                )
            elif task_kind == "Builder":
                r = pipeline.run_builder(
                    conn, goal_id=goal_id, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                )
            elif task_kind == "Backward":
                r = pipeline.run_backward(
                    conn, goal_id=goal_id, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                )
            else:
                r = pipeline.PipelineResult(outcome="failed",
                                            failure_reason="unknown_kind")

            status = "succeeded" if r.outcome in ("proved", "success") else "failed"
            db.record_pipeline(
                conn, pipeline_id=pipeline_id, kind=task_kind,
                target_id=target_id, target_kind=target_kind,
                status=status, outcome=r.outcome,
                started_at=started_at,
            )

            # Capture artifacts from .attempts/<pid>/ before WorkArea rmtree.
            # 'superseded' isn't a real failure (just OR race noise), don't
            # pollute dead_attempts with it.
            if r.failure_reason and r.failure_reason != "superseded":
                artifacts = pipeline._collect_artifacts(attempts_dir)
                tk = target_kind
                tid = goal_id if tk == "Goal" else int(target_id)
                db.record_dead_attempt(
                    conn, target_id=tid, target_kind=tk,
                    pipeline_id=pipeline_id,
                    failure_reason=r.failure_reason,
                    failure_detail=r.failure_detail,
                    proposal_md=r.proposal_md,
                    artifacts=_json.dumps(artifacts) if artifacts else "",
                )

            return (pipeline_id, task_kind, target_id, target_kind, r.outcome)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------

def run(workspace: Path, *, once: bool = False) -> int:
    global BUILDER_THRESHOLD, SHELVE_THRESHOLD
    pool_size = int(os.environ.get("ASTERISM_POOL", "4"))
    budget_sec = int(os.environ.get("ASTERISM_BUDGET_SEC", "1800"))
    or_fanout = int(os.environ.get("ASTERISM_OR_FANOUT",
                                   str(OR_FANOUT_DEFAULT)))
    b_default, s_default = _model_aware_thresholds()
    BUILDER_THRESHOLD = int(os.environ.get(
        "ASTERISM_BUILDER_THRESHOLD", str(b_default)))
    SHELVE_THRESHOLD = int(os.environ.get(
        "ASTERISM_SHELVE_THRESHOLD", str(s_default)))
    if SHELVE_THRESHOLD <= BUILDER_THRESHOLD:
        # An invalid combo would mean Backward never gets a chance —
        # fail loudly rather than silently degrade behavior.
        raise ValueError(
            f"ASTERISM_SHELVE_THRESHOLD ({SHELVE_THRESHOLD}) must exceed "
            f"ASTERISM_BUILDER_THRESHOLD ({BUILDER_THRESHOLD}); otherwise "
            f"the goal shelves before any Backward attempt fires.")
    pool = ThreadPoolExecutor(max_workers=pool_size)
    futures: dict[Future, tuple[str, str, str, str]] = {}
    # In-memory live set of (target_id, kind, pipeline_id) currently executing
    # in this daemon. Including pipeline_id keeps multiple Backwards on the
    # same goal as distinct entries (OR parallelism). Daemon crash → set
    # vanishes → restart sees clean slate.
    running: set[tuple[str, str, str]] = set()

    conn = db.connect()
    manifests: dict[str, manifest.Manifest] = {}
    for row in conn.execute("SELECT name, manifest_path FROM problems"):
        manifests[row["name"]] = manifest.parse(workspace / row["manifest_path"])

    _recover_at_startup(conn, workspace)

    print(f"[dispatcher] start, pool={pool_size}, problems={list(manifests)}",
          flush=True)
    start_time = time.time()

    while True:
        # Cascade for any completed pipelines
        if futures:
            done, _ = wait(list(futures), timeout=0, return_when=FIRST_COMPLETED)
            for fut in done:
                meta = futures.pop(fut)
                # meta = (pipeline_id, kind, target_id, target_kind)
                running.discard((meta[2], meta[1], meta[0]))
                try:
                    pid, kind, tid, tk, outcome = fut.result()
                    cascade_one(conn, pipeline_id=pid, kind=kind,
                                target_id=tid, target_kind=tk,
                                outcome=outcome, workspace=workspace)
                    print(f"[cascade] {kind} {tk}={tid} → {outcome}", flush=True)
                except Exception as exc:
                    print(f"[cascade] worker exception: {exc}", flush=True)

        if db.root_proved(conn):
            print("[dispatcher] all roots proved", flush=True)
            for problem_name in manifests:
                # Reconcile first (fix any FILE/DB drift from OR races),
                # THEN prune (delete orphans, now safe to remove).
                repaired = prune.reconcile_proved_goals(
                    conn, workspace, problem_name)
                if repaired:
                    print(f"[reconcile] {problem_name}: repaired "
                          f"{len(repaired)} drifted files", flush=True)
                removed = prune.prune_problem(conn, workspace, problem_name)
                if removed:
                    print(f"[prune] {problem_name}: removed {len(removed)} "
                          f"orphan files", flush=True)
            pool.shutdown(wait=False, cancel_futures=True)
            return 0

        # Refill queue (uses in-memory `running` for dedup)
        bfs_refill(conn, running, or_fanout=or_fanout)

        # Spawn from queue while pool has slots. No (target_id, kind)
        # dedup here — bfs_refill is cap-aware (running + queue) and
        # OR-parallel Backwards intentionally allow multiple in flight
        # per goal.
        while len(futures) < pool_size:
            row = db.pop_queue(conn)
            if row is None:
                break
            target_id = str(row["target_id"])
            kind = str(row["kind"])
            target_kind = "Strategy" if kind == "Verify" else "Goal"
            pipeline_id = agent.new_pipeline_id()
            running.add((target_id, kind, pipeline_id))
            fut = pool.submit(_run_pipeline, workspace, manifests,
                              kind, target_id, target_kind, pipeline_id)
            futures[fut] = (pipeline_id, kind, target_id, target_kind)
            print(f"[dispatch] {kind} {target_kind}={target_id} "
                  f"pid={pipeline_id[:8]}", flush=True)

        if once and not futures and db.pop_queue(conn) is None:
            print("[dispatcher] --once and queue empty, exit")
            pool.shutdown(wait=True)
            return 0

        # Idle exit: nothing in flight, queue empty, and bfs_refill found
        # nothing to dispatch (open_goals filter excludes shelved/orphan).
        # Means we'd just spin until budget — exit instead. Distinct from
        # root_proved exit above: this fires when goals have shelved or
        # all reachable goals are dead.
        if (not futures
                and db.queue_size(conn) == 0
                and len(db.open_goals(conn)) == 0
                and len(db.strategies_ready_for_verify(conn)) == 0):
            print(f"[dispatcher] no dispatchable work, exiting "
                  f"(roots_proved={db.root_proved(conn)})", flush=True)
            pool.shutdown(wait=True)
            return 0 if db.root_proved(conn) else 1

        # Wait for any completion or tick
        if futures:
            wait(list(futures), timeout=TICK_TIMEOUT,
                 return_when=FIRST_COMPLETED)
        else:
            time.sleep(min(TICK_TIMEOUT, 5))

        if time.time() - start_time > budget_sec:
            print(f"[dispatcher] {budget_sec}s budget exceeded; stopping",
                  flush=True)
            pool.shutdown(wait=False, cancel_futures=True)
            return 1


