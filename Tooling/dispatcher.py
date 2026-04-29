"""Main dispatcher loop. Cascade in main thread, pipelines in pool.

See architecture.md §7-§8.
"""
from __future__ import annotations

import os
import sqlite3
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

from . import agent, db, manifest, pipeline, prune


SHELVE_THRESHOLD = 7
TICK_TIMEOUT = 30  # seconds
OR_FANOUT_DEFAULT = 3  # max concurrent Backwards per open goal (env override)


# ---------------------------------------------------------------------
# Startup recovery
# ---------------------------------------------------------------------

def _recover_at_startup(conn: sqlite3.Connection) -> None:
    """Sweep transient state left by a crashed prior daemon.

    Three classes of stale state, each restored to a consistent baseline:

      1. queue rows         — live dispatch state, never persists across
                              daemon lifetimes; clear unconditionally.
      2. half-baked strategies — INSERTed by run_backward then crashed
                              before UPDATE scratch_path; status stayed
                              'proposed' with empty path. Mark 'dead'.
      3. stuck-attempting goals — Backward succeeded last run, but no
                              'proposed' strategy survives now (all dead/
                              superseded). Reset to 'open' so bfs_refill
                              can dispatch a fresh Backward.

    Orphan lean files in proofs/ are NOT touched here — they're handled
    by the post-success reconcile + prune path.
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

    if queue_cleared or strategies_killed or goals_reopened:
        print(f"[dispatcher] recovery: cleared {queue_cleared} queue rows, "
              f"killed {strategies_killed} half-baked strategies, "
              f"reopened {goals_reopened} stuck goals", flush=True)


def next_worker_kind(goal: sqlite3.Row) -> str:
    """Pure: input goal row → 'Builder' or 'Backward'."""
    if int(goal["difficulty"]) >= 4:
        return "Backward"
    if int(goal["attempts"]) <= 2:
        return "Builder"
    return "Backward"


# ---------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------

def cascade_one(conn: sqlite3.Connection, *, pipeline_id: str,
                kind: str, target_id: str, target_kind: str,
                outcome: str) -> None:
    """Apply state transitions for one finished pipeline.

    Each worker_kind has a fixed target_kind:
      Builder  → Goal   (fresh sorry-stub closure)
      Backward → Goal   (decompose into sub-goals)
      Verify   → Strategy (re-run lake build after sub-goals proved)

    No-op entry: if the target's underlying goal is already proved or
    its strategy is already 'superseded', skip the transition. This
    catches loser strategies / orphan sub-goals whose workers finish
    after a sibling has won (OR parallelism).
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
    elif target_kind == "Goal":
        row = conn.execute(
            "SELECT status FROM goals WHERE id = ?", (int(target_id),),
        ).fetchone()
        if row and row["status"] == "proved":
            return

    if kind == "Builder":
        if outcome == "proved":
            db.update_goal_status(conn, int(target_id), "proved")
            return
        if outcome in ("exhausted", "failed"):
            n = db.increment_goal_attempts(conn, int(target_id))
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, int(target_id), "shelved")
            return

    if kind == "Backward":
        if outcome == "success":
            db.update_goal_status(conn, int(target_id), "attempting")
            return
        # exhausted / failed
        n = db.increment_goal_attempts(conn, int(target_id))
        if n >= SHELVE_THRESHOLD:
            db.update_goal_status(conn, int(target_id), "shelved")
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
            return
        # exhausted / failed
        db.update_strategy_status(conn, int(target_id), "dead")
        if goal_id is not None:
            n = db.increment_goal_attempts(conn, goal_id)
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, goal_id, "shelved")
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
    pool_size = int(os.environ.get("ASTERISM_POOL", "4"))
    budget_sec = int(os.environ.get("ASTERISM_BUDGET_SEC", "1800"))
    or_fanout = int(os.environ.get("ASTERISM_OR_FANOUT",
                                   str(OR_FANOUT_DEFAULT)))
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

    _recover_at_startup(conn)

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
                                target_id=tid, target_kind=tk, outcome=outcome)
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


