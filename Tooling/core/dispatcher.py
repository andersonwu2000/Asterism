"""Main dispatcher loop. Cascade in main thread, pipelines in pool.

See architecture.md §7-§8.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

from .. import agent, pipeline
from . import config
from ..state import db, manifest, tree
from ..quality import prune, verify


# Per-model defaults. Empirically:
#   Sonnet/Opus rarely succeed at attempts ≥3 — 97% of proves happen
#                in ≤3 Builder fails. Use 3/8 — first 3 attempts go to
#                Builder, then Backward retries until attempts hit 8.
#   Haiku       iterates productively across more attempts (its training
#                memory of Mathlib API specifics is thinner; lemma
#                signature lookup + retries lets it converge given enough
#                budget). Use 5/10.
#
# Passive OR=1 means every dead strategy now consumes one goal-attempt
# (added in _propagate_shelve). SHELVE_THRESHOLD was raised (7→8 / 8→10)
# so the goal doesn't shelve before Backward gets enough chances to
# explore alternative strategies.
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
# Forward retry budget per Inject. Each Inject is a Strategist meta-
# decision; on Forward failure (lake error / parse rejected / dedupe
# blocked) the agent --resume's next attempt sees the failure as
# retry_context and can correct (e.g. missing `import` observed SG run
# 2026-05-17: agent referenced `Collinear` without importing Defs).
# Kept small (mirrors BUILDER_THRESHOLD) because Forward is a single
# lemma write — diminishing returns past 3 retries.
FORWARD_RETRY_BUDGET = 3

TICK_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------
# Startup recovery
# ---------------------------------------------------------------------

# Recovery moved to Tooling/recovery.py. Re-exported here for
# back-compat with existing test imports (`dispatcher._recover_at_startup`,
# `dispatcher._sweep_lean_backups`).
from ..state.recovery import recover_at_startup as _recover_at_startup  # noqa: E402,F401
from ..state.recovery import sweep_lean_backups as _sweep_lean_backups  # noqa: E402,F401


# ---------------------------------------------------------------------
# Phase 2 — pending_strategist_review + cascade_shelve_descendants +
# reopen_with_detach (used by cascade_one Rule 1 and the future
# Strategist pipeline for ConfirmShelve / Reopen commits).
# ---------------------------------------------------------------------

def _record_inject_decision_outcome(conn: sqlite3.Connection,
                                    decision_id: int,
                                    outcome: str,
                                    failure_reason: str) -> None:
    """Write the Forward pipeline's terminal outcome back into the
    strategist_decisions row that emitted it.

    Solo + batch Inject both go through this; the row's `outcome` was
    NULL post-commit and gets filled here so failure_replay (Strategist
    self-feedback) shows 'my Inject succeeded / failed because X'.
    `failure_reason` joins outcome via ':' for compactness — full
    forensic still lives in dead_attempts.failure_detail keyed by
    pipeline_id.
    """
    text = outcome if not failure_reason else f"{outcome}:{failure_reason}"
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (text, db.now(), decision_id),
    )
    conn.commit()


def _maybe_enqueue_inject_batch_done(conn: sqlite3.Connection,
                                     decision_id: int) -> None:
    """If `decision_id` belongs to an Inject batch (batch_id non-NULL)
    AND every sibling row in the batch now has `outcome` filled, fire
    a single 'inject_batch_done' Strategist trigger on this problem.

    Idempotent via the queue dedup inside the helper: a duplicate
    Strategist trigger for the same root is silently dropped. Solo
    Inject (batch_id NULL) is a no-op.
    """
    row = conn.execute(
        "SELECT batch_id, problem FROM strategist_decisions WHERE id = ?",
        (decision_id,),
    ).fetchone()
    if row is None or row["batch_id"] is None:
        return
    batch_id = str(row["batch_id"])
    problem = str(row["problem"])
    pending = conn.execute(
        "SELECT COUNT(*) AS n FROM strategist_decisions"
        " WHERE batch_id = ? AND outcome IS NULL",
        (batch_id,),
    ).fetchone()
    if int(pending["n"]) > 0:
        return
    root_row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()
    if root_row is None:
        return
    root_id = str(root_row["id"])
    if db.is_in_queue(conn, target_id=root_id, kind="Strategist"):
        return
    # Priority 20 — same band as T2 pending_review; batch completion is
    # an event-driven follow-up that supersedes the routine T1 wall-clock.
    db.enqueue(conn, kind="Strategist", target_id=root_id,
               target_kind="Goal", priority=20)


def _enqueue_strategist_review(conn: sqlite3.Connection,
                               goal_id: int) -> None:
    """Phase 2 Rule 1 — agent_shelved branch.

    Set the goal to `pending_strategist_review` (transitional, not
    terminal) and enqueue a Strategist run on this problem's root.
    Strategist later commits one of ConfirmShelve / Reopen / Inject;
    until then the upward strategy chain stays alive.

    Idempotent on duplicate Strategist enqueue: if the queue already
    has a Strategist row for this problem's root, skip the second
    enqueue (per-problem in-flight dedup; see pipelines.md §4.3).
    """
    g = db.get_goal(conn, goal_id)
    if g is None:
        return
    # Status transition: pending_strategist_review (not 'shelved').
    # update_goal_status() flips integrity_verified=0 for any
    # non-'proved' transition; we want that for stability since the
    # goal may later be Reopen'd.
    db.update_goal_status(conn, goal_id, "pending_strategist_review")

    # Find this problem's root goal — Strategist queue target.
    root_row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND origin = 'root'",
        (g["problem"],),
    ).fetchone()
    if root_row is None:
        return
    root_id = str(root_row["id"])

    # Per-problem in-flight dedup: skip if a Strategist row already sits
    # in the queue for this problem's root. dispatcher's main-loop
    # in-memory `running` set covers active dispatches; this DB check
    # covers queue-pending entries.
    if db.is_in_queue(conn, target_id=root_id, kind="Strategist"):
        return
    # Priority 20 — above T0/T1 (=10) per pipelines.md §2.1 "T2 > T0 > T1".
    # T2 is event-driven (an agent shelved, review needed); T0/T1 are
    # routine. Without an explicit priority kwarg the default 0 would put
    # T2 below Backward (=2) and Builder (=5), inverting the spec.
    db.enqueue(conn, kind="Strategist", target_id=root_id,
               target_kind="Goal", priority=20)


def _cascade_shelve_descendants(conn: sqlite3.Connection,
                                goal_id: int) -> int:
    """Phase 2 Rule 2 — ConfirmShelve downward cascade.

    Walk strategy_subgoals from `goal_id` to all reachable descendants
    via alive strategies (BFS over goal → its strategies → their
    sub-goals → ...). Flip every descendant whose status ∈ {open,
    attempting, pending_strategist_review} to 'shelved'. Preserves
    terminal states (proved / shelved / disproved) — Reopen still
    works on the cascade-shelved goals because 'shelved' is soft.

    Returns the number of goals transitioned.

    Distinct from `_propagate_shelve`:
      * _propagate_shelve walks UPWARD (parent strategies of this
        goal; reopens or attempts++ parent goals on chain death).
      * _cascade_shelve_descendants walks DOWNWARD (sub-goals of this
        goal's own strategies; releases BFS hold on them).
    Both helpers are called by Strategist's ConfirmShelve commit (see
    docs/phase2/pipelines.md §4.2 Rule 2).
    """
    visited: set[int] = set()
    frontier: list[int] = [goal_id]
    transitioned = 0
    while frontier:
        next_frontier: list[int] = []
        for gid in frontier:
            # Find this goal's strategies' sub-goals (one hop down).
            rows = conn.execute(
                "SELECT ss.subgoal_id FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " WHERE s.goal_id = ?",
                (gid,),
            ).fetchall()
            for r in rows:
                sub_id = int(r["subgoal_id"])
                if sub_id in visited:
                    continue
                visited.add(sub_id)
                # Read status; only transition non-terminal rows.
                grow = conn.execute(
                    "SELECT status FROM goals WHERE id = ?",
                    (sub_id,),
                ).fetchone()
                if grow is None:
                    continue
                if grow["status"] in ("open", "attempting",
                                      "pending_strategist_review"):
                    db.update_goal_status(conn, sub_id, "shelved")
                    transitioned += 1
                # Continue BFS into this sub-goal's own strategies' subs
                # regardless of its status (the descendants of a
                # proved sub-goal can still include alive open goals
                # under sibling strategies of the proved one).
                next_frontier.append(sub_id)
        frontier = next_frontier
    return transitioned


def _has_terminal_disproved_ancestor(conn: sqlite3.Connection,
                                     goal_id: int) -> bool:
    """Phase 2 Rule 3 — Reopen safety walk.

    Return True iff any ancestor goal in the strategy_subgoals chain
    has status='disproved'. 'shelved' ancestors do NOT count (soft
    terminal; auto-detach handles broken upward chains).
    Walks UPWARD via strategy_subgoals.subgoal_id = goal_id → parent
    strategy → strategy.goal_id, recursively.
    """
    visited: set[int] = set()
    frontier: list[int] = [goal_id]
    while frontier:
        next_frontier: list[int] = []
        for gid in frontier:
            # Find this goal's parent goals (one hop up via strategies
            # that claim this goal as a sub-goal).
            rows = conn.execute(
                "SELECT s.goal_id FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " WHERE ss.subgoal_id = ?",
                (gid,),
            ).fetchall()
            for r in rows:
                parent_id = int(r["goal_id"])
                if parent_id in visited:
                    continue
                visited.add(parent_id)
                grow = conn.execute(
                    "SELECT status FROM goals WHERE id = ?",
                    (parent_id,),
                ).fetchone()
                if grow is None:
                    continue
                if grow["status"] == "disproved":
                    return True
                next_frontier.append(parent_id)
        frontier = next_frontier
    return False


def _has_dead_strategy_in_chain(conn: sqlite3.Connection,
                                goal_id: int) -> bool:
    """Phase 2 Rule 3 — auto-detach trigger detection.

    Return True iff any ancestor strategy in the upward chain has
    status ∈ {'dead', 'superseded'}. If so, Reopen sets `goals.detached
    = 1` so BFS dispatches on the goal standalone (no live parent
    strategy needed to thread the proof back to root).
    """
    visited: set[int] = set()
    frontier: list[int] = [goal_id]
    while frontier:
        next_frontier: list[int] = []
        for gid in frontier:
            rows = conn.execute(
                "SELECT s.id, s.goal_id, s.status FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " WHERE ss.subgoal_id = ?",
                (gid,),
            ).fetchall()
            for r in rows:
                if r["status"] in ("dead", "superseded"):
                    return True
                parent_id = int(r["goal_id"])
                if parent_id in visited:
                    continue
                visited.add(parent_id)
                next_frontier.append(parent_id)
        frontier = next_frontier
    return False


def _propagate_shelve(conn: sqlite3.Connection, goal_id: int) -> None:
    """Cascade a goal-shelve event in two directions:

    Upward: every parent strategy that still depends on this goal as a
    sub-goal can never become ready_for_verify (requires all sub-goals
    'proved'). Kill those proposed strategies; for each affected parent
    goal, if no live strategy survives, reopen it.

    Inward: strategies for proving the just-shelved goal are now moot.
    Kill them as well. Their sub-goals become orphans — `open_goals`
    walks the alive-strategy DAG and excludes them from dispatch, so no
    further cleanup is required.

    Iterative — a re-opened parent goal may shelve later via its own
    increment_goal_attempts path; we don't recurse here.
    """
    # Upward kill — strategies USING this goal as a sub-goal
    parent_strategies = conn.execute(
        "SELECT s.id, s.goal_id FROM strategies s "
        "JOIN strategy_subgoals ss ON ss.strategy_id = s.id "
        "WHERE ss.subgoal_id = ? AND s.status = 'proposed'",
        (goal_id,),
    ).fetchall()

    for s in parent_strategies:
        db.update_strategy_status(conn, int(s["id"]), "dead")

    # For each affected parent goal: if no 'proposed' strategy
    # survives, transition 'attempting' → 'open' AND increment the
    # goal's attempts counter. The increment ensures every dead
    # strategy advances toward SHELVE_THRESHOLD; without it, passive
    # OR=1 would spin Backward indefinitely producing strategies that
    # all die to deeper sub-goal shelves without ever exhausting the
    # goal's attempt budget.
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

    # Inward kill — strategies whose parent goal IS this shelved goal.
    # Explicit commit required: previously the trailing UPDATE relied
    # on a downstream `db.update_*` helper to flush. Most cascades
    # do trigger one before the worker conn closes, but if the loop
    # exits cleanly (budget exhausted, idle-exit) right after this
    # function returns, the inward-kill row updates never reach disk.
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


def _classify_worker_exception(exc: BaseException) -> str:
    """Map an uncaught worker-thread exception to a framework
    failure_reason. Returns `"gateway_unreachable"` for transport-level
    errors (urllib URLError, socket OSError with conn refused / reset /
    network-name-deleted), `""` otherwise so the default path applies
    (synthesize generic "failed" outcome → attempts++).

    Background — SG run #14 (2026-05-11) had a gateway IOCP-accept
    crash mid-run. After the crash, every Backward dispatch raised
    `urlopen error [WinError 10061]` (connection refused) from the
    daemon's own HTTP POST to the gateway. The legacy worker-exception
    branch wrote outcome=failed with no failure_reason → counted as
    a real attempt against the goal. Five infra refusals later, the
    root goal shelved at SHELVE_THRESHOLD. This classifier returns the
    transport reason so cascade_one routes through the existing
    _INFRA_REASONS short-circuit (no attempts++) AND the dispatcher
    main loop applies a 30s cooldown before re-dispatching to the
    same (target, kind) — giving the gateway time to recover (when
    accompanied by gateway-side fixes like 475c318) or letting the
    operator notice & restart.
    """
    import errno
    import urllib.error

    if isinstance(exc, urllib.error.URLError):
        return "gateway_unreachable"
    if isinstance(exc, OSError):
        # Cross-platform errno values for transport-level loss
        conn_errnos = {errno.ECONNREFUSED, errno.ECONNRESET,
                       errno.ENETUNREACH, errno.EHOSTUNREACH,
                       errno.ETIMEDOUT}
        if exc.errno in conn_errnos:
            return "gateway_unreachable"
        # Windows wraps these as WinError codes (winerror attr) often
        # without setting errno. winerror 10061=ECONNREFUSED-equiv,
        # 10054=ECONNRESET-equiv, 64=NETNAME_DELETED (peer aborted).
        winerror = getattr(exc, "winerror", None)
        if winerror in (10061, 10054, 10060, 10065, 64):
            return "gateway_unreachable"
    # Pipeline-side LSP RPC timeouts (lsp_client.py raises TimeoutError
    # when an `$/lean/rpc/call` doesn't complete within budget).
    # Distinct from gateway_unreachable: gateway IS reachable but
    # contended (e.g. miniF2F pilot's 5 simultaneous Builders vs 3
    # worker slots → 2 spawns time out waiting for slot acquire).
    # Same infra semantics (cooldown + retry, no attempts++), but
    # MUST NOT contribute to the gateway-death circuit breaker —
    # under healthy concurrency, transient_timeouts cluster and
    # would prematurely kill the daemon if treated as gateway death.
    if isinstance(exc, TimeoutError):
        return "transient_timeout"
    # Fallback string scan for wrapped/chained exceptions whose outer
    # type didn't match either isinstance branch above.
    msg = repr(exc)
    if any(s in msg for s in ("WinError 10061", "WinError 10054",
                              "WinError 64",
                              "Connection refused",
                              "Connection reset",
                              "gateway unreachable")):
        return "gateway_unreachable"
    return ""


def cascade_one(conn: sqlite3.Connection, *, pipeline_id: str,
                kind: str, target_id: str, target_kind: str,
                outcome: str, failure_reason: str = "",
                decision_id: int | None = None) -> None:
    """Apply state transitions for one finished pipeline.

    Each worker_kind has a fixed target_kind:
      Builder  → Goal   (fresh sorry-stub closure)
      Backward → Goal   (decompose into sub-goals)

    Strategy verification is no longer a worker_kind. The framework-side
    verify happens inline in the dispatcher tick via
    `verify.verify_housekeeping`, not here.

    No-op entry: if the target's underlying goal is already proved or
    its strategy is already 'superseded', skip the transition. This
    catches loser strategies / orphan sub-goals whose workers finish
    after the goal has been won by a (possibly sequential) sibling
    strategy or after the goal cascade-shelved.
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
                # Cascade race guard: parent goal was shelved while
                # this strategy's pipeline was in flight. Strategy is
                # moot; mark dead so invariant `proposed → parent alive`
                # holds.
                if row["status"] == "proposed":
                    db.update_strategy_status(conn, int(target_id),
                                              "dead")
                return
    elif target_kind == "Goal":
        row = conn.execute(
            "SELECT status FROM goals WHERE id = ?", (int(target_id),),
        ).fetchone()
        # Cascade race guard: once a goal reaches a terminal state
        # (proved/shelved), late cascades from in-flight pipelines must
        # not mutate it.
        # Without the 'shelved' guard, a Backward 'success' that races
        # past the shelve transition would unconditionally flip status
        # back to 'attempting' (observed: goal stuck at attempts=N with
        # status='attempting' instead of 'shelved').
        if row and row["status"] in ("proved", "shelved"):
            return

    # Provider/transport infra failures don't burn the goal's attempts
    # cap. Dispatcher main loop applies a per-target cooldown for all
    # four; only spawn_fast_fail contributes to the CONSEC daemon-exit
    # counter.
    #   * spawn_fast_fail      — rc≠0 with wall<10s (claude.exe crash)
    #   * quota_exhausted      — rc=126 (provider rate limit / quota)
    #   * missing_dep          — rc=127 (CLI binary missing)
    #   * gateway_unreachable  — pipeline raised URLError/OSError
    #                            (gateway HTTP transport failed: SG run
    #                            #14 2026-05-11 IOCP accept-loop death
    #                            shelved root goal by counting infra
    #                            refusals against attempts)
    _INFRA_REASONS = ("spawn_fast_fail", "quota_exhausted", "missing_dep",
                      "gateway_unreachable", "transient_timeout")
    is_infra = (outcome == "failed" and failure_reason in _INFRA_REASONS)

    # Phase 7 — `moot` outcome: pipeline detected the goal already
    # terminated (sibling proved / shelved / propagated shelve) before
    # spawning. No state mutation, no attempts++, no dead_attempt write
    # (decision 2). bfs_refill won't re-queue a terminal goal anyway.
    if outcome == "moot":
        return

    if kind == "Builder":
        if outcome == "proved":
            db.update_goal_status(conn, int(target_id), "proved")
            return
        # Phase 7 — `exhausted` outcome: in-pipeline retry helper
        # consumed its budget without a terminal outcome. Helper has
        # already written N dead_attempts + N attempts++ for the N
        # failed retries (decision 5/6). Cascade does status transition
        # only — no further increment, no dead_attempt write.
        if outcome == "exhausted":
            cur = db.get_goal(conn, int(target_id))
            n = int(cur["attempts"]) if cur else 0
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, int(target_id), "shelved")
                _propagate_shelve(conn, int(target_id))
            # If n is at/over BUILDER_THRESHOLD but under SHELVE, the
            # next bfs_refill picks Backward via next_worker_kind
            # — no extra cascade work needed (no session_id column to
            # clear post Phase 7-D).
            return
        if outcome == "failed":
            if is_infra:
                # Leave attempts unchanged; dispatcher will cool this
                # (target,kind) for ~30s before the next dispatch.
                return
            # Phase 2 — decline directives split by intent (see
            # `docs/phase2/pipelines.md` §4.2 Rule 1):
            #   * agent_infeasible (counterexample shown) → 'disproved'
            #     (hard terminal, dedupe blocks future same-shape proposals).
            #   * parent_needs_fix → 'shelved' (soft terminal, Phase 1
            #     behaviour preserved; Strategist may Reopen via auto-detach).
            #   * agent_shelved → 'pending_strategist_review'
            #     (transitional; defer judgment to Strategist via T2 trigger).
            # All three increment attempts once (LLM call happened;
            # preserve 1:1 attempts ↔ dead_attempts invariant) but only
            # the first two cascade — agent_shelved leaves the upward
            # strategy chain alive until Strategist commits a verdict.
            if failure_reason == "agent_infeasible":
                db.increment_goal_attempts(conn, int(target_id))
                db.update_goal_status(conn, int(target_id), "disproved")
                _propagate_shelve(conn, int(target_id))
                return
            if failure_reason == "parent_needs_fix":
                db.increment_goal_attempts(conn, int(target_id))
                db.update_goal_status(conn, int(target_id), "shelved")
                _propagate_shelve(conn, int(target_id))
                return
            if failure_reason == "agent_shelved":
                db.increment_goal_attempts(conn, int(target_id))
                _enqueue_strategist_review(conn, int(target_id))
                return
            # `needs_decomposition` directive (legacy `too_hard`):
            # Builder says "this goal needs decomposition first". Route
            # next dispatch to Backward via entry_kind switch instead
            # of inflating attempts to BUILDER_THRESHOLD. Phase 7
            # decision 5: attempts is LLM-call failure count, not a
            # routing knob; entry_kind preserves the 1:1 invariant
            # while still forcing the next dispatch to Backward.
            if failure_reason == "agent_declined":
                n = db.increment_goal_attempts(conn, int(target_id))
                if n >= SHELVE_THRESHOLD:
                    db.update_goal_status(conn, int(target_id), "shelved")
                    _propagate_shelve(conn, int(target_id))
                else:
                    db.update_goal_entry_kind(conn, int(target_id),
                                              "Backward")
                return
            n = db.increment_goal_attempts(conn, int(target_id))
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, int(target_id), "shelved")
                _propagate_shelve(conn, int(target_id))
            return

    if kind == "Forward":
        # Forward's target is the problem name (target_kind='Problem');
        # no goal row to update. Phase 2.5 unified — every Forward is
        # dispatched from an Inject batch (queue.decision_id always
        # set), so the batch-done hook covers the "give Strategist a
        # chance to re-decide after Forward fails" need that the legacy
        # pending_review re-enqueue used to handle separately.
        #
        # The hook: record this row's outcome, then if every sibling in
        # the batch is now terminal, enqueue a single Strategist with
        # trigger derivation → `inject_batch_done` (via the
        # `unacknowledged_inject_batches` ratchet). Infra and moot
        # outcomes do NOT advance the batch (Forward retries handle
        # infra internally; moot = no real attempt happened).
        if (decision_id is not None
                and not is_infra
                and outcome
                and outcome != "moot"):
            _record_inject_decision_outcome(conn, decision_id, outcome,
                                            failure_reason)
            _maybe_enqueue_inject_batch_done(conn, decision_id)
        return

    if kind == "Backward":
        if outcome == "success":
            # Race guard: when a Backward leaf-bypass commits a strategy
            # that fails axiom probe (e.g. sorry-stub body), verify
            # housekeeping can fire BEFORE this cascade — verify marks
            # the strategy dead and reopens the goal to 'open'. The
            # delay comes from the worker's WorkArea.__exit__ release_
            # session HTTP call (up to 30s under gateway load); during
            # that window the main thread's tick boundary lets verify
            # see the just-committed ready_for_verify strategy and
            # process it before the worker's future is observed done.
            # Without this guard, the late cascade overwrites the
            # verify-reopened 'open' with 'attempting', leaving the
            # goal in a self-inconsistent state (no live strategy yet
            # status='attempting'); bfs_refill's open-only filter then
            # excludes it and the dispatcher idle-exits with budget
            # still available. Mirrors verify.py:218-224's has_live
            # check.
            has_live = conn.execute(
                "SELECT 1 FROM strategies WHERE goal_id = ?"
                " AND status IN ('proposed','succeeded') LIMIT 1",
                (int(target_id),),
            ).fetchone()
            if has_live is not None:
                db.update_goal_status(conn, int(target_id), "attempting")
            return
        # Phase 7 — `exhausted` outcome: mirrors Builder branch above.
        # Helper buffered N dead_attempts + N attempts++ for the N
        # failed retries; cascade does status transition only.
        if outcome == "exhausted":
            cur = db.get_goal(conn, int(target_id))
            n = int(cur["attempts"]) if cur else 0
            if n >= SHELVE_THRESHOLD:
                db.update_goal_status(conn, int(target_id), "shelved")
                _propagate_shelve(conn, int(target_id))
            return
        # failed
        if is_infra:
            return  # same skip-increment as Builder above
        # Decline directives mirror the Builder branch above (Phase 2
        # split: agent_infeasible → 'disproved' + propagate; parent_
        # needs_fix → 'shelved' + propagate; agent_shelved → 'pending_
        # strategist_review' + enqueue Strategist, no propagate).
        # Backward cannot send `needs_decomposition` (Builder-only); if
        # a typo / unknown directive lands here it falls through to the
        # generic attempts++ branch and eventually shelves at threshold.
        if failure_reason == "agent_infeasible":
            db.increment_goal_attempts(conn, int(target_id))
            db.update_goal_status(conn, int(target_id), "disproved")
            _propagate_shelve(conn, int(target_id))
            return
        if failure_reason == "parent_needs_fix":
            db.increment_goal_attempts(conn, int(target_id))
            db.update_goal_status(conn, int(target_id), "shelved")
            _propagate_shelve(conn, int(target_id))
            return
        if failure_reason == "agent_shelved":
            db.increment_goal_attempts(conn, int(target_id))
            _enqueue_strategist_review(conn, int(target_id))
            return
        n = db.increment_goal_attempts(conn, int(target_id))
        if n >= SHELVE_THRESHOLD:
            db.update_goal_status(conn, int(target_id), "shelved")
            _propagate_shelve(conn, int(target_id))
        return

    # Verify removed as a worker_kind. Strategy verification + parent
    # promotion happens in `verify.verify_housekeeping`, called at the
    # end of each dispatcher tick (see `run` below).


# ---------------------------------------------------------------------
# BFS queue refill
# ---------------------------------------------------------------------

def bfs_refill(conn: sqlite3.Connection,
               running: set[tuple[str, str]],
               cooldown_until: dict[tuple[str, str], float] | None = None,
               *,
               scope: str | None = None,
               quota_cooldown_kind: dict[str, float] | None = None,
               ) -> None:
    """Enqueue dispatchable tasks. `running` is the in-memory live set
    of (target_id, kind) pairs currently executing in this daemon.
    Passive trigger: cap = 1 per (target_id, kind) — a goal has at most
    one Builder OR one Backward in flight at a time, and a strategy at
    most one Verify. Daemon crash → set vanishes; pipelines table only
    holds finished rows so restart is clean.

    `cooldown_until` carries (target_id, kind) → epoch seconds until
    which dispatch is suppressed. Pairs whose cooldown is in the future
    are skipped this tick. Set after a spawn_fast_fail cascade so
    transient claude / network failures don't burst-retry at 2s/call.

    `quota_cooldown_kind` is the kind-wide variant: quota_exhausted is
    provider-level, not target-level — gating one (tid, kind) leaves
    243 other Backwards free to burn through the cap. While a kind is
    cooled here every enqueue of that kind is skipped this tick.

    `scope` (optional SQL LIKE pattern): when set, only enqueue goals
    whose problem matches. Lets a daemon run be restricted to a
    benchmark batch (e.g. `minif2f_%`) without disturbing unrelated
    problems sitting in the same workspace.
    """
    now = time.time()
    cd = cooldown_until or {}
    qcd = quota_cooldown_kind or {}

    def in_flight(tid: str, kind: str) -> int:
        # Phase 2.5 — running key is (target_id, kind, decision_id);
        # batch Inject can have multiple entries with same (tid, kind)
        # but distinct decision_id. Sum across all matching entries.
        running_n = sum(1 for r in running if r[0] == tid and r[1] == kind)
        return running_n + db.queue_count(conn, target_id=tid, kind=kind)

    def cooled(tid: str, kind: str) -> bool:
        return cd.get((tid, kind), 0.0) > now

    def kind_cooled(kind: str) -> bool:
        return qcd.get(kind, 0.0) > now

    # Strategies ready for verify are no longer enqueued as Verify
    # pipelines. They're processed inline in `verify_housekeeping` at
    # the end of each tick.

    # Phase 2 — awaiting_human gate: cache per-problem to avoid N+1
    # queries (one per open goal). A problem with an unresolved
    # RequestUserAmend pauses all dispatch on it until operator
    # resolves the strategist_decisions row.
    awaiting_cache: dict[str, bool] = {}

    def problem_paused(problem: str) -> bool:
        if problem not in awaiting_cache:
            awaiting_cache[problem] = db.problem_has_awaiting_human(
                conn, problem)
        return awaiting_cache[problem]

    # Open goals → enqueue if no in-flight or queued attempt exists.
    # Phase 2 — `pending_strategist_review` goals are excluded from
    # `open_goals` (status='open' filter). `goals.detached=1` goals
    # are included via the CTE seed change in db.open_goals.
    for g in db.open_goals(conn, scope=scope):
        if problem_paused(str(g["problem"])):
            continue
        gid = str(g["id"])
        kind = next_worker_kind(g)
        if kind_cooled(kind):
            continue
        if in_flight(gid, kind) == 0 and not cooled(gid, kind):
            priority = 5 if kind == "Builder" else 2
            db.enqueue(conn, kind=kind, target_id=gid, priority=priority)


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def strategist_triggers(conn: sqlite3.Connection,
                        running: set[tuple[str, str]],
                        *,
                        scope: str | None = None,
                        interval_min: float = 60.0,
                        ) -> None:
    """T0 (first-launch) + T1 (wall-clock routine) enqueues for the
    Strategist pipeline. T2 (pending_review) is handled by
    `_enqueue_strategist_review` at cascade-time, not here.

    T0 condition: `problems.bootstrap_done = 0`.
    T1 condition: `last_strategist_at` older than `interval_min` minutes
                   AND root not terminal.

    Per-problem dedup: skip enqueue if a Strategist (target=root) is
    already running or already in the queue. The awaiting_human gate
    skips Strategist enqueue for problems whose human-input request
    hasn't been resolved.

    Called from `dispatcher.run` once per tick alongside `bfs_refill`.
    """
    max_age_sec = interval_min * 60.0

    def already_inflight(root_id_str: str) -> bool:
        # Phase 2.5 — running key is (target_id, kind, decision_id);
        # Strategist queue rows always have decision_id=None (Strategist
        # is never spawned from an Inject), so a tuple-match by (root,
        # Strategist, *) covers the invariant.
        in_running = any(
            r[0] == root_id_str and r[1] == "Strategist" for r in running
        )
        return (in_running
                or db.is_in_queue(conn, target_id=root_id_str,
                                  kind="Strategist"))

    # T0 — first launch (highest urgency among Strategist triggers)
    for prob, root_id in db.problems_needing_t0(conn, scope=scope):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        rid = str(root_id)
        if already_inflight(rid):
            continue
        # Higher priority than Backward (2) / Builder (5)? Phase 2 spec
        # says Strategist > Backward/Builder but < Verify housekeeping.
        # Verify is inline (not queued), so queue.priority just needs
        # to put Strategist ahead of Backward/Builder.
        db.enqueue(conn, kind="Strategist", target_id=rid,
                   target_kind="Goal", priority=10)

    # T1 — wall-clock routine
    for prob, root_id in db.problems_needing_t1(
        conn, scope=scope, max_age_sec=max_age_sec,
    ):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        rid = str(root_id)
        if already_inflight(rid):
            continue
        db.enqueue(conn, kind="Strategist", target_id=rid,
                   target_kind="Goal", priority=10)


# ---------------------------------------------------------------------
# Worker thread body
# ---------------------------------------------------------------------

def _run_pipeline(workspace: Path, manifests: dict[str, manifest.Manifest],
                  task_kind: str, target_id: str, target_kind: str,
                  pipeline_id: str,
                  decision_id: int | None = None,
                  ) -> tuple[str, str, str, str, str]:
    """Run one pipeline in worker thread. Returns (pipeline_id, kind, target_id,
    target_kind, outcome).

    Side effects:
      - INSERT one finished pipeline row (succeeded/failed)
      - On failure: INSERT dead_attempt row with full artifacts JSON
      - Always rmtree .attempts/<pid>/ + .attempts/_backup_<pid>/ via WorkArea

    Phase 2 — `decision_id` carries the strategist_decisions row id
    when the spawning queue entry came from a Strategist Inject
    decision. Passed through to compile_context for the
    `## Strategist brief` section. BFS-auto-dispatched pipelines have
    decision_id=None.

    NB: opens its own DB conn (sqlite3 thread safety)."""
    import json as _json
    conn = db.connect()
    started_at = db.now()
    try:
        with agent.WorkArea(workspace, pipeline_id) as wa:
            attempts_dir = wa.attempts

            # Phase 2 — Strategist + Forward dispatch.
            #   Strategist: target_kind='Goal', target_id=problem.root.id;
            #     pipeline operates problem-level via root's `problem`
            #     column. decision_id is unused (Strategist EMITS decisions).
            #   Forward:    target_kind='Problem', target_id=problem_name;
            #     decision_id is the Strategist Inject row that spawned
            #     this Forward.
            if task_kind == "Strategist":
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
                problem = str(goal["problem"])
                mfst = manifests[problem]
                # Determine trigger_kind heuristically from problem
                # state (no explicit trigger column on queue rows; the
                # trigger_kind is derived per Phase 2 §2.1 + 2.5):
                #   bootstrap_done=0  → 'first_launch'
                #   unack Inject batch done → 'inject_batch_done'
                #   any pending_strategist_review goal in this problem
                #                     → 'pending_review' + use that goal
                #                       as pending_review_id
                #   otherwise        → 'routine'
                #
                # `inject_batch_done` takes precedence over `pending_
                # review` because a batch completion is the freshest
                # event (Strategist asked for those Forwards specifically
                # to address the pending_review; the batch outcomes
                # belong in that decision context).
                prob_row = conn.execute(
                    "SELECT bootstrap_done FROM problems WHERE name = ?",
                    (problem,),
                ).fetchone()
                bootstrapped = bool(prob_row["bootstrap_done"]) if prob_row else False
                pending_row = conn.execute(
                    "SELECT id FROM goals WHERE problem = ?"
                    "   AND status = 'pending_strategist_review'"
                    " ORDER BY id LIMIT 1",
                    (problem,),
                ).fetchone()
                pending_id = int(pending_row["id"]) if pending_row else None
                unack_batches = (db.unacknowledged_inject_batches(conn, problem)
                                 if bootstrapped else [])
                if not bootstrapped:
                    trigger = "first_launch"
                elif unack_batches:
                    trigger = "inject_batch_done"
                elif pending_id is not None:
                    trigger = "pending_review"
                else:
                    trigger = "routine"

                from ..pipeline import strategist
                r = strategist.run_strategist(
                    conn, problem=problem, trigger_kind=trigger,
                    tick=0,  # tick concept TBD; 0 as placeholder for now
                    workspace=workspace, mfst=mfst,
                    pipeline_id=pipeline_id,
                    pending_review_id=pending_id,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status=status, outcome=r.outcome,
                    started_at=started_at,
                )
                if status == "failed":
                    db.record_dead_attempt(
                        conn, target_id=goal_id, target_kind=target_kind,
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                    )
                return (pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            if task_kind == "Forward":
                # Forward target = problem name (TEXT); no goal lookup.
                problem = target_id
                if problem not in manifests:
                    db.record_pipeline(
                        conn, pipeline_id=pipeline_id, kind=task_kind,
                        target_id=target_id, target_kind=target_kind,
                        status="failed", outcome="failed",
                        started_at=started_at,
                    )
                    return (pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                mfst = manifests[problem]
                from ..pipeline import forward
                r = forward.run_forward(
                    conn, problem=problem, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                    decision_id=decision_id,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status=status, outcome=r.outcome,
                    started_at=started_at,
                )
                # Flush per-retry buffered failures from the retry
                # helper. Phase 2 dead_attempts row for Forward uses
                # target_id=0 + target_kind='Problem' (migration_plan
                # §C option 1: dead_attempts.target_id is INTEGER, so
                # Problem-targeted forensic uses 0 with the audit
                # index living on target_kind + decision_id).
                for pf in r.pending_failures:
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind="Problem",
                        pipeline_id=pipeline_id,
                        failure_reason=pf["reason"],
                        failure_detail=pf["detail"],
                        proposal_md=pf.get("proposal_md", ""),
                        artifacts=(_json.dumps(pf["artifacts"])
                                   if pf.get("artifacts") else ""),
                    )
                # Pipeline-level dead_attempt for the final outcome.
                # Skip when outcome is 'exhausted' — the helper has
                # already buffered the last retry's failure (flushed
                # above); duplicating here would over-count.
                if (status == "failed"
                        and r.outcome != "exhausted"):
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind=target_kind,
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                    )
                return (pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            # Builder / Backward — Goal-targeted.
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
                    decision_id=decision_id,
                )
            elif task_kind == "Backward":
                r = pipeline.run_backward(
                    conn, goal_id=goal_id, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                    decision_id=decision_id,
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

            # Phase 7 — flush per-retry buffered failures from the
            # in-pipeline retry helper. The helper writes one
            # `goals.attempts++` eagerly (for live TREE.md visibility)
            # but buffers the paired dead_attempts row here because
            # dead_attempts.pipeline_id FKs the pipelines row we just
            # INSERTed. Flush only writes the dead_attempts rows; the
            # increment already happened in-helper.
            #
            # Skip flush on outcome='moot': decision 2 mandates moot is
            # uniform no-op (no dead_attempts written). Mid-loop moot
            # detection drops any prior-iteration buffered failures —
            # those were real LLM calls but on a goal that's since gone
            # terminal, so their forensic value is curiosity-only. Note
            # the eager attempts++ from those iterations remains in DB
            # (helper already wrote them); strict decision-2 alignment
            # is at the dead_attempts surface, not the attempts column.
            if r.outcome != "moot":
                for pf in r.pending_failures:
                    db.record_dead_attempt(
                        conn, target_id=goal_id, target_kind="Goal",
                        pipeline_id=pipeline_id,
                        failure_reason=pf["reason"],
                        failure_detail=pf["detail"],
                        proposal_md=pf.get("proposal_md", ""),
                        artifacts=(_json.dumps(pf["artifacts"])
                                   if pf.get("artifacts") else ""),
                    )

            # Capture artifacts from .attempts/<pid>/ before WorkArea rmtree.
            # Skip the pipeline-final dead_attempts INSERT for:
            #   - 'exhausted' outcome: helper already buffered the
            #     last retry's failure into pending_failures (flushed
            #     above); duplicating here would violate the 1:1
            #     attempts ↔ dead_attempts invariant.
            #   - 'superseded' (OR race noise, not a real failure).
            #   - infra reasons (spawn_fast_fail / quota_exhausted /
            #     missing_dep): not agent actions; reason carried back
            #     via the future tuple for cooldown, events.py filters
            #     them anyway.
            if (r.outcome != "exhausted"
                    and r.failure_reason
                    and r.failure_reason not in (
                        "superseded",
                        "spawn_fast_fail",
                        "quota_exhausted",
                        "missing_dep",
                    )):
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

def _pid_alive(pid: int) -> bool:
    """Cross-platform liveness check. POSIX: os.kill(pid, 0); Windows:
    OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION.

    Note: On Windows, os.kill(pid, 0) raises SystemError because sig
    0 isn't a real Windows signal — Python's os.kill on Windows only
    handles termination signals via TerminateProcess."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        kernel32.CloseHandle(h)
        return True
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _acquire_singleton_lock(workspace: Path) -> Path | None:
    """Refuse to start if another daemon is already running on this
    workspace. Two daemons sharing one DB silently dispatch the same
    goal twice, write conflicting strategy rows, and clobber each
    other's verify_strategy state. Caught in the wild when a stray
    `&` background invocation overlapped with a fresh `run`.

    Mechanism: PID file at `.asterism/daemon.pid`. On startup:
      - if file missing → create, return path
      - if file exists + holds a live PID → return None (caller exits)
      - if file exists + holds a dead PID → stale, overwrite

    Returned path should be `.unlink(missing_ok=True)` at shutdown.
    """
    asterism_dir = workspace / ".asterism"
    asterism_dir.mkdir(parents=True, exist_ok=True)
    pid_file = asterism_dir / "daemon.pid"
    my_pid = os.getpid()

    if pid_file.exists():
        try:
            existing = int(pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing = -1
        if existing > 0 and existing != my_pid and _pid_alive(existing):
            print(f"[dispatcher] another daemon (pid={existing}) is "
                  f"already running on this workspace. Kill it or wait "
                  f"for it to exit, then retry. (lock: {pid_file})",
                  file=sys.stderr, flush=True)
            return None

    pid_file.write_text(str(my_pid), encoding="utf-8")
    return pid_file


def run(workspace: Path, *, once: bool = False,
        scope: str | None = None) -> int:
    pid_lock = _acquire_singleton_lock(workspace)
    if pid_lock is None:
        return 1
    import atexit
    atexit.register(lambda: pid_lock.unlink(missing_ok=True))

    global BUILDER_THRESHOLD, SHELVE_THRESHOLD
    pool_size = config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=workspace)
    budget_sec = config.get(
        "dispatch.budget_sec", default=1800,
        env_var="ASTERISM_BUDGET_SEC", cast=int, workspace=workspace)
    # BUILDER_THRESHOLD semantically belongs to the Builder kind
    # (controls Builder→Backward transition based on Builder model
    # strength). Canonical key: `builder.threshold`. Old
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
    # Phase 2 — T1 (wall-clock routine) interval in minutes. Default 60
    # per `docs/phase2/pipelines.md` §5. Picked by `strategist_triggers`
    # each tick. Override via env var or Asterism.yaml for calibration.
    strategist_interval_min = config.get(
        "strategist.interval_min", default=60.0,
        env_var="ASTERISM_STRATEGIST_INTERVAL_MIN", cast=float,
        workspace=workspace,
    )
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
    # this daemon. Passive trigger means at most one of each kind per
    # target, so the pair is a unique key. Daemon crash → set vanishes →
    # restart sees clean slate.
    running: set[tuple[str, str]] = set()
    # Per-(target_id, kind) cooldown until epoch seconds. Set after
    # a spawn_fast_fail cascade; bfs_refill skips cooled pairs so the
    # daemon doesn't burst-retry a broken claude.exe at 2s/call.
    cooldown_until: dict[tuple[str, str], float] = {}
    # Global counter of consecutive spawn_fast_fail outcomes (across
    # all targets). Reset by any non-fast-fail cascade. If it crosses
    # CONSEC_SPAWN_FAIL_LIMIT the daemon exits with a clear message —
    # claude.exe is persistently broken and human attention is required.
    consec_fast_fails = 0
    SPAWN_COOLDOWN_SEC = 30.0
    CONSEC_SPAWN_FAIL_LIMIT = 10
    # Independent counter for gateway_unreachable. d2dd861 prevents
    # transient gateway hiccups from charging goal attempts (good),
    # but a PERMANENT gateway death (e.g. accept loop crashed) means
    # every dispatch instantly hits WinError 10061 → 30s cooldown →
    # re-dispatch → new strategy row → infinite loop. Run #17 cut at
    # +52min after 48 strategies piled up on 2 hard goals. The
    # circuit breaker exits when consecutive gateway-unreachable
    # crosses CONSEC_GATEWAY_UNREACHABLE_LIMIT — daemon refuses to
    # busy-loop against a dead gateway and forces operator attention.
    consec_gateway_unreachable = 0
    CONSEC_GATEWAY_UNREACHABLE_LIMIT = 8
    # Per-kind quota backoff (#103). quota_exhausted is provider-level,
    # not target-level — gating one (tid, kind) leaves all other targets
    # of the same kind free to keep hammering. Backoff doubles on each
    # consecutive quota_exhausted for that kind, capped at 600s; any
    # non-quota outcome (success or agent-side failure) resets the
    # counter and clears the per-kind cooldown so dispatch resumes.
    consec_quota_per_kind: dict[str, int] = {}
    quota_cooldown_kind: dict[str, float] = {}
    QUOTA_BACKOFF_BASE_SEC = 30.0
    QUOTA_BACKOFF_CAP_SEC = 600.0

    conn = db.connect()
    # Idempotent — picks up additive migrations on an existing DB
    # without requiring `cli init` / `cli reset`. SCHEMA itself is
    # CREATE TABLE IF NOT EXISTS, and ALTER TABLE ADD COLUMN entries
    # swallow "duplicate column name". Required because the daemon
    # is the long-running consumer of the DB on a workspace that
    # was init'd against an earlier schema version.
    db.init_schema(conn)
    manifests: dict[str, manifest.Manifest] = {}
    for row in conn.execute("SELECT name, manifest_path FROM problems"):
        manifests[row["name"]] = manifest.parse(workspace / row["manifest_path"])

    _recover_at_startup(conn, workspace)

    # Spawn-sandbox sweep: clean any orphan sandboxes left by SIGKILL'd
    # spawns from a prior daemon run (per docs/archive/spawn_sandbox.md §3.3).
    # Runs after _recover_at_startup so DB state is consistent before
    # filesystem state is reconciled. Sweep skips sandboxes whose owner
    # daemon is alive (guards against concurrent daemons).
    from ..agent import sandbox as _spawn_sandbox
    _sb_counters = _spawn_sandbox.sweep_orphan_sandboxes(workspace)
    if any(_sb_counters[k] for k in
           ("rolled_back", "deleted_committed", "corrupt_manifest",
            "drift_warnings", "skipped_alive_owner")):
        print(f"[sandbox-sweep] startup: {_sb_counters}", flush=True)

    # Refresh BRIEF.md for every registered problem at startup. Covers
    # Manifest edits + Library promotes since the last daemon run
    # (daemon has no hot-reload; startup is the canonical refresh point).
    # Lemma resolution can take ~30s when Manifest hints are dense; only
    # paid once per startup, off the dispatch path.
    from ..state import brief
    brief.write_for_all_problems(conn, workspace, manifests)

    scope_label = f", scope={scope!r}" if scope else ""
    print(f"[dispatcher] start, pool={pool_size}, "
          f"problems={list(manifests)}{scope_label}",
          flush=True)
    start_time = time.time()

    # Phase 1 gateway: launch long-living LSP HTTP MCP server, wait
    # until backend pre-warm completes (mathlib loaded). Per-spawn MCP
    # config will point at this gateway via HTTP; spawns no longer
    # fork their own lake serve. Cold start ~30-145s amortized once
    # per daemon startup. start_gateway registers an atexit handler so
    # the subprocess dies with the daemon — we don't need to track the
    # Popen ourselves here.
    from ..lsp import lifecycle as gateway_lifecycle
    gateway_lifecycle.start_gateway(workspace)

    while True:
        # Cascade for any completed pipelines
        if futures:
            done, _ = wait(list(futures), timeout=0, return_when=FIRST_COMPLETED)
            for fut in done:
                meta = futures.pop(fut)
                # meta = (pipeline_id, kind, target_id, target_kind,
                #        decision_id). Phase 2.5 — running key includes
                # decision_id so batch Inject siblings (same target+kind,
                # different decision_id) don't share a slot.
                running.discard((meta[2], meta[1], meta[4]))
                meta_decision_id = meta[4]
                try:
                    pid, kind, tid, tk, outcome, reason = fut.result()
                    cascade_one(conn, pipeline_id=pid, kind=kind,
                                target_id=tid, target_kind=tk,
                                outcome=outcome, failure_reason=reason,
                                decision_id=meta_decision_id)
                    # Back-off + global counter for spawn fast-fails.
                    # Phase 7 — quota_exhausted (rc=126) / missing_dep (rc=127)
                    # also cooldown but do NOT contribute to CONSEC tracking
                    # (quota recovers on its own; missing_dep is operator-fix).
                    # #103 — quota_exhausted is now handled separately with
                    # per-kind exponential backoff: provider rate limit is
                    # provider-level, not target-level, so the per-(tid, kind)
                    # cooldown alone leaves 200+ siblings of the same kind
                    # free to drain the queue and burn the cap.
                    if outcome == "failed" and reason == "quota_exhausted":
                        n = consec_quota_per_kind.get(kind, 0) + 1
                        consec_quota_per_kind[kind] = n
                        backoff = min(
                            QUOTA_BACKOFF_BASE_SEC * (2 ** (n - 1)),
                            QUOTA_BACKOFF_CAP_SEC,
                        )
                        quota_cooldown_kind[kind] = time.time() + backoff
                        # Flush queued entries of this kind so the
                        # pop loop doesn't keep draining the backlog
                        # against an exhausted provider (each pop
                        # would re-fire and bump consec further).
                        flushed = db.flush_queue_kind(conn, kind=kind)
                        print(f"[cooldown] {kind} quota_exhausted "
                              f"(consec={n}, backoff={backoff:.0f}s, "
                              f"flushed={flushed} queued; all {kind} "
                              f"dispatch suspended)", flush=True)
                    elif outcome == "failed" and reason in (
                        "spawn_fast_fail", "missing_dep",
                        "gateway_unreachable", "transient_timeout",
                    ):
                        cooldown_until[(tid, kind)] = (
                            time.time() + SPAWN_COOLDOWN_SEC)
                        if reason == "spawn_fast_fail":
                            consec_fast_fails += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"spawn_fast_fail "
                                  f"(consec={consec_fast_fails})", flush=True)
                            if consec_fast_fails >= CONSEC_SPAWN_FAIL_LIMIT:
                                print(f"[dispatcher] {consec_fast_fails} "
                                      f"consecutive spawn_fast_fails — "
                                      f"claude.exe or provider appears broken; "
                                      f"exiting. Inspect "
                                      f".attempts/<pid>/_spawn.stderr "
                                      f"for the underlying error.", flush=True)
                                pool.shutdown(wait=False, cancel_futures=True)
                                return 2
                        elif reason == "gateway_unreachable":
                            consec_gateway_unreachable += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"gateway_unreachable "
                                  f"(consec={consec_gateway_unreachable})",
                                  flush=True)
                            if (consec_gateway_unreachable
                                    >= CONSEC_GATEWAY_UNREACHABLE_LIMIT):
                                print(f"[dispatcher] "
                                      f"{consec_gateway_unreachable} "
                                      f"consecutive gateway_unreachable — "
                                      f"gateway appears permanently dead; "
                                      f"exiting. Restart daemon (gateway "
                                      f"will be re-launched) and inspect "
                                      f".asterism/logs/gateway.log for the "
                                      f"underlying crash.", flush=True)
                                pool.shutdown(wait=False, cancel_futures=True)
                                return 2
                        else:
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after {reason}",
                                  flush=True)
                    else:
                        consec_fast_fails = 0
                        consec_gateway_unreachable = 0
                        # #103 — any non-quota, non-infra outcome on this
                        # kind proves the provider responded: clear the
                        # per-kind quota backoff so dispatch resumes
                        # fresh. (Other infra reasons above are orthogonal
                        # to quota — handled in their own branch and don't
                        # touch quota state.)
                        if kind in consec_quota_per_kind:
                            consec_quota_per_kind.pop(kind, None)
                            quota_cooldown_kind.pop(kind, None)
                            print(f"[cooldown] {kind} quota state reset "
                                  f"(non-quota outcome confirms provider "
                                  f"responsive)", flush=True)
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
                    #
                    # Classify first: transport-level errors (gateway
                    # unreachable / conn refused / network reset) are
                    # infrastructure failures, not the goal's fault.
                    # Route through the _INFRA_REASONS short-circuit so
                    # attempts stay unchanged AND the per-target cooldown
                    # below kicks in.
                    pid, kind, tid, tk, _did = meta
                    infra_reason = _classify_worker_exception(exc)
                    label = (f"{infra_reason} (no attempts++)"
                             if infra_reason else "treating as failed")
                    print(f"[cascade] worker exception on {kind} "
                          f"{tk}={tid}: {exc}; {label}",
                          flush=True)
                    try:
                        cascade_one(conn, pipeline_id=pid, kind=kind,
                                    target_id=tid, target_kind=tk,
                                    outcome="failed",
                                    failure_reason=infra_reason,
                                    decision_id=_did)
                        tree.write_for_target(conn, workspace, tid, tk)
                        # Mirror the normal-result cooldown path so
                        # gateway-unreachable / transient_timeout also
                        # yield a 30s back-off — without this, the same
                        # Backward gets re-dispatched on the next tick
                        # and re-fails.
                        if infra_reason == "transient_timeout":
                            cooldown_until[(tid, kind)] = (
                                time.time() + SPAWN_COOLDOWN_SEC)
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"transient_timeout (slot contention "
                                  f"or RPC budget exceeded; no consec "
                                  f"increment — circuit breaker reserved "
                                  f"for true gateway death)",
                                  flush=True)
                        elif infra_reason == "gateway_unreachable":
                            cooldown_until[(tid, kind)] = (
                                time.time() + SPAWN_COOLDOWN_SEC)
                            consec_gateway_unreachable += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"gateway_unreachable "
                                  f"(consec={consec_gateway_unreachable})",
                                  flush=True)
                            if (consec_gateway_unreachable
                                    >= CONSEC_GATEWAY_UNREACHABLE_LIMIT):
                                print(f"[dispatcher] "
                                      f"{consec_gateway_unreachable} "
                                      f"consecutive gateway_unreachable — "
                                      f"gateway appears permanently dead; "
                                      f"exiting. Restart daemon (gateway "
                                      f"will be re-launched) and inspect "
                                      f".asterism/logs/gateway.log for the "
                                      f"underlying crash.", flush=True)
                                pool.shutdown(wait=False, cancel_futures=True)
                                return 2
                    except Exception as exc2:
                        # Cascade itself bombing is a deeper bug; log
                        # but don't crash the daemon (other work may
                        # still progress).
                        print(f"[cascade] secondary exception during "
                              f"recovery: {exc2}", flush=True)

        # Strategy verify housekeeping. Runs after cascade so any
        # newly-proved sub-goals from this tick contribute to the
        # `ready_for_verify` poll. Inline + recursive (chain follow-up
        # for multi-layer strategies in one tick).
        verify.verify_housekeeping(conn, workspace=workspace,
                                   manifests=manifests)

        # Per-problem post-proved gate. Only problems whose root just
        # flipped to 'proved' AND haven't yet passed integrity_gate
        # under this DB are visited — `db.unverified_proved_roots`
        # returns at most that subset, dropping to [] once every root
        # is verified. The earlier formulation iterated `manifests`
        # every tick and paid one gateway-driven axiom_probe per
        # proved root every loop iteration (244 miniF2F roots stalled
        # dispatch for ~115min on every restart); the marker in
        # `goals.integrity_verified` is what keeps this O(unverified)
        # instead of O(all proved). Rollback paths flip the marker off
        # transparently via `db.update_goal_status` whenever a goal
        # leaves 'proved', so a once-failed root re-enters this gate
        # on the next tick after cascade rollback.
        for problem_name in db.unverified_proved_roots(conn):
            if problem_name not in manifests:
                # Root proved for a problem we don't have a Manifest
                # for in-process (CLI invoked with a scope filter that
                # excluded it, or DB row outlived its Manifest dir).
                # Skip without flipping the marker — it'll get picked
                # up the next run that loads this Manifest.
                continue
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
            # Root integrity gate — single root-level axiom_probe under
            # verify-collapse. Sets `integrity_verified=1` on success
            # so subsequent ticks skip this problem. On sorryAx
            # detection, rolls back the cascade chain via
            # `verify.rollback_cascade_chain`, which leaves the
            # culprit goal in 'open' state and (via update_goal_status)
            # clears integrity_verified on the root so the gate fires
            # again once a fresh proof cascades back up.
            verify.root_integrity_gate(
                conn, workspace, problem_name, manifests[problem_name])
            # Final TREE.md refresh — the per-cascade write_for_target
            # ran before the verify_housekeeping that cascade-proved
            # the root, leaving TREE.md frozen at root=attempting.
            tree.write(conn, workspace, problem_name)

        # Workspace-wide exit: when every problem's root is proved.
        # `verify.root_integrity_gate` above may have called
        # `rollback_cascade_chain` on sorryAx detection, reverting a
        # root to 'attempting'; in that case this check fails and the
        # dispatcher loop continues for re-Backward.
        if db.root_proved(conn):
            print("[dispatcher] all roots proved", flush=True)
            pool.shutdown(wait=False, cancel_futures=True)
            return 0

        # Refill queue (uses in-memory `running` for dedup; cooldown_until
        # holds spawn_fast_fail back-offs; quota_cooldown_kind holds the
        # per-kind quota backoff (#103); scope restricts to a benchmark
        # subset like `minif2f_%`).
        bfs_refill(conn, running, cooldown_until, scope=scope,
                   quota_cooldown_kind=quota_cooldown_kind)

        # Phase 2 — Strategist T0/T1 triggers (T2 fires at cascade time
        # in `cascade_one`, not here). Skipped under awaiting_human gate
        # per-problem inside `strategist_triggers`. Defaults to 60-min
        # routine (`strategist.interval_min` in Asterism.yaml).
        strategist_triggers(conn, running, scope=scope,
                            interval_min=strategist_interval_min)

        # Spawn from queue while pool has slots. Skip if a pipeline of
        # the same (target_id, kind) is already in flight in this
        # daemon — bfs_refill caps at 1 but daemon recovery + race
        # corners mean defense-in-depth here is cheap.
        while len(futures) < pool_size:
            row = db.pop_queue(conn)
            if row is None:
                break
            target_id = str(row["target_id"])
            kind = str(row["kind"])
            # Phase 2 — queue.target_kind defaults to 'Goal' (post-
            # migration column), and queue.decision_id is non-NULL when
            # this row was emitted by a Strategist Inject decision.
            # Both default-safe for pre-Phase 2 queue rows (target_kind
            # has DEFAULT 'Goal', decision_id NULL). Decision_id must
            # be read BEFORE the running-dedup check below so the
            # 3-tuple key is complete (Phase 2.5: batch Inject siblings
            # share target+kind but differ by decision_id).
            try:
                target_kind = str(row["target_kind"]) or "Goal"
            except (IndexError, KeyError):
                target_kind = "Goal"
            try:
                _did = row["decision_id"]
                decision_id = int(_did) if _did is not None else None
            except (IndexError, KeyError):
                decision_id = None
            if (target_id, kind, decision_id) in running:
                continue
            # #103 — defense-in-depth: even after bfs_refill skips
            # cooled kinds, a race (cooldown set between bfs_refill
            # and pop) could leave a queued row for a now-cooled
            # kind. Drop it; bfs_refill will repopulate post-cooldown.
            if quota_cooldown_kind.get(kind, 0.0) > time.time():
                continue
            pipeline_id = agent.new_pipeline_id()
            running.add((target_id, kind, decision_id))
            fut = pool.submit(_run_pipeline, workspace, manifests,
                              kind, target_id, target_kind, pipeline_id,
                              decision_id)
            futures[fut] = (pipeline_id, kind, target_id, target_kind,
                            decision_id)
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

        # Periodic TREE.md refresh — cascade-only writes leave the tree
        # frozen during long Builder/Backward spawns (5-15min under LSP).
        # Cheap render + atomic replace; failures are swallowed inside
        # tree.write_for_target's caller pattern but tree.write itself
        # raises, so guard here.
        for problem_name in manifests:
            try:
                tree.write(conn, workspace, problem_name)
            except Exception as exc:
                print(f"[tree] periodic write skipped for "
                      f"{problem_name}: {exc}", flush=True)

        if time.time() - start_time > budget_sec:
            print(f"[dispatcher] {budget_sec}s budget exceeded; stopping",
                  flush=True)
            pool.shutdown(wait=False, cancel_futures=True)
            return 1


