"""Main dispatcher loop. Cascade in main thread, pipelines in pool.

See architecture.md §7-§8.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import dataclass, field
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

from .. import agent, pipeline
from . import config
from ..state import db, manifest, transitions, tree
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

# A Librarian chain step (dedup/classify/migrate/bridge) that fails
# after its own internal session-retries is re-enqueued up to this many times
# (the next tick re-derives the same step), then the chain stalls and is left
# for the operator — bounds a genuinely-stuck step from looping forever while
# still surviving a transient gateway/harness failure.
# LIBRARIAN_MAX_CHAIN_RETRIES moved to librarian_sched (re-exported below).
from .librarian_sched import (  # noqa: E402 — historical names, tests + runbooks use them
    LIBRARIAN_MAX_CHAIN_RETRIES,
    _LIB_SEP,
    _advance_librarian_chain,
    _derive_librarian_work,
    _harvest_outstanding,
    _lib_decode,
    _lib_encode,
    _librarian_index_has,
    _librarian_invalidate_index,
    _librarian_refill,
    _librarian_selfstart_problems,
)


def _exit_pool_fast(pool: ThreadPoolExecutor) -> None:
    """Shutdown pool from an abort path (budget exceeded / gateway
    permadown / root proved). `pool.shutdown(wait=False)` is not enough
    on its own — when the caller subsequently `return`s from the main
    loop, Python's `concurrent.futures._python_exit` atexit hook joins
    every still-active worker thread regardless of the wait flag, and
    each worker blocks in `proc.wait(timeout=req.timeout_sec)` until
    its claude subprocess hits the per-spawn cap (default 960s). With
    pool_size workers all mid-spawn at abort time, total shutdown wall
    grew to ~16min × pool_size before the bash wrapper saw the daemon
    exit and the harness fired its task-notification (2026-05-27
    Banach-Tarski run: observed ~30min shutdown).

    Fix: kill every in-flight claude subprocess via
    `claude_cli.request_shutdown`. Workers unblock from `proc.wait`,
    return through their normal dead_attempt cleanup paths (per-thread
    DB conns make this concurrent-safe), and on next retry-loop entry
    see the shutdown event and bail with `daemon_shutdown`. Pool joins
    in seconds; atexit cleanup (gateway terminate, pid_lock unlink)
    runs as designed.
    """
    from ..llm import claude_cli
    killed = claude_cli.request_shutdown()
    if killed:
        print(f"[dispatcher] killed {killed} in-flight claude "
              f"subprocess(es) to unblock worker shutdown",
              flush=True)
    pool.shutdown(wait=True, cancel_futures=True)
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
# State-transition machine relocated to state/transitions.py (#11 P2).
# Re-exported under the original names so callers / tests that reference
# `dispatcher.<name>` (verify, strategist, the test suite) keep working.
from ..state.transitions import (  # noqa: E402,F401
    _cascade_shelve_descendants,
    _set_goal_terminal_and_propagate,
    _record_inject_decision_outcome,
    _maybe_enqueue_inject_batch_done,
    _enqueue_strategist_review,
    _has_hard_terminal_ancestor,
    _has_terminal_disproved_ancestor,
    _has_dead_strategy_in_chain,
    _inward_kill_strategies,
    _maybe_stall_parent_strategies,
    _propagate_shelve,
    _kill_upward_chain,
    _reconcile_goal_after_strategy_loss,
    _propagate_disproved,
    _propagate_dead,
    cascade_one,
)


def next_worker_kind(goal: sqlite3.Row) -> str:
    """Pure-ish: input goal row → 'Builder' or 'Backward'.

    Routing is `entry_kind`-driven with an attempts-threshold safety net.
    While attempts < `BUILDER_THRESHOLD` we honor the `entry_kind`
    directive (`'Builder'` | `'Backward'`); once attempts reach the
    threshold, escalation to Backward is forced (safety net for an
    entry_kind=Builder directive that turns out wrong).

    `entry_kind` is set by:
      - cli init for the root goal: hardcoded to `'Backward'`. Root
        entry is gated by Strategist's `first_launch` trigger before
        any Builder/Backward dispatch; the `## Entry kind` Manifest
        section was dropped in Phase 2 (see manifest.py module header).
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




# ---------------------------------------------------------------------
# BFS queue refill
# ---------------------------------------------------------------------

def _problem_of_target(conn: sqlite3.Connection, target_id: str,
                       target_kind: str) -> str | None:
    """Resolve the Asterism problem name for a dispatch target.
    Forward targets the problem directly (target_kind='Problem',
    target_id=problem name); everything else targets a goal whose
    `problem` column we look up."""
    if target_kind == "Problem":
        # Strip a Librarian per-file suffix (problem\x1ffile); a plain
        # problem (Forward / phase-step Librarian) is returned unchanged.
        return _lib_decode(target_id)[0]
    try:
        g = db.get_goal(conn, int(target_id))
    except (TypeError, ValueError):
        return None
    return g["problem"] if g else None


def _verify_problem(workspace: Path, problem: str) -> bool:
    """Lake-build the problem's Defs.lean + Root.lean — whichever exist.
    Present files must type-check cleanly. Phase 6: both files are
    OPTIONAL (pure-NL problems ship neither; Root-only and Defs-only
    are valid shapes), so a missing file is simply skipped and a
    problem with neither passes vacuously. Lazy verification gate: run
    on first dispatch for the problem this daemon run; cached in-memory
    thereafter.

    Why lazy (vs at-startup): wide-scope daemons (e.g. miniF2F=244
    problems) would pay 30-60min upfront. Lazy pays only for problems
    that actually get dispatched (BFS may never touch a problem whose
    parent is dead/shelved). Per-problem ~5-15s amortizes over a long
    run.
    """
    pdir = db.problem_dir(workspace, problem)
    defs_path = pdir / "Defs.lean"
    root_path = pdir / "Root.lean"
    present = [p for p in (defs_path, root_path) if p.exists()]
    if not present:
        print(f"[verify] {problem}: OK (pure-NL — no Defs/Root)",
              flush=True)
        return True
    from ..pipeline._lake import lake_build_modules, lean_path_to_module
    modules = [lean_path_to_module(workspace, p) for p in present]
    ok, msg = lake_build_modules(workspace, modules)
    if not ok:
        snippet = (msg or "")[:500]
        print(f"[verify] {problem}: FAILED\n{snippet}", flush=True)
    else:
        print(f"[verify] {problem}: OK", flush=True)
    return ok


def _dispatch_is_duplicate(running: "set[tuple]", target_id: str,
                           kind: str, decision_id: int | None) -> bool:
    """Dispatch-time dedup at the single pop-loop chokepoint every source
    funnels through (organic bfs_refill, Strategist Inject, recovery /
    `null_inject_redispatch_specs`). An exact (target, kind, decision_id)
    match is always a duplicate.

    Builder additionally caps at ONE per goal regardless of decision_id:
    it proves IN PLACE, writing the goal's single `proofs/L_<slug>.lean`
    directly (builder.py commit window) — unlike Backward, whose parallel
    OR-node decompositions each write an isolated `_strategy_<sid>.lean`
    and are intentionally allowed to run in parallel (distinct
    decision_id). Two Builders on one goal race that single file: a loser
    that fails *after* the winner committed restores its start-of-run
    sorry-stub snapshot over the winner's proof (`_restore_goal_lean`),
    leaving DB='proved' but file=stub — the Jordan-5/25 drift class, only
    caught end-of-run by axiom_probe. The (target, kind, decision_id) key
    misses this because an organic Builder (decision_id=None) and a
    routine/recovery-injected Builder (decision_id set) are distinct keys;
    collapse Builder to (target, 'Builder') so the second never spawns."""
    if (target_id, kind, decision_id) in running:
        return True
    if kind == "Builder" and any(
            r[0] == target_id and r[1] == "Builder" for r in running):
        return True
    return False


def bfs_refill(conn: sqlite3.Connection,
               running: set[tuple[str, str]],
               cooldown_until: dict[tuple[str, str], float] | None = None,
               *,
               scope: str | None = None,
               quota_cooldown_kind: dict[str, float] | None = None,
               verified_problems: dict[str, bool] | None = None,
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

    def goal_has_any_pipeline(tid: str) -> bool:
        # 2026-05-28: any queued or running pipeline (of any kind) on
        # the same goal blocks bfs_refill from enqueueing another.
        # Strategist Inject(Backward|Builder) already enqueues a row at
        # commit time; without this guard bfs_refill would still pick
        # up the goal on the next tick and enqueue an organic-routing
        # pipeline of a different kind, racing the Inject (LU lu_step_
        # assembly 2026-05-28 — Strategist Inject(Builder) + bfs_refill
        # parallel Backward).
        #
        # Inject's OR-fanout semantic isn't lost: a Strategist batch can
        # still emit multiple Injects on the same target by emitting
        # them itself; bfs_refill's job is organic routing, and organic
        # routing should defer to whatever Strategist already authored.
        if any(r[0] == tid for r in running):
            return True
        row = conn.execute(
            "SELECT 1 FROM queue WHERE target_id = ? LIMIT 1", (tid,),
        ).fetchone()
        return row is not None

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
    vp = verified_problems if verified_problems is not None else {}
    for g in db.open_goals(conn, scope=scope):
        problem = str(g["problem"])
        # Lazy-verify quarantine: a problem whose Defs.lean / Root.lean
        # failed a prior dispatch's verify is skipped here (and at the
        # pop site, defense in depth) so worker spawns don't burn quota
        # on a broken spec. `True` and `unset` both fall through; only
        # explicit `False` triggers the skip.
        if vp.get(problem, True) is False:
            continue
        if problem_paused(problem):
            continue
        gid = str(g["id"])
        # Strategist Inject (or a prior bfs_refill enqueue of any kind)
        # already covers this goal — defer organic routing this tick.
        if goal_has_any_pipeline(gid):
            continue
        kind = next_worker_kind(g)
        if kind_cooled(kind):
            continue
        if in_flight(gid, kind) == 0 and not cooled(gid, kind):
            priority = 5 if kind == "Builder" else 2
            db.enqueue(conn, kind=kind, target_id=gid, priority=priority)


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def _strategist_inflight(conn: sqlite3.Connection, problem: str,
                         running: "set[tuple]") -> bool:
    """A Strategist for this problem is already running or queued — the
    per-problem serialization invariant (one Strategist per problem at a
    time; Strategist mutates problem-global state — `strategist_directive`
    overwrite-on-write, goal/strategy status, cross-decision coherence — so
    concurrent runs would race). Checks BOTH the in-memory `running` set
    (in-flight) AND the DB queue (pending); the cascade-time
    `_enqueue_strategist_review` checked only the queue, which is the gap
    `reconcile_stuck_states` closes.

    Phase 6 — Strategist rows are problem-keyed (target_id=problem name,
    target_kind='Problem', mirroring Forward): the old root-goal key made
    every trigger JOIN on origin='root', so a pure-NL problem (no root)
    could never wake a Strategist. Running key is (target_id, kind,
    decision_id); Strategist rows always have decision_id=None (never
    spawned from an Inject), so a match by (problem, 'Strategist', *)
    covers the invariant."""
    in_running = any(
        r[0] == problem and r[1] == "Strategist" for r in running
    )
    return (in_running
            or db.is_in_queue(conn, target_id=problem, kind="Strategist"))


def reconcile_stuck_states(conn: sqlite3.Connection,
                           running: "set[tuple]",
                           *, scope: str | None = None) -> None:
    """Per-tick safety net for mid-run stuck states that no other reconciler
    re-triggers and that can persist in a LIVE daemon (not only across a
    crash, which `recover_at_startup` handles).

    Two classes, both confirmed reachable mid-run and unrecoverable without
    this (investigation 2026-06-13):

      1. `pending_strategist_review` goals whose cascade-time Strategist
         enqueue was deduped (L355 queue-only race), lost, or dropped — there
         is no restart recovery for these, so they orphan permanently (P13
         left 2/3 stuck; BT g3246 waited 30+ min for the accidental 120-min
         T1). Enqueue a Strategist; the spawn's `_derive_strategist_trigger`
         sees the pending goal and runs a `pending_review` wake.

      2. NULL-outcome Inject decisions whose worker died on infra failure
         with no artifact — this wedges the WHOLE problem (the in-flight-
         batch clause suppresses T0/T1/T4), recoverable otherwise only at
         restart. Re-enqueue the worker.

    Both are IN-FLIGHT GATED: an item whose worker is live (in `running`) or
    already queued is skipped, so this never double-dispatches. That gating
    is the only thing this adds over the startup-recovery logic it shares
    (`db.null_inject_redispatch_specs`), which runs against a clean slate."""
    # 1 — pending_review: enqueue Strategist (spawn derives the trigger).
    for prob in db.problems_with_pending_review(conn, scope=scope):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, prob, running):
            continue
        db.enqueue(conn, kind="Strategist", target_id=prob,
                   target_kind="Problem", priority=20)

    # 1.5 — settled NULL-outcome Inject decisions: the produced goal/
    # strategy already terminated (or a Backward inject's strategy is
    # 'proposed' but wedged with zero alive subgoals — a soft-shelved
    # subgoal awaiting a Reopen that this very NULL outcome blocks by
    # suppressing T4). Resolve the outcome so the batch completes, fires
    # inject_batch_done, and stops suppressing the stall trigger.
    # Complements step 2 below (worker died with no artifact → re-dispatch);
    # the two are disjoint by the produced goal/strategy state.
    db.reconcile_settled_inject_outcomes(conn, scope=scope)

    # 2 — NULL-outcome Inject: re-enqueue the worker, in-flight gated.
    for spec in db.null_inject_redispatch_specs(conn, scope=scope):
        did = spec["decision_id"]
        if any(len(r) > 2 and r[2] == did for r in running):
            continue  # a worker for this Inject is live this run
        if db.queue_has_decision(conn, did):
            continue  # already queued (e.g. cascade-time L967 re-enqueue)
        db.enqueue(conn, kind=spec["kind"], target_id=spec["target_id"],
                   target_kind=spec["target_kind"], priority=10,
                   decision_id=did)


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def strategist_triggers(conn: sqlite3.Connection,
                        running: set[tuple[str, str]],
                        *,
                        scope: str | None = None,
                        interval_min: float = 60.0,
                        daemon_start_iso: str | None = None,
                        ) -> None:
    """T1 (routine) + T4 (stall) enqueues for the Strategist pipeline.
    T2 (pending_review) is handled by `_enqueue_strategist_review` at
    cascade-time, not here.

    Phase 6 — T0 (first_launch) is RETIRED: a fresh problem has no
    dispatchable work and no committed Ingest, so it is structurally
    STALLED and T4 wakes the Strategist immediately (the wake runs under
    the `inject_batch_done` prompt, whose mandatory-advance rule forces
    the first Inject). Priority stays: queue.priority just needs to put
    Strategist ahead of Backward (2) / Builder (5).

    T1 condition: `last_routine_at` (the routine-only clock, not reset by
                   event-driven triggers) older than `interval_min` minutes of
                   running time (paused/down time excluded via
                   `daemon_start_iso`), AND no committed Ingest.

    Per-problem dedup: skip enqueue if a Strategist (target=problem) is
    already running or already in the queue. The awaiting_human gate
    skips Strategist enqueue for problems whose human-input request
    hasn't been resolved.

    Called from `dispatcher.run` once per tick alongside `bfs_refill`.
    """
    max_age_sec = interval_min * 60.0

    # T1 — routine audit (own running-time cadence; see problems_needing_t1)
    for prob in db.problems_needing_t1(
        conn, scope=scope, max_age_sec=max_age_sec,
        since_iso=daemon_start_iso,
    ):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, prob, running):
            continue
        db.enqueue(conn, kind="Strategist", target_id=prob,
                   target_kind="Problem", priority=10)

    # T4 — structural stall trigger.
    # Fires when a problem has no open goals (BFS has nothing to
    # dispatch), no in-flight Backward/Builder/Forward worker, and
    # the root is not yet proved. Captures the failure mode polar
    # 2026-05-23 hit: a parent strategy with a shelved sub-goal sat
    # 'proposed' forever, parent goal stayed 'attempting' (filtered
    # out of `open_goals`), no spawn fired for 174 min until budget
    # exhaust. Routine T1 (60 min) eventually fires but Strategist
    # Noop'd 4 times because the snapshot ("X proved") didn't change
    # between ticks. T4 is the structural backstop: if we hit this
    # signal we KNOW the framework is deadlocked, so we wake
    # Strategist immediately + surface the stall in Context.md (see
    # `_section_stall_warning` in phase2_context). Strategist prompt
    # has the corresponding rule: don't Noop when stall section is
    # present.
    for prob in db.problems_stalled(conn, scope=scope, running=running):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, prob, running):
            continue
        db.enqueue(conn, kind="Strategist", target_id=prob,
                   target_kind="Problem", priority=10)


# ---------------------------------------------------------------------
# Worker thread body
# ---------------------------------------------------------------------

def _derive_strategist_trigger(conn: sqlite3.Connection,
                                problem: str) -> tuple[str, int | None]:
    """Pick `trigger_kind` for a Strategist run on `problem`. Returns
    `(trigger, pending_review_id)` where pending_review_id is non-None
    iff trigger is 'pending_review'.

    Priority order (Phase 2 §2.1 + 2.5 + 5; Phase 6 retires first_launch):

      1. `inject_batch_done` — unacknowledged Inject batch resolved.
         A batch completion is the freshest event; Strategist must
         decide follow-up (Reopen / Inject / etc) before any other
         reasoning, even if root happens to be frozen meanwhile.
      2. `pending_review` — at least one goal in pending_strategist_
         review status. A goal explicitly waiting on a verdict is more
         focused than a generic status check.
      3. `inject_batch_done` again, on a structural STALL — the "empty
         batch done" reading (Phase 6, first_launch's replacement): a
         fresh problem (nothing dispatchable yet) and a deadlocked one
         are the same situation as a resolved batch with everything
         settled — the Strategist must advance the plan, and only
         inject_batch_done.md carries the mandatory-advance rule
         ("stalled → commit at least one Inject"). routine.md does not,
         so classifying these wakes as routine invites a Noop →
         re-stall → re-wake livelock (P13 2026-06-13 shape).
      4. `routine` — default; wall-clock check-in.
    """
    pending_row = conn.execute(
        "SELECT id FROM goals WHERE problem = ?"
        "   AND status = 'pending_strategist_review'"
        " ORDER BY id LIMIT 1",
        (problem,),
    ).fetchone()
    pending_id = int(pending_row["id"]) if pending_row else None
    unack_batches = db.unacknowledged_inject_batches(conn, problem)
    if unack_batches:
        return ("inject_batch_done", pending_id)
    if pending_id is not None:
        return ("pending_review", pending_id)
    # No running-set here (worker thread) — queue-only in-flight check;
    # a brief false-stall just classifies this wake as batch-done, which
    # is benign (same context, stricter advance rule).
    if db.is_problem_stalled(conn, problem):
        return ("inject_batch_done", pending_id)
    return ("routine", pending_id)


def _strategist_row_is_stale(conn: sqlite3.Connection,
                             target_id: str, kind: str) -> bool:
    """A queued Strategist whose problem has already committed `Ingest`
    has nothing left to decide — it would only spawn, Noop, and advance
    `last_strategist_at`. The dispatcher drops such a popped row.

    Phase 6 — the old drop condition (root goal `proved`) is exactly
    wrong now: a root-proved problem is where the Strategist must wake to
    judge the Manifest and commit `Ingest` (the only exit trigger), so
    the drop keys off the problem terminal state instead. If a rollback
    later revokes the Ingest (post-Ingest un-prove), the problem re-enters
    the live path and the normal triggers re-fire.

    `target_id` of a Strategist row is the problem name
    (target_kind='Problem').
    """
    if kind != "Strategist":
        return False
    return db.problem_ingested(conn, str(target_id))


# ── run()-loop scheduling constants (hoisted from function locals, task #9) ──
SPAWN_COOLDOWN_SEC = 30.0
CONSEC_SPAWN_FAIL_LIMIT = 10
CONSEC_GATEWAY_UNREACHABLE_LIMIT = 8
QUOTA_BACKOFF_BASE_SEC = 30.0
QUOTA_BACKOFF_CAP_SEC = 600.0


@dataclass
class SchedulerState:
    """The dispatcher run-loop's mutable scheduling state in ONE place
    (task #9 — formerly seven loose locals whose persistence policy lived
    only in scattered comments).

    Persistence policy per field — decide + document here when adding one:
      - `librarian_fail_counts` — DB WRITE-THROUGH (`librarian_fail_counts`
        table, loaded at startup): a stuck unit's count must survive a
        restart so it STALLs at LIBRARIAN_MAX_CHAIN_RETRIES instead of
        looping forever.
      - everything else — deliberately in-memory; crash ⇒ clean slate IS
        the policy: cooldowns lapse (they were timed anyway), the consec
        circuit breakers re-arm (a restart is exactly the operator action
        they exist to force), quota backoff re-probes the provider, and
        `verified_problems` re-pays one lake pre-flight per problem
        (correct after any on-disk change).
    """
    # (tid, kind) → wall time before which bfs_refill/pop skip the pair.
    cooldown_until: "dict[tuple[str, str], float]" = field(default_factory=dict)
    # Per-kind provider-quota backoff (#103): kind → resume time / consec.
    quota_cooldown_kind: "dict[str, float]" = field(default_factory=dict)
    consec_quota_per_kind: "dict[str, int]" = field(default_factory=dict)
    # Global consecutive spawn_fast_fail counter; breaker exits the daemon
    # at CONSEC_SPAWN_FAIL_LIMIT (claude.exe persistently broken).
    consec_fast_fails: int = 0
    # Independent gateway_unreachable breaker (run #17: 48 strategies piled
    # up busy-looping against a dead gateway before this existed).
    consec_gateway_unreachable: int = 0
    # DB write-through — see class docstring.
    librarian_fail_counts: "dict[str, int]" = field(default_factory=dict)
    # Lazy verify cache: problem → Defs/Root built clean (False =
    # quarantined for this daemon run).
    verified_problems: "dict[str, bool]" = field(default_factory=dict)


def _gateway_unreachable_backoff(st: "SchedulerState", pool, *,
                                 kind: str, tk: str, tid: str) -> bool:
    """Shared gateway-unreachable back-off + circuit breaker (task #9 —
    formerly two verbatim copies in the normal-result and worker-exception
    cascade paths; editing the breaker rule meant editing both). Returns
    True when the breaker trips (caller exits the daemon with rc=2)."""
    st.cooldown_until[(tid, kind)] = time.time() + SPAWN_COOLDOWN_SEC
    st.consec_gateway_unreachable += 1
    print(f"[cooldown] {kind} {tk}={tid} cooled "
          f"{SPAWN_COOLDOWN_SEC:.0f}s after "
          f"gateway_unreachable "
          f"(consec={st.consec_gateway_unreachable})",
          flush=True)
    if st.consec_gateway_unreachable >= CONSEC_GATEWAY_UNREACHABLE_LIMIT:
        print(f"[dispatcher] "
              f"{st.consec_gateway_unreachable} "
              f"consecutive gateway_unreachable — "
              f"gateway appears permanently dead; "
              f"exiting. Restart daemon (gateway "
              f"will be re-launched) and inspect "
              f".asterism/logs/gateway.log for the "
              f"underlying crash.", flush=True)
        _exit_pool_fast(pool)
        return True
    return False


def _run_pipeline(workspace: Path,
                  manifests: "manifest.ManifestCache | dict[str, manifest.Manifest]",
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
            #   Strategist: target_kind='Problem', target_id=problem_name
            #     (Phase 6 — problem-keyed like Forward; the old root-goal
            #     key made pure-NL problems unwakeable). decision_id is
            #     unused (Strategist EMITS decisions).
            #   Forward:    target_kind='Problem', target_id=problem_name;
            #     decision_id is the Strategist Inject row that spawned
            #     this Forward.
            if task_kind == "Strategist":
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
                trigger, pending_id = _derive_strategist_trigger(
                    conn, problem)

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
                    # Problem-targeted forensic uses target_id=0 (INTEGER
                    # column; same convention as Forward below).
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind=target_kind,
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

            if task_kind == "Librarian":
                # Problem-targeted background harvest (plan §5). Derive
                # the work_kind from library_decls state — work_kind is
                # NOT in the queue row (mirrors strategist deriving its
                # trigger), so a re-enqueued chain step always reflects
                # the latest state.
                # #92 — target_id is `problem\x1ffile` for a per-file
                # migrate/cleanup unit, or a plain `problem` for a serial phase
                # step (dedup/classify/bridge).
                problem, target_file = _lib_decode(target_id)
                if problem not in manifests:
                    db.record_pipeline(
                        conn, pipeline_id=pipeline_id, kind=task_kind,
                        target_id=target_id, target_kind=target_kind,
                        status="failed", outcome="failed",
                        started_at=started_at,
                    )
                    return (pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                from ..pipeline import librarian
                if target_file is not None:
                    # Per-file unit: run THIS file's current step.
                    work_kind = librarian.file_work_kind(
                        conn, problem=problem, target_file=target_file)
                    target = target_file
                else:
                    # Serial phase step. If state has advanced to a per-file
                    # phase (migrate/cleanup), `_librarian_refill` owns it —
                    # this plain row is a no-op (the per-file rows do the work).
                    work_kind, target = _derive_librarian_work(
                        conn, problem, workspace)
                    if work_kind in ("migrate", "cleanup"):
                        work_kind = None
                if work_kind is None:
                    # Nothing to do for this row (chain drained, or a stale
                    # plain row whose phase is now per-file). Clean no-op.
                    db.record_pipeline(
                        conn, pipeline_id=pipeline_id, kind=task_kind,
                        target_id=target_id, target_kind=target_kind,
                        status="succeeded", outcome="success",
                        started_at=started_at,
                    )
                    return (pipeline_id, task_kind, target_id, target_kind,
                            "success", "")
                # Per-file axiom check uses the operator's authorized
                # axioms (Manifest `axioms_whitelist`), falling back to
                # the 3 standard axioms — same source + fallback as
                # root_integrity_gate. Only migrate consumes it.
                mfst = manifests[problem]
                whitelist = (list(mfst.axioms_whitelist)
                             if mfst.axioms_whitelist
                             else list(verify.FRAMEWORK_DEFAULT_AXIOMS))
                r = librarian.run_librarian(
                    conn, problem=problem, work_kind=work_kind,
                    workspace=workspace, pipeline_id=pipeline_id,
                    target=target, whitelist=whitelist,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status=status, outcome=r.outcome,
                    started_at=started_at,
                )
                # Problem-targeted forensic uses target_id=0 (mirrors
                # Forward — dead_attempts.target_id is INTEGER). Librarian
                # is background: a failure is logged but never blocks
                # proof work, and the chain does not auto-retry a
                # schema/verify failure (operator inspects).
                if status == "failed":
                    artifacts = pipeline.collect_artifacts(attempts_dir)
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind="Problem",
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                        proposal_md=r.proposal_md,
                        artifacts=(_json.dumps(artifacts) if artifacts
                                   else ""),
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
    OpenProcess + GetExitCodeProcess.

    Note: On Windows, os.kill(pid, 0) raises SystemError because sig
    0 isn't a real Windows signal — Python's os.kill on Windows only
    handles termination signals via TerminateProcess.

    Windows kernel keeps the Process object live for any handle holder
    even AFTER the process has terminated, so OpenProcess succeeds on
    a freshly-killed PID. GetExitCodeProcess distinguishes "still
    running" (STILL_ACTIVE=259) from "terminated but handle-zombie".
    Without this check, the singleton lock would refuse new daemons
    for any PID the OS hasn't recycled yet."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            exit_code = ctypes.c_uint32(0)
            ok = kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
            if not ok:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _proc_start_time(pid: int) -> "float | None":
    """psutil process create-time for `pid` (epoch seconds), or None if the
    process is gone / its start-time is unreadable. Paired with the PID it
    forms a reuse-proof process-instance identity for the singleton lock."""
    try:
        import psutil
        return psutil.Process(pid).create_time()
    except Exception:
        return None


def _cmdline_is_daemon(pid: int) -> "bool | None":
    """True / False iff the live process at `pid` is / isn't an asterism
    dispatcher (`python -m Tooling.core.cli run …` or the `asterism run`
    console script); None if its command line can't be read. The fallback
    identity signal for a legacy pid-only lock that has no recorded
    start-time."""
    try:
        import psutil
    except ImportError:
        return None
    try:
        argv = psutil.Process(pid).cmdline()
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None
    joined = " ".join(argv)
    if ("Tooling.core.cli" in joined
            or "core/cli" in joined or "core\\cli" in joined):
        return True
    if argv and "run" in argv:
        exe = argv[0].lower().replace("\\", "/").rsplit("/", 1)[-1]
        if exe.startswith("asterism"):
            return True
    return False


def _lock_held_by_live_daemon(pid: int, stored_start: "float | None") -> bool:
    """True iff `pid` is the SAME live daemon instance that wrote the lock —
    NOT merely a live PID. Guards against PID REUSE: after a daemon crashes
    without releasing its lock, the OS can hand its PID to an unrelated live
    process (observed 2026-06-15 — a crashed daemon's PID was reused by the
    editor, so the bare-liveness lock blocked every restart). A (pid,
    start-time) pair identifies a process instance, so a reused PID — alive
    but with a different start-time — reads as stale.

    `stored_start` is the start-time recorded in the lock (None for a legacy
    pid-only lock). When absent or unreadable, fall back to a command-line
    signature; if neither signal can be read, conservatively treat a live PID
    as the daemon so two daemons never share one DB (the disaster the lock
    exists to prevent)."""
    if not _pid_alive(pid):
        return False
    if stored_start is not None:
        live = _proc_start_time(pid)
        if live is not None:
            return abs(live - stored_start) < 1.0
        # start-time unreadable — fall through to the cmdline signal.
    sig = _cmdline_is_daemon(pid)
    if sig is None:
        return True  # can't introspect a live PID — conservative (block)
    return sig


def _acquire_singleton_lock(workspace: Path) -> Path | None:
    """Refuse to start if another daemon is already running on this
    workspace. Two daemons sharing one DB silently dispatch the same
    goal twice, write conflicting strategy rows, and clobber each
    other's verify_strategy state. Caught in the wild when a stray
    `&` background invocation overlapped with a fresh `run`.

    Mechanism: PID file at `.asterism/daemon.pid` holding `pid\\nstart_time`.
    On startup:
      - if file missing → create, return path
      - if it names the SAME live process instance (pid + start-time, or a
        daemon command line for a legacy pid-only lock) → return None
        (caller exits)
      - if it names a dead PID, or a REUSED PID now belonging to a different
        process → stale, overwrite. (Bare liveness alone is fooled by PID
        reuse — 2026-06-15: a crashed daemon's PID became the editor's,
        blocking every restart.)

    Returned path should be `.unlink(missing_ok=True)` at shutdown.
    """
    asterism_dir = workspace / ".asterism"
    asterism_dir.mkdir(parents=True, exist_ok=True)
    pid_file = asterism_dir / "daemon.pid"
    my_pid = os.getpid()

    if pid_file.exists():
        existing = -1
        stored_start: "float | None" = None
        try:
            parts = pid_file.read_text(encoding="utf-8").split("\n")
            existing = int(parts[0].strip())
            if len(parts) > 1 and parts[1].strip():
                stored_start = float(parts[1].strip())
        except (OSError, ValueError):
            existing = -1
        if (existing > 0 and existing != my_pid
                and _lock_held_by_live_daemon(existing, stored_start)):
            print(f"[dispatcher] another daemon (pid={existing}) is "
                  f"already running on this workspace. Kill it or wait "
                  f"for it to exit, then retry. (lock: {pid_file})",
                  file=sys.stderr, flush=True)
            return None

    my_start = _proc_start_time(my_pid)
    pid_file.write_text(
        f"{my_pid}\n{my_start if my_start is not None else ''}",
        encoding="utf-8")
    return pid_file


def run(workspace: Path, *, once: bool = False,
        scope: str | None = None) -> int:
    pid_lock = _acquire_singleton_lock(workspace)
    if pid_lock is None:
        return 1
    import atexit
    atexit.register(lambda: pid_lock.unlink(missing_ok=True))

    # Bind this process + every later spawn (claude / lake / lean / per-spawn
    # LSP) into a kill-on-close Job Object, so a hard daemon death reaps the
    # whole tree at the OS level — no manual orphan-cleanup ritual, no broad-kill
    # footgun (CLAUDE.md rule 8). The reusable LSP gateway breaks away (below) so
    # it survives. Soft: on failure the orphan-sweep below stays the safety net.
    from . import process_group
    if process_group.assign_self_to_kill_on_close_job():
        print("[daemon] process tree bound to kill-on-close job", flush=True)

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
    # per `docs/archive/design/phase2/pipelines.md` §5. Picked by `strategist_triggers`
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
    # Background .olean warmer (#103): after verify_housekeeping promotes
    # a strategy (parent → alias rewrite), the alias spine needs a fresh
    # .olean so the later root integrity probe doesn't pay a cold closure
    # build on this main thread. The warmer runs that `lake build` on its
    # own daemon thread — off the main thread AND off this LLM worker pool
    # (which is gateway-bound, #118). Kill switch: `verify.olean_warm`.
    from ..pipeline._olean_warm import OleanWarmer
    _olean_warm_raw = config.get(
        "verify.olean_warm", default=True,
        env_var="ASTERISM_OLEAN_WARM", workspace=workspace)
    olean_warm_enabled = (
        _olean_warm_raw if isinstance(_olean_warm_raw, bool)
        else str(_olean_warm_raw).strip().lower() in ("true", "1", "yes", "on"))
    olean_warmer = OleanWarmer(workspace, enabled=olean_warm_enabled)
    atexit.register(lambda: olean_warmer.shutdown(wait=False))
    futures: dict[Future, tuple[str, str, str, str]] = {}
    # In-memory live set of (target_id, kind) pairs currently executing in
    # this daemon. Passive trigger means at most one of each kind per
    # target, so the pair is a unique key. Daemon crash → set vanishes →
    # restart sees clean slate.
    running: set[tuple[str, str]] = set()
    # All mutable scheduling state — persistence policy documented on
    # SchedulerState (task #9). Constants hoisted to module level.
    st = SchedulerState()

    conn = db.connect()
    # Idempotent — picks up additive migrations on an existing DB
    # without requiring `cli init` / `cli reset`. SCHEMA itself is
    # CREATE TABLE IF NOT EXISTS, and ALTER TABLE ADD COLUMN entries
    # swallow "duplicate column name". Required because the daemon
    # is the long-running consumer of the DB on a workspace that
    # was init'd against an earlier schema version.
    db.init_schema(conn)
    # Restore the Librarian chain fail cap across restarts (#92 B#3): a stuck
    # unit's tally persists so it STALLs instead of looping forever.
    st.librarian_fail_counts.update(db.librarian_fail_counts_all(conn))
    # ManifestCache hot-reloads on Manifest.md mtime change at each
    # spawn-time access — daemon previously locked in the startup-time
    # parse, so user edits mid-run were invisible until restart. Cache
    # quacks like dict[str, Manifest] for downstream callers.
    manifests = manifest.ManifestCache(workspace)
    for row in conn.execute("SELECT name, manifest_path FROM problems"):
        manifests.load(row["name"], row["manifest_path"])

    _recover_at_startup(conn, workspace, scope=scope)

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
    # Daemon start as an ISO timestamp — the T1 routine clock baseline, so
    # paused/down time between runs is excluded from the routine interval.
    from datetime import datetime as _dt, timezone as _tz
    daemon_start_iso = _dt.fromtimestamp(start_time, tz=_tz.utc).isoformat()

    # Surface problems paused on an unresolved RequestUserAmend up front.
    # bfs_refill silently skips these (awaiting_human gate), so without
    # this line a scoped daemon whose only in-scope problem is paused is
    # indistinguishable from a hang — 2026-06-12 a paused P12
    # (stokes_induced_orient) read as a multi-hour gateway/tree-render
    # hang across two sessions. Operator must resolve the amend (apply
    # the proposed Defs.lean/Manifest.md body, clear the decision) then
    # re-run. Cheap: idx_sd_outcome backs the filter.
    _paused_q = ("SELECT DISTINCT problem FROM strategist_decisions "
                 "WHERE outcome = 'awaiting_human'")
    _paused_params: tuple = ()
    if scope:
        _paused_q += " AND problem LIKE ?"
        _paused_params = (scope,)
    _paused_startup = sorted(r[0] for r in conn.execute(_paused_q, _paused_params))
    if _paused_startup:
        print(f"[dispatcher] {len(_paused_startup)} problem(s) PAUSED on "
              f"awaiting_human (unresolved RequestUserAmend); dispatch "
              f"suppressed until resolved: {_paused_startup}", flush=True)

    # Phase 1 gateway: launch long-living LSP HTTP MCP server, wait
    # until backend pre-warm completes (mathlib loaded). Per-spawn MCP
    # config will point at this gateway via HTTP; spawns no longer
    # fork their own lake serve. Cold start ~30-145s amortized once
    # per daemon startup. start_gateway registers an atexit handler so
    # the subprocess dies with the daemon — we don't need to track the
    # Popen ourselves here.
    from ..lsp import lifecycle as gateway_lifecycle
    gateway_lifecycle.start_gateway(workspace)

    # Framework⇄Lean contract gate (task #12): when the toolchain
    # fingerprint (lean-toolchain + lake-manifest) changed since the last
    # recorded pass, run the interface-contract suite once on the freshly
    # warmed gateway — a red contract means every proving spawn would be
    # burning budget against a broken probe/parser, so refuse to start.
    # Unchanged fingerprint = zero cost. Mechanism, not discipline: the
    # toolchain cannot change without the suite running once.
    from ..quality import lean_contracts
    if not lean_contracts.check_on_startup(workspace):
        _exit_pool_fast(pool)
        return 2

    # Periodic TREE.md refresh targets. A `--scope X` run only mutates
    # in-scope problems, so refreshing all ~281 problems' trees every tick
    # is pure churn — and with idx_strategies_goal_id the render dropped to
    # ~0.17s/tick, so the loop now cycles fast enough that the rapid
    # atomic-replace of unrelated TREE.md files raised transient WinError 5
    # sharing violations on Windows (caught below, but noise). Computed once
    # — the problem set is fixed for a run. Unscoped runs still refresh all.
    if scope is not None:
        tree_problems = db.scoped_problem_names(conn, scope)
    else:
        tree_problems = list(manifests)

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
                    # Librarian chain advance (#92). Only COUNTS this unit's
                    # outcome (per-target_id fail tracking); re-enqueue is owned
                    # by the tick-level `_librarian_refill` DAG scheduler. A
                    # unit that keeps failing crosses LIBRARIAN_MAX_CHAIN_RETRIES
                    # and the refill then skips it (stalled) instead of looping.
                    if kind == "Librarian":
                        _advance_librarian_chain(
                            conn, workspace, tid, outcome=outcome,
                            reason=reason, fail_counts=st.librarian_fail_counts,
                            pipeline_id=pid)
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
                        n = st.consec_quota_per_kind.get(kind, 0) + 1
                        st.consec_quota_per_kind[kind] = n
                        backoff = min(
                            QUOTA_BACKOFF_BASE_SEC * (2 ** (n - 1)),
                            QUOTA_BACKOFF_CAP_SEC,
                        )
                        st.quota_cooldown_kind[kind] = time.time() + backoff
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
                        st.cooldown_until[(tid, kind)] = (
                            time.time() + SPAWN_COOLDOWN_SEC)
                        if reason == "spawn_fast_fail":
                            st.consec_fast_fails += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"spawn_fast_fail "
                                  f"(consec={st.consec_fast_fails})", flush=True)
                            if st.consec_fast_fails >= CONSEC_SPAWN_FAIL_LIMIT:
                                print(f"[dispatcher] {st.consec_fast_fails} "
                                      f"consecutive spawn_fast_fails — "
                                      f"claude.exe or provider appears broken; "
                                      f"exiting. Inspect "
                                      f".attempts/<pid>/_spawn.stderr "
                                      f"for the underlying error.", flush=True)
                                _exit_pool_fast(pool)
                                return 2
                        elif reason == "gateway_unreachable":
                            # (cooldown already set by the generic infra
                            # branch above; the helper re-sets the same key
                            # — idempotent.)
                            if _gateway_unreachable_backoff(
                                    st, pool, kind=kind, tk=tk, tid=tid):
                                return 2
                        else:
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after {reason}",
                                  flush=True)
                    else:
                        st.consec_fast_fails = 0
                        st.consec_gateway_unreachable = 0
                        # #103 — any non-quota, non-infra outcome on this
                        # kind proves the provider responded: clear the
                        # per-kind quota backoff so dispatch resumes
                        # fresh. (Other infra reasons above are orthogonal
                        # to quota — handled in their own branch and don't
                        # touch quota state.)
                        if kind in st.consec_quota_per_kind:
                            st.consec_quota_per_kind.pop(kind, None)
                            st.quota_cooldown_kind.pop(kind, None)
                            print(f"[cooldown] {kind} quota state reset "
                                  f"(non-quota outcome confirms provider "
                                  f"responsive)", flush=True)
                    # `strategist_noop` is a non-success outcome but means
                    # "nothing to propose" (often: root already proved by
                    # the time the trigger fired) — not an error. Render it
                    # as `noop` so the log doesn't read as a failure.
                    _disp_outcome = (
                        "noop" if outcome == "failed"
                        and reason == "strategist_noop" else outcome)
                    print(f"[cascade] {kind} {tk}={tid} → {_disp_outcome}",
                          flush=True)
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
                        # Backward's BaseException handler in
                        # `backward.py` deletes the placeholder
                        # strategy when the worker crashed before
                        # writing proposal_md/scratch_path. Combined
                        # with cascade_one's early-return on infra
                        # reasons (no attempts++, no status touch),
                        # the parent goal can be left 'attempting'
                        # with no live strategy — bfs_refill skips it
                        # (open_goals filter) and no cascade re-
                        # checks. Reconcile here so the goal either
                        # reopens for a fresh Backward (under
                        # threshold) or shelves (deferred terminal
                        # from earlier strong-signal cascades).
                        if kind == "Backward" and tk == "Goal":
                            try:
                                _reconcile_goal_after_strategy_loss(
                                    conn, int(tid))
                            except (ValueError, TypeError):
                                pass
                        tree.write_for_target(conn, workspace, tid, tk)
                        # Mirror the normal-result cooldown path so
                        # gateway-unreachable / transient_timeout also
                        # yield a 30s back-off — without this, the same
                        # Backward gets re-dispatched on the next tick
                        # and re-fails.
                        if infra_reason == "transient_timeout":
                            st.cooldown_until[(tid, kind)] = (
                                time.time() + SPAWN_COOLDOWN_SEC)
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"transient_timeout (slot contention "
                                  f"or RPC budget exceeded; no consec "
                                  f"increment — circuit breaker reserved "
                                  f"for true gateway death)",
                                  flush=True)
                        elif infra_reason == "gateway_unreachable":
                            if _gateway_unreachable_backoff(
                                    st, pool, kind=kind, tk=tk, tid=tid):
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
                                   manifests=manifests,
                                   olean_warmer=olean_warmer)

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
            # Reconcile FILE/DB drift from OR races. Auto-prune was
            # removed 2026-05-26 after Jordan 2026-05-25 incident exposed
            # how easily a single bad keep-set computation wipes a chain;
            # the bugs that caused that wipe were fixed (1660200), but the
            # blast radius of an auto-delete loop is large enough that
            # explicit operator opt-in is the safer default. Manual GC via
            # `asterism prune <problem>` (preferably `--dry-run` first).
            repaired = prune.reconcile_proved_goals(
                conn, workspace, problem_name)
            if repaired:
                print(f"[reconcile] {problem_name}: repaired "
                      f"{len(repaired)} drifted files", flush=True)
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

        # #92 — Librarian DAG scheduler: enqueue every dispatchable file
        # (and the serial phase steps), self-starting opted-in proved
        # problems, so independent files migrate/clean in parallel in the
        # pool, the same way bfs_refill fans out proving goals. Run BEFORE the
        # exit gate so its `pending` return can hold the daemon alive while
        # Library-ization is outstanding (Bug A — proof work alone no longer
        # keeps the daemon up once every root is proved).
        librarian_pending = _librarian_refill(
            conn, workspace, running, manifests, scope=scope,
            fail_counts=st.librarian_fail_counts)

        # Workspace-wide exit (Phase 6): every problem has committed its
        # `Ingest` terminal (the Strategist's Manifest-satisfied judgment —
        # root_proved is its HARD prerequisite when a root exists, enforced
        # at the Ingest verify gate) AND no Librarian work remains. A
        # rollback (`verify.root_integrity_gate` → sorryAx cascade) revokes
        # the Ingest stamp, so this check fails and the loop continues.
        # `scope` filter: a `--scope sylvester_gallai` daemon must gate on its
        # scoped problems only — without this filter, unrelated miniF2F
        # problems sitting in the same workspace hold the gate forever.
        # `librarian_pending`: without it a scoped run over an already-proved
        # problem (or the last root proving in any run) exits before the
        # Library-ization chain — dedup→classify→migrate→bridge→INDEX —
        # has a chance to run, since that chain spans many ticks (Bug A).
        # `_harvest_outstanding`: durable-state backstop. `librarian_pending` is
        # a transient queue/running snapshot that can read False on the
        # proof→harvest handoff tick (root just integrity-verified, mechanical
        # dedup completing in a worker), letting the gate exit and kill the
        # in-flight Librarian — silently skipping harvest on a clean opted-in
        # proof. The INDEX/lifecycle/fail-count check is timing-independent and
        # holds the daemon until harvest actually finishes (or stalls).
        if (db.all_problems_ingested(conn, scope=scope)
                and not librarian_pending
                and not _harvest_outstanding(
                    conn, workspace, manifests, scope=scope,
                    fail_counts=st.librarian_fail_counts)):
            print("[dispatcher] all problems ingested", flush=True)
            _exit_pool_fast(pool)
            return 0

        # Refill queue (uses in-memory `running` for dedup; st.cooldown_until
        # holds spawn_fast_fail back-offs; st.quota_cooldown_kind holds the
        # per-kind quota backoff (#103); scope restricts to a benchmark
        # subset like `minif2f_%`).
        bfs_refill(conn, running, st.cooldown_until, scope=scope,
                   quota_cooldown_kind=st.quota_cooldown_kind,
                   verified_problems=st.verified_problems)

        # Phase 2 — Strategist T0/T1 triggers (T2 pending_review fires at
        # cascade time in `cascade_one` as the fast path). Skipped under
        # awaiting_human gate per-problem inside `strategist_triggers`.
        # Defaults to 60-min routine (`strategist.interval_min`).
        strategist_triggers(conn, running, scope=scope,
                            interval_min=strategist_interval_min,
                            daemon_start_iso=daemon_start_iso)

        # Per-tick stuck-state reconciler: the safety net for the two
        # mid-run-reachable stuck states the cascade fast paths can drop —
        # orphaned pending_review goals + NULL-outcome Inject wedges. Runs
        # every tick, in-flight gated, so a dropped wakeup self-heals within
        # one tick instead of waiting for restart / the 120-min routine.
        reconcile_stuck_states(conn, running, scope=scope)

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
            if _dispatch_is_duplicate(running, target_id, kind, decision_id):
                continue
            # #103 — defense-in-depth: even after bfs_refill skips
            # cooled kinds, a race (cooldown set between bfs_refill
            # and pop) could leave a queued row for a now-cooled
            # kind. Drop it; bfs_refill will repopulate post-cooldown.
            if st.quota_cooldown_kind.get(kind, 0.0) > time.time():
                continue
            # Drop a queued Strategist whose problem already committed
            # Ingest (e.g. a wake that raced the terminal commit). It
            # would only spawn + Noop. See `_strategist_row_is_stale`.
            if _strategist_row_is_stale(conn, target_id, kind):
                print(f"[dispatch] skip Strategist Problem={target_id} "
                      f"— already ingested", flush=True)
                continue
            # Lazy verify gate — must hold before any worker spawn.
            # First dispatch for a problem this daemon run pays a one-
            # time `lake build Defs.lean + Root.lean` (~5-15s). Failure
            # quarantines the problem in `st.verified_problems` so neither
            # the pop loop nor bfs_refill dispatches further on it.
            problem_name = _problem_of_target(conn, target_id, target_kind)
            if problem_name is None:
                # Defensive: unknown target shape (DB drift?). Skip
                # rather than wedge the pop loop.
                continue
            if problem_name not in st.verified_problems:
                st.verified_problems[problem_name] = _verify_problem(
                    workspace, problem_name)
            if not st.verified_problems[problem_name]:
                continue
            pipeline_id = agent.new_pipeline_id()
            running.add((target_id, kind, decision_id))
            fut = pool.submit(_run_pipeline, workspace, manifests,
                              kind, target_id, target_kind, pipeline_id,
                              decision_id)
            futures[fut] = (pipeline_id, kind, target_id, target_kind,
                            decision_id)
            # Librarian per-file rows encode `problem\x1ffile` (#92); the
            # \x1f is non-printing, so render it readably in the log.
            _disp_prob, _disp_file = _lib_decode(target_id)
            _disp_tid = (f"{_disp_prob} file={_disp_file}"
                         if _disp_file else target_id)
            print(f"[dispatch] {kind} {target_kind}={_disp_tid} "
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
        #
        # `open_goals` is SCOPED here. The unscoped form let a `--scope X`
        # run livelock forever whenever ANY other problem in the workspace
        # had an open goal (2026-06-12 P12: the only in-scope problem was
        # paused on awaiting_human, but brouwer's unrelated open goal kept
        # this check non-zero, so the daemon never exited and just burned
        # the periodic tree-write each tick). Goals whose problem is paused
        # on awaiting_human are not dispatchable (bfs_refill skips them), so
        # they're excluded from the "dispatchable" set too — and reported,
        # so silence on a paused problem doesn't read as a hang.
        dispatchable_open = db.dispatchable_open_goals(conn, scope=scope)
        if (not futures
                and db.queue_size(conn) == 0
                and len(dispatchable_open) == 0
                and len(db.strategies_ready_for_verify(conn)) == 0):
            paused_probs = sorted({
                str(g["problem"]) for g in db.open_goals(conn, scope=scope)
                if db.problem_has_awaiting_human(conn, str(g["problem"]))})
            if paused_probs:
                print(f"[dispatcher] {len(paused_probs)} problem(s) paused on "
                      f"awaiting_human — resolve the RequestUserAmend then "
                      f"re-run: {paused_probs}", flush=True)
            scoped_done = db.all_problems_ingested(conn, scope=scope)
            print(f"[dispatcher] no dispatchable work, exiting "
                  f"(all_ingested={scoped_done})", flush=True)
            pool.shutdown(wait=True)
            return 0 if scoped_done else 1

        # Wait for any completion or tick
        if futures:
            wait(list(futures), timeout=TICK_TIMEOUT,
                 return_when=FIRST_COMPLETED)
        else:
            time.sleep(min(TICK_TIMEOUT, 5))

        # Periodic TREE.md refresh — cascade-only writes leave the tree
        # frozen during long Builder/Backward spawns (5-15min under LSP).
        # Restricted to `tree_problems` (in-scope for a scoped run). Cheap
        # render + atomic replace; failures are swallowed inside
        # tree.write_for_target's caller pattern but tree.write itself
        # raises, so guard here.
        for problem_name in tree_problems:
            try:
                tree.write(conn, workspace, problem_name)
            except Exception as exc:
                print(f"[tree] periodic write skipped for "
                      f"{problem_name}: {exc}", flush=True)

        if time.time() - start_time > budget_sec:
            print(f"[dispatcher] {budget_sec}s budget exceeded; stopping",
                  flush=True)
            _exit_pool_fast(pool)
            return 1


