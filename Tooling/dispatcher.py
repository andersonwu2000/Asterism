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

from . import (
    agent, config, db, library, manifest, pipeline, playbook, prune, tree,
)


# Per-model defaults (F31 + F37). Empirically:
#   Sonnet/Opus rarely succeed at attempts ≥3 — 97% of proves happen
#                in ≤3 Builder fails. Use 3/8 — first 3 attempts go to
#                Builder, then Backward retries until attempts hit 8.
#   Haiku       iterates productively across more attempts (its training
#                memory of Mathlib API specifics is thinner; F20 + F22 +
#                retries lets it converge given enough budget). Use 5/10.
#
# F37 raised the SHELVE half (7→8 / 8→10) because passive OR=1 means
# every dead strategy now consumes one goal-attempt (added in
# _propagate_shelve). Without the bump the goal would shelve before
# Backward gets enough chances to explore alternative strategies.
#
# Semantics:
#   BUILDER_THRESHOLD = N → first N attempts (0..N-1) dispatch Builder,
#                          attempts >= N dispatch Backward.
#   SHELVE_THRESHOLD = M  → goal shelves once attempts hits M.
#
# Resolution chain (see Tooling/config.py): env override
# (ASTERISM_{BUILDER,SHELVE}_THRESHOLD) → Asterism.yaml `dispatch.*`
# → built-in (3, 8) tuned for Sonnet/Opus baseline. Weak-tier models
# (haiku/flash) want roughly (5, 10) — set explicitly in Asterism.yaml.
# Real values resolved in `run()` below per-process.
BUILDER_THRESHOLD = 3
SHELVE_THRESHOLD = 8

TICK_TIMEOUT = 30  # seconds


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
    # 'proposed' strategy survives, transition 'attempting' → 'open'
    # AND increment the goal's attempts counter. The increment (F37)
    # ensures every dead strategy advances toward SHELVE_THRESHOLD;
    # without it, passive OR=1 would spin Backward indefinitely
    # producing strategies that all die to deeper sub-goal shelves
    # without ever exhausting the goal's attempt budget.
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
                n = db.increment_goal_attempts(conn, gid)
                if n >= SHELVE_THRESHOLD:
                    # Cascading shelve: this parent has now run out of
                    # attempts as a result of the sub-goal's death.
                    # Recurse so its own parents propagate too.
                    db.update_goal_status(conn, gid, "shelved")
                    _propagate_shelve(conn, gid)
                else:
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

def _latest_failure_reason(conn: sqlite3.Connection,
                           pipeline_id: str) -> str | None:
    """Look up the failure_reason of the latest dead_attempt for this
    pipeline, or None when no row exists (worker-exception cascades
    synthesized from outside don't write dead_attempts)."""
    row = conn.execute(
        "SELECT failure_reason FROM dead_attempts "
        "WHERE pipeline_id = ? ORDER BY id DESC LIMIT 1",
        (pipeline_id,),
    ).fetchone()
    return row["failure_reason"] if row else None


def _is_spawn_fast_fail(conn: sqlite3.Connection, pipeline_id: str) -> bool:
    """F46 — was this pipeline's failure a spawn-side fast fail (rc≠0
    in <10s, almost certainly an infra problem and not an agent error)?
    The pipeline writes a dead_attempt row with `failure_reason =
    'spawn_fast_fail'` in this case. Check that row to decide whether
    the cascade should skip incrementing the goal's attempts counter.
    Returns False if no dead_attempt was recorded (e.g. success cases
    or worker-exception cascades synthesized from outside)."""
    return _latest_failure_reason(conn, pipeline_id) == "spawn_fast_fail"


def _is_agent_declined(conn: sqlite3.Connection, pipeline_id: str) -> bool:
    """F48 — did the Builder agent invoke the decline hatch (write
    PROPOSAL.md but no patch.lean)? When True, cascade fast-tracks the
    goal to Backward rather than burning the rest of BUILDER_THRESHOLD
    on attempts the agent already declared unwinnable."""
    return _latest_failure_reason(conn, pipeline_id) == "agent_declined"


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
    after the goal has been won by a (possibly sequential) sibling
    strategy or after the goal cascade-shelved.

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

    # F46 — spawn fast-fail (rc≠0 in <10s) is almost always an infra
    # fault (claude.exe crash on launch, cwd issue, transient OS hiccup),
    # not an agent error. Don't burn the goal's attempts cap for it.
    # Dispatcher main loop separately back-offs via cooldown dict.
    is_fast_fail = (outcome in ("exhausted", "failed")
                    and _is_spawn_fast_fail(conn, pipeline_id))

    if kind == "Builder":
        if outcome == "proved":
            db.update_goal_status(conn, int(target_id), "proved")
            # F33 — goal proved; the Builder session served its purpose.
            # Clearing keeps DB tidy; on-disk session file is harmless.
            db.set_builder_session_id(conn, int(target_id), None)
            return
        if outcome in ("exhausted", "failed"):
            if is_fast_fail:
                # F46 — leave attempts unchanged; dispatcher will cool
                # this (target,kind) for ~30s before the next dispatch.
                return
            # F48 — Builder explicitly declined (wrote PROPOSAL.md
            # but no patch.lean per builder.md's STOP block). Honor
            # the agent: jump attempts to BUILDER_THRESHOLD so the
            # next dispatch is Backward rather than another Builder
            # the agent already said it can't handle. SHELVE_THRESHOLD
            # progress still advances by the same +1 the increment
            # would have produced — declines are not free, just
            # routed differently.
            if _is_agent_declined(conn, pipeline_id):
                cur = db.get_goal(conn, int(target_id))
                cur_n = int(cur["attempts"]) if cur else 0
                target_n = max(cur_n + 1, BUILDER_THRESHOLD)
                # Bring attempts up to the Backward boundary in one step.
                for _ in range(target_n - cur_n):
                    n = db.increment_goal_attempts(conn, int(target_id))
                if n >= SHELVE_THRESHOLD:
                    db.update_goal_status(conn, int(target_id), "shelved")
                    db.set_builder_session_id(conn, int(target_id), None)
                    _propagate_shelve(conn, int(target_id))
                else:
                    # Builder session is moot now; next dispatch is Backward.
                    db.set_builder_session_id(conn, int(target_id), None)
                return
            n = db.increment_goal_attempts(conn, int(target_id))
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, int(target_id), "shelved")
                db.set_builder_session_id(conn, int(target_id), None)
                _propagate_shelve(conn, int(target_id))
            elif n >= BUILDER_THRESHOLD:
                # F33 — next dispatch is Backward (no LLM session);
                # the lingering Builder session won't be reused.
                db.set_builder_session_id(conn, int(target_id), None)
            return

    if kind == "Backward":
        if outcome == "success":
            db.update_goal_status(conn, int(target_id), "attempting")
            return
        # exhausted / failed
        if is_fast_fail:
            return  # F46 — same skip-increment as Builder above
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
                # Defensive: mark any other live strategies on this goal
                # 'superseded'. Under F37 OR=1 this is rare (typically only
                # the winner is alive), but cascade timing can briefly
                # leave a stale 'proposed' sibling.
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
               running: set[tuple[str, str]],
               cooldown_until: dict[tuple[str, str], float] | None = None,
               ) -> None:
    """Enqueue dispatchable tasks. `running` is the in-memory live set
    of (target_id, kind) pairs currently executing in this daemon. F37
    passive trigger: cap = 1 per (target_id, kind) — a goal has at most
    one Builder OR one Backward in flight at a time, and a strategy at
    most one Verify. Daemon crash → set vanishes; pipelines table only
    holds finished rows so restart is clean.

    F46 — `cooldown_until` carries (target_id, kind) → epoch seconds
    until which dispatch is suppressed. Pairs whose cooldown is in the
    future are skipped this tick. Set after a spawn_fast_fail cascade
    so transient claude / network failures don't burst-retry at 2s/call.
    """
    now = time.time()
    cd = cooldown_until or {}

    def in_flight(tid: str, kind: str) -> int:
        running_n = 1 if (tid, kind) in running else 0
        return running_n + db.queue_count(conn, target_id=tid, kind=kind)

    def cooled(tid: str, kind: str) -> bool:
        return cd.get((tid, kind), 0.0) > now

    # Strategies with all sub-goals proved → enqueue Verify
    for s in db.strategies_ready_for_verify(conn):
        sid = str(s["id"])
        if in_flight(sid, "Verify") == 0 and not cooled(sid, "Verify"):
            db.enqueue(conn, kind="Verify", target_id=sid, priority=10)

    # Open goals → enqueue if no in-flight or queued attempt exists
    for g in db.open_goals(conn):
        gid = str(g["id"])
        kind = next_worker_kind(g)
        if in_flight(gid, kind) == 0 and not cooled(gid, kind):
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
    pool_size = config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=workspace)
    budget_sec = config.get(
        "dispatch.budget_sec", default=1800,
        env_var="ASTERISM_BUDGET_SEC", cast=int, workspace=workspace)
    # F47 — BUILDER_THRESHOLD semantically belongs to the Builder kind
    # (controls Builder→Backward transition based on Builder model
    # strength). New canonical key: `builder.threshold`. Old
    # `dispatch.builder_threshold` is honored as a back-compat fallback
    # so existing Asterism.yaml files keep working unchanged.
    BUILDER_THRESHOLD = config.get(
        "builder.threshold", default=None,
        env_var="ASTERISM_BUILDER_THRESHOLD", cast=int, workspace=workspace)
    if BUILDER_THRESHOLD is None:
        BUILDER_THRESHOLD = config.get(
            "dispatch.builder_threshold", default=3,
            cast=int, workspace=workspace)
    SHELVE_THRESHOLD = config.get(
        "dispatch.shelve_threshold", default=8,
        env_var="ASTERISM_SHELVE_THRESHOLD", cast=int, workspace=workspace)
    if SHELVE_THRESHOLD <= BUILDER_THRESHOLD:
        # An invalid combo would mean Backward never gets a chance —
        # fail loudly rather than silently degrade behavior.
        raise ValueError(
            f"shelve_threshold ({SHELVE_THRESHOLD}) must exceed "
            f"builder_threshold ({BUILDER_THRESHOLD}); otherwise "
            f"the goal shelves before any Backward attempt fires.")
    pool = ThreadPoolExecutor(max_workers=pool_size)
    futures: dict[Future, tuple[str, str, str, str]] = {}
    # In-memory live set of (target_id, kind) pairs currently executing in
    # this daemon. F37 passive trigger means at most one of each kind per
    # target, so the pair is a unique key. Daemon crash → set vanishes →
    # restart sees clean slate.
    running: set[tuple[str, str]] = set()
    # F46 — per-(target_id, kind) cooldown until epoch seconds. Set after
    # a spawn_fast_fail cascade; bfs_refill skips cooled pairs so the
    # daemon doesn't burst-retry a broken claude.exe at 2s/call.
    cooldown_until: dict[tuple[str, str], float] = {}
    # F46 — global counter of consecutive spawn_fast_fail outcomes
    # (across all targets). Reset by any non-fast-fail cascade. If it
    # crosses CONSEC_SPAWN_FAIL_LIMIT the daemon exits with a clear
    # message — claude.exe is persistently broken and human attention
    # is required.
    consec_fast_fails = 0
    SPAWN_COOLDOWN_SEC = 30.0
    CONSEC_SPAWN_FAIL_LIMIT = 10

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
                running.discard((meta[2], meta[1]))
                try:
                    pid, kind, tid, tk, outcome = fut.result()
                    cascade_one(conn, pipeline_id=pid, kind=kind,
                                target_id=tid, target_kind=tk,
                                outcome=outcome, workspace=workspace)
                    # F46 — back-off + global counter for spawn fast-fails
                    if outcome in ("exhausted", "failed") \
                            and _is_spawn_fast_fail(conn, pid):
                        cooldown_until[(tid, kind)] = (
                            time.time() + SPAWN_COOLDOWN_SEC)
                        consec_fast_fails += 1
                        print(f"[cooldown] {kind} {tk}={tid} cooled "
                              f"{SPAWN_COOLDOWN_SEC:.0f}s after spawn_fast_fail "
                              f"(consec={consec_fast_fails})", flush=True)
                        if consec_fast_fails >= CONSEC_SPAWN_FAIL_LIMIT:
                            print(f"[dispatcher] {consec_fast_fails} "
                                  f"consecutive spawn_fast_fails — claude.exe "
                                  f"or provider appears broken; exiting. "
                                  f"Inspect .attempts/<pid>/_spawn.stderr "
                                  f"for the underlying error.", flush=True)
                            pool.shutdown(wait=False, cancel_futures=True)
                            return 2
                    else:
                        consec_fast_fails = 0
                    print(f"[cascade] {kind} {tk}={tid} → {outcome}", flush=True)
                    tree.write_for_target(conn, workspace, tid, tk)
                except Exception as exc:
                    # Worker thread raised an unhandled exception (e.g.
                    # subprocess launch errno-2, OSError on temp dir, an
                    # internal pipeline bug). Without explicit recovery
                    # the goal stays open, attempts unchanged, and
                    # bfs_refill re-dispatches in an infinite loop.
                    # Synthesize a cascade with outcome='failed' so the
                    # goal advances toward SHELVE_THRESHOLD and forensic
                    # state at least mentions the exception.
                    pid, kind, tid, tk = meta
                    print(f"[cascade] worker exception on {kind} "
                          f"{tk}={tid}: {exc}; treating as failed",
                          flush=True)
                    try:
                        cascade_one(conn, pipeline_id=pid, kind=kind,
                                    target_id=tid, target_kind=tk,
                                    outcome="failed", workspace=workspace)
                        tree.write_for_target(conn, workspace, tid, tk)
                    except Exception as exc2:
                        # Cascade itself bombing is a deeper bug; log
                        # but don't crash the daemon (other work may
                        # still progress).
                        print(f"[cascade] secondary exception during "
                              f"recovery: {exc2}", flush=True)

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
                # F49 — promote proved root to Library/<Topic>/. Runs
                # AFTER reconcile + prune so the file set is canonical
                # before re-export. Idempotent + axiom-gated; safe to
                # call on every daemon exit.
                library.maybe_promote(
                    conn, workspace, problem_name, manifests[problem_name])
            pool.shutdown(wait=False, cancel_futures=True)
            return 0

        # Refill queue (uses in-memory `running` for dedup; cooldown_until
        # holds spawn_fast_fail back-offs from F46).
        bfs_refill(conn, running, cooldown_until)

        # Spawn from queue while pool has slots. F37: skip if a pipeline
        # of the same (target_id, kind) is already in flight in this
        # daemon — bfs_refill caps at 1 but daemon recovery + race
        # corners mean defense-in-depth here is cheap.
        while len(futures) < pool_size:
            row = db.pop_queue(conn)
            if row is None:
                break
            target_id = str(row["target_id"])
            kind = str(row["kind"])
            if (target_id, kind) in running:
                continue
            target_kind = "Strategy" if kind == "Verify" else "Goal"
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


