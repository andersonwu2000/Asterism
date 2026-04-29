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

from . import agent, db, manifest, pipeline


SHELVE_THRESHOLD = 7
TICK_TIMEOUT = 30  # seconds


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
    """Apply state transitions for one finished pipeline."""
    if kind == "Builder":
        if outcome == "proved":
            if target_kind == "Strategy":
                db.update_strategy_status(conn, int(target_id), "succeeded")
                row = conn.execute(
                    "SELECT goal_id FROM strategies WHERE id = ?",
                    (int(target_id),),
                ).fetchone()
                if row:
                    db.update_goal_status(conn, int(row["goal_id"]), "proved")
            else:
                db.update_goal_status(conn, int(target_id), "proved")
            return
        if outcome in ("exhausted", "failed"):
            if target_kind == "Strategy":
                db.update_strategy_status(conn, int(target_id), "dead")
                row = conn.execute(
                    "SELECT goal_id FROM strategies WHERE id = ?",
                    (int(target_id),),
                ).fetchone()
                if row:
                    n = db.increment_goal_attempts(conn, int(row["goal_id"]))
                    if n >= SHELVE_THRESHOLD:
                        db.update_goal_status(conn, int(row["goal_id"]), "shelved")
            else:
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


# ---------------------------------------------------------------------
# BFS queue refill
# ---------------------------------------------------------------------

def bfs_refill(conn: sqlite3.Connection,
               running: set[tuple[str, str]]) -> None:
    """Enqueue dispatchable tasks. `running` is the in-memory live set
    (target_id, kind) of pipelines currently executing in this daemon.
    Stale state from prior daemon runs lives nowhere (pipelines table only
    holds finished rows; daemon crash leaves clean slate)."""
    def already(tid: str, kind: str) -> bool:
        return ((tid, kind) in running
                or db.is_in_queue(conn, target_id=tid, kind=kind))

    # Strategies with all sub-goals proved → enqueue Builder
    for s in db.strategies_ready_for_builder(conn):
        sid = str(s["id"])
        if not already(sid, "Builder"):
            db.enqueue(conn, kind="Builder", target_id=sid, priority=10)

    # Open goals → enqueue worker_kind
    for g in db.open_goals(conn):
        gid = str(g["id"])
        kind = next_worker_kind(g)
        if not already(gid, kind):
            priority = 5 if kind == "Builder" else 2
            db.enqueue(conn, kind=kind, target_id=gid, priority=priority)


# ---------------------------------------------------------------------
# Worker thread body
# ---------------------------------------------------------------------

def _run_pipeline(workspace: Path, manifests: dict[str, manifest.Manifest],
                  task_kind: str, target_id: str, target_kind: str,
                  pipeline_id: str) -> tuple[str, str, str, str, str]:
    """Run one pipeline in worker thread. Returns (pipeline_id, kind, target_id,
    target_kind, outcome).

    Side effects (long-term cleanup design):
      - On finish: INSERT one finished pipeline row (no 'running' state in DB)
      - On failure: INSERT dead_attempt row with full artifacts JSON
      - Always: rmtree the .attempts/<pid>/ sandbox after capturing artifacts

    NB: opens its own DB conn (sqlite3 thread safety)."""
    import json as _json
    conn = db.connect()
    started_at = db.now()
    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    try:
        # Resolve goal_id (Builder may target Strategy → look up its goal_id)
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

        if task_kind == "Builder":
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

        # INSERT finished pipeline row (success or failure — uniform path).
        status = "succeeded" if r.outcome in ("proved", "success") else "failed"
        db.record_pipeline(
            conn, pipeline_id=pipeline_id, kind=task_kind,
            target_id=target_id, target_kind=target_kind,
            status=status, outcome=r.outcome,
            started_at=started_at,
        )

        # On failure: capture full artifacts from .attempts/<pid>/ before rmtree
        if r.failure_reason:
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
        # Unconditional rmtree: .attempts/<pid>/ is pure ephemeral working dir;
        # all forensic data (PROPOSAL.md, patches) is in dead_attempts.artifacts.
        try:
            if attempts_dir.exists():
                shutil.rmtree(attempts_dir)
        except OSError:
            pass
        conn.close()


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------

def run(workspace: Path, *, once: bool = False) -> int:
    pool_size = int(os.environ.get("ASTERISM_POOL", "4"))
    pool = ThreadPoolExecutor(max_workers=pool_size)
    futures: dict[Future, tuple[str, str, str, str]] = {}
    # In-memory live set of (target_id, kind) currently executing in this daemon.
    # Daemon crash → set vanishes → next start sees clean slate (no zombie sweep
    # needed; pipelines table only holds finished rows).
    running: set[tuple[str, str]] = set()

    conn = db.connect()
    manifests: dict[str, manifest.Manifest] = {}
    for row in conn.execute("SELECT name, manifest_path FROM problems"):
        manifests[row["name"]] = manifest.parse(workspace / row["manifest_path"])

    print(f"[dispatcher] start, pool={pool_size}, problems={list(manifests)}",
          flush=True)
    start_time = time.time()

    while True:
        # Cascade for any completed pipelines
        if futures:
            done, _ = wait(list(futures), timeout=0, return_when=FIRST_COMPLETED)
            for fut in done:
                meta = futures.pop(fut)
                running.discard((meta[2], meta[1]))  # (target_id, kind)
                try:
                    pid, kind, tid, tk, outcome = fut.result()
                    cascade_one(conn, pipeline_id=pid, kind=kind,
                                target_id=tid, target_kind=tk, outcome=outcome)
                    print(f"[cascade] {kind} {tk}={tid} → {outcome}", flush=True)
                except Exception as exc:
                    print(f"[cascade] worker exception: {exc}", flush=True)

        if db.root_proved(conn):
            print("[dispatcher] all roots proved", flush=True)
            pool.shutdown(wait=False, cancel_futures=True)
            return 0

        # Refill queue (uses in-memory `running` for dedup)
        bfs_refill(conn, running)

        # Spawn from queue while pool has slots
        while len(futures) < pool_size:
            row = db.pop_queue(conn)
            if row is None:
                break
            target_id = str(row["target_id"])
            kind = str(row["kind"])
            target_kind = "Strategy" if kind == "Builder" and \
                _looks_like_strategy_id(conn, target_id) else "Goal"
            if (target_id, kind) in running:
                continue
            pipeline_id = agent.new_pipeline_id()
            running.add((target_id, kind))
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

        if time.time() - start_time > 30 * 60:
            print("[dispatcher] 30 min budget exceeded; stopping")
            pool.shutdown(wait=False, cancel_futures=True)
            return 1


def _looks_like_strategy_id(conn: sqlite3.Connection, tid: str) -> bool:
    try:
        i = int(tid)
    except ValueError:
        return False
    row = conn.execute(
        "SELECT 1 FROM strategies WHERE id = ? LIMIT 1", (i,)
    ).fetchone()
    return row is not None
