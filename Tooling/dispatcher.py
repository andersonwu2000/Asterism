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
    verify,
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

# P2-#4: recovery moved to Tooling/recovery.py. Re-exported here for
# back-compat with existing test imports (`dispatcher._recover_at_startup`,
# `dispatcher._sweep_lean_backups`).
from .recovery import recover_at_startup as _recover_at_startup  # noqa: E402,F401
from .recovery import sweep_lean_backups as _sweep_lean_backups  # noqa: E402,F401


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

    # F16 — kill strategies whose parent goal IS this shelved goal.
    # P1-#5: explicit commit. Previously the trailing UPDATE relied
    # on a downstream `db.update_*` helper to flush. Most cascades
    # do trigger one before the worker conn closes, but if the loop
    # exits cleanly (budget exhausted, idle-exit) right after this
    # function returns, the F16 row updates never reach disk.
    conn.execute(
        "UPDATE strategies SET status='dead' "
        "WHERE goal_id = ? AND status='proposed'",
        (goal_id,),
    )
    conn.commit()


def next_worker_kind(goal: sqlite3.Row) -> str:
    """Pure-ish: input goal row → 'Builder' or 'Backward'.

    Routing is `entry_kind`-driven with an attempts-threshold safety net.
    While attempts < `BUILDER_THRESHOLD` we honor the `entry_kind`
    directive (`'Builder'` | `'Backward'`); once attempts reach the
    threshold, escalation to Backward is forced (safety net for an
    entry_kind=Builder directive that turns out wrong).

    `entry_kind` is set by:
      - cli init for the root goal, from `Manifest.entry_kind`
        (`Builder` | `Backward`, human-authored in `## Entry kind`).
      - Backward agent for each sub-goal it generates, via the
        `-- entry_kind: ...` directive in `new_<slug>.lean`'s docstring;
        framework parses + persists at sub-goal insertion time.

    Earlier iterations gated on a numeric `difficulty` (1-10): a hard
    `>=4 → Backward` rule was unreliable because the agent's estimate
    tracked conceptual complexity, not Builder-tractability. The boolean
    directive is now the only routing signal — `difficulty` was removed
    from both Manifest and the goals table.

    `BUILDER_THRESHOLD` is module-level so test/env overrides are visible
    without re-importing.
    """
    if int(goal["attempts"]) >= BUILDER_THRESHOLD:
        return "Backward"
    if str(goal["entry_kind"]) == "Backward":
        return "Backward"
    return "Builder"


# ---------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------

# Cascade reads `failure_reason` directly from PipelineResult passed in;
# helpers that round-tripped through dead_attempts (`_latest_failure_reason`
# / `_is_*`) were removed — the reason is already in scope, no DB query
# needed. spawn_fast_fail rows are no longer written to dead_attempts at
# all (they were noise: never projected as event, only read by these
# helpers); the reason is a transient signal carried through the future
# result tuple.


def cascade_one(conn: sqlite3.Connection, *, pipeline_id: str,
                kind: str, target_id: str, target_kind: str,
                outcome: str, failure_reason: str = "",
                workspace: Path | None = None) -> None:
    """Apply state transitions for one finished pipeline.

    Each worker_kind has a fixed target_kind:
      Builder  → Goal   (fresh sorry-stub closure)
      Backward → Goal   (decompose into sub-goals)

    F56 — strategy verification is no longer a worker_kind. The
    framework-side verify happens inline in the dispatcher tick via
    `verify.verify_housekeeping`, not here.

    No-op entry: if the target's underlying goal is already proved or
    its strategy is already 'superseded', skip the transition. This
    catches loser strategies / orphan sub-goals whose workers finish
    after the goal has been won by a (possibly sequential) sibling
    strategy or after the goal cascade-shelved.

    `workspace` is retained on the signature for back-compat (legacy
    callers passed it for Verify's playbook hook); now unused.
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
    is_fast_fail = (outcome == "failed"
                    and failure_reason == "spawn_fast_fail")

    if kind == "Builder":
        if outcome == "proved":
            db.update_goal_status(conn, int(target_id), "proved")
            # F33 — goal proved; the Builder session served its purpose.
            # Clearing keeps DB tidy; on-disk session file is harmless.
            db.set_builder_session_id(conn, int(target_id), None)
            return
        if outcome == "failed":
            if is_fast_fail:
                # F46 — leave attempts unchanged; dispatcher will cool
                # this (target,kind) for ~30s before the next dispatch.
                return
            # Infeasibility escape: agent reported `parent_type_infeasible`
            # in PROPOSAL.md frontmatter (counterexample required). Skip
            # attempts++; shelve this goal directly so `_propagate_shelve`
            # kills the parent strategy and re-opens the parent goal for
            # a redesigned Backward decomposition. Without this, the wrong-
            # type sub-goal would burn SHELVE_THRESHOLD attempts before
            # cascading up — typically several hours of LLM time.
            if failure_reason == "agent_infeasible":
                db.update_goal_status(conn, int(target_id), "shelved")
                db.set_builder_session_id(conn, int(target_id), None)
                _propagate_shelve(conn, int(target_id))
                return
            # F48 — Builder explicitly declined (wrote PROPOSAL.md
            # but no patch.lean per builder.md's STOP block). Honor
            # the agent: jump attempts to BUILDER_THRESHOLD so the
            # next dispatch is Backward rather than another Builder
            # the agent already said it can't handle. SHELVE_THRESHOLD
            # progress still advances by the same +1 the increment
            # would have produced — declines are not free, just
            # routed differently.
            if failure_reason == "agent_declined":
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
            # F53 — strategy committed; clear backward session so the
            # next Backward on this goal (cascade-reopen path) starts
            # fresh rather than resuming a session about a strategy
            # that's already taken on the goal.
            db.set_backward_session_id(conn, int(target_id), None)
            return
        # failed
        if is_fast_fail:
            return  # F46 — same skip-increment as Builder above
        # Infeasibility escape (mirrors Builder branch above): Backward
        # agent declined with `parent_type_infeasible`, skip attempts++,
        # propagate shelve so the parent strategy re-decomposes.
        if failure_reason == "agent_infeasible":
            db.update_goal_status(conn, int(target_id), "shelved")
            db.set_backward_session_id(conn, int(target_id), None)
            _propagate_shelve(conn, int(target_id))
            return
        n = db.increment_goal_attempts(conn, int(target_id))
        if n >= SHELVE_THRESHOLD:
            db.update_goal_status(conn, int(target_id), "shelved")
            # F53 — shelved; same cleanup as Builder.
            db.set_backward_session_id(conn, int(target_id), None)
            _propagate_shelve(conn, int(target_id))
        return

    # F56 — Verify removed as a worker_kind. Strategy verification +
    # parent promotion happens in `verify.verify_housekeeping`, called
    # at the end of each dispatcher tick (see `run` below).


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

    # F56 — strategies ready for verify are no longer enqueued as
    # Verify pipelines. They're processed inline in `verify_housekeeping`
    # at the end of each tick.

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

            # F56 — only Goal-targeting kinds remain (Builder /
            # Backward). Strategy verify is housekeeping, not a worker.
            goal_id = int(target_id)
            goal = db.get_goal(conn, goal_id)
            if goal is None:
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status="failed", outcome="failed",
                    started_at=started_at,
                )
                return (pipeline_id, task_kind, target_id, target_kind,
                        "failed", "goal_not_found")

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

            status = "succeeded" if r.outcome in ("proved", "success") else "failed"
            db.record_pipeline(
                conn, pipeline_id=pipeline_id, kind=task_kind,
                target_id=target_id, target_kind=target_kind,
                status=status, outcome=r.outcome,
                started_at=started_at,
            )

            # Capture artifacts from .attempts/<pid>/ before WorkArea rmtree.
            # Skip dead_attempts INSERT for:
            #   - 'superseded' (OR race noise, not a real failure)
            #   - 'spawn_fast_fail' (infra fault, not agent action; reason
            #     is carried back through the future tuple for cooldown,
            #     dead_attempts row would only be filtered out by events
            #     anyway — F46/audit problem 4)
            if r.failure_reason and r.failure_reason not in (
                "superseded", "spawn_fast_fail",
            ):
                artifacts = pipeline.collect_artifacts(attempts_dir)
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

            return (pipeline_id, task_kind, target_id, target_kind,
                    r.outcome, r.failure_reason)
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
                    pid, kind, tid, tk, outcome, reason = fut.result()
                    cascade_one(conn, pipeline_id=pid, kind=kind,
                                target_id=tid, target_kind=tk,
                                outcome=outcome, failure_reason=reason,
                                workspace=workspace)
                    # F46 — back-off + global counter for spawn fast-fails
                    if outcome == "failed" and reason == "spawn_fast_fail":
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

        # F56 — strategy verify housekeeping. Runs after cascade so any
        # newly-proved sub-goals from this tick contribute to the
        # `ready_for_verify` poll. Inline + recursive (chain follow-up
        # for multi-layer strategies in one tick).
        verify.verify_housekeeping(conn, workspace=workspace)

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
                # Final TREE.md refresh — the per-cascade write_for_target
                # ran before the verify_housekeeping that cascade-proved
                # the root, leaving TREE.md frozen at root=attempting.
                tree.write(conn, workspace, problem_name)
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
            target_kind = "Goal"  # F56 — Verify removed; only Goal kinds left
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


