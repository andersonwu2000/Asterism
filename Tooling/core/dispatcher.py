"""Main dispatcher loop. Cascade in main thread, pipelines in pool.

See architecture.md §7-§8.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import typing as _typing
import shutil
import sqlite3
from dataclasses import dataclass, field
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime
from pathlib import Path

from .. import agent, pipeline
from . import config, fsutil, quota, quota_wait
from .admission import (ADMIT, DENY_KIND_BACKOFF, DENY_QUOTA,
                        DENY_TARGET_COOLED, admission)
from ..state import db, manifest, thresholds, transitions, tree
from ..state import failures as _failures
from ..state import groups as _groups
from ..quality import prune, verify


#: The quota ledger, one per process (its probes are network calls and
#: it caches). Blocks are re-read on the tick cadence, not per spawn.
_quota_ledger = quota.Ledger()

#: Every pipeline that spawns a model, and therefore every seat that can
#: run out of quota independently. `presearch` burns its own cheap model
#: (research_mode_design §0) and `scholar` its own — both are seats even
#: though neither is a decision-maker.
_QUOTA_SEATS = ("strategist", "adversary", "formalizer", "presearch",
                "scholar", "librarian", "paper_index")


def _pipeline_seats() -> "dict[str, tuple[str, str | None]]":
    """`kind -> (provider, model)` as configured right now.

    Read per tick rather than cached: `Asterism.yaml` is live-editable
    and the daemon hands off on config change, so a seat can move
    between providers inside one run — which is exactly what happened on
    2026-08-06 when the judge moved off an exhausted model.
    """
    seats: "dict[str, tuple[str, str | None]]" = {}
    for kind in _QUOTA_SEATS:
        provider = str(config.get(
            f"{kind}.provider", default="claude",
            env_var=f"ASTERISM_{kind.upper()}_PROVIDER") or "claude")
        model = config.get(f"{kind}.model", default=None,
                           env_var=f"ASTERISM_{kind.upper()}_MODEL")
        seats[kind] = (provider, str(model) if model else None)
    return seats


# Attempt thresholds. Builder ROUTING is retired (Formalizer merge —
# see state/thresholds.py): SHELVE_THRESHOLD still shelves a goal once
# attempts hit it (env ASTERISM_SHELVE_THRESHOLD → Asterism.yaml
# `dispatch.*` → built-in, resolved in `run()`); BUILDER_THRESHOLD
# survives only as an internal small-retry-budget constant. Task
# #10(d): the LIVE values sit in `state.thresholds` (leaf — broke the
# repo's only dependency cycle); the module __getattr__ below keeps
# `dispatcher.*_THRESHOLD` reads working for historical call sites
# (read-only aliases — tests monkeypatch `state.thresholds`).

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
#: how often the daemon re-fingerprints the source tree (drift handoff).
#: ~300 stat() calls per check — cheap, but not per-tick cheap.
_DRIFT_CHECK_SEC = 60.0


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


# `next_worker_kind` retired (update_plan_2026_07 #1): every open goal
# dispatches as 'Formalizer' — the merged worker decides prove-vs-split
# itself, so pre-dispatch routing (entry_kind + the BUILDER_THRESHOLD
# escalation net) no longer exists. Its predecessor, a numeric
# `difficulty` (1-10), died for the same reason: upfront tractability
# estimates track conceptual complexity, not provability.


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

    # Memory exhaustion — the machine, not the mathematics (2026-08-08:
    # a runaway lean worker ate the pagefile; ten WinError 1455s then
    # fell through this classifier's "" default and burned ten attempts
    # across five goals with no dead_attempts row — the same shape
    # SG#14 fixed for transport errors). 1455=ERROR_COMMITMENT_LIMIT,
    # 8=ERROR_NOT_ENOUGH_MEMORY.
    if isinstance(exc, MemoryError):
        return "system_killed"
    if isinstance(exc, OSError) and (
            getattr(exc, "winerror", None) in (1455, 8)
            or exc.errno == errno.ENOMEM):
        return "system_killed"
    # The gateway ANSWERED — 5xx is a verdict, not silence. This branch
    # must precede the URLError one below because `HTTPError` is a
    # SUBCLASS of `URLError`: without it, "no free worker slot — pool
    # exhausted" is filed as "the gateway is unreachable" and feeds the
    # consecutive-unreachable breaker that exits the daemon. That is the
    # 2026-08-13 stop: a healthy gateway holding leaked slots from a
    # killed predecessor, 8 rounds, ~780s, daemon gone. `failures.py`
    # already drew this distinction for the verify path when it created
    # `verify_infra` ("the process is up and talking, so this must NOT
    # feed the breaker") — the lesson simply never reached the
    # dispatcher's own classifier.
    from ..lsp.lifecycle import GatewayRefused
    if isinstance(exc, (GatewayRefused, urllib.error.HTTPError)):
        return "verify_infra"
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
    if target_kind == "Group":
        # v35 — a Strategist row carries a GROUP id. Falling through to
        # the goal lookup below would read it as a goal id and hand back
        # whatever problem THAT goal belongs to, scoping an infra retry
        # to an unrelated problem.
        row = conn.execute("SELECT problem FROM groups WHERE id = ?",
                           (int(target_id),)).fetchone()
        return str(row["problem"]) if row is not None else None
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
               kind_backoff: dict[str, float] | None = None,
               blocked_kinds: "set[str] | None" = None,
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

    The two kind-wide inputs are separate on purpose, and used to be one
    map: quota is provider-level, not target-level — gating one
    (tid, kind) leaves 243 other Backwards free to burn through the cap.

    `blocked_kinds` is the quota ledger's answer for this tick, handed
    in by the caller rather than stored anywhere. `kind_backoff` is the
    rc=126 exponential rate brake, which the dispatcher does own. Both
    suppress a whole kind; only one of them is a fact about the outside
    world, and mixing them is what made the release direction
    unwritable (see `core/admission.py`).

    `scope` (optional SQL LIKE pattern): when set, only enqueue goals
    whose problem matches. Lets a daemon run be restricted to a
    benchmark batch (e.g. `minif2f_%`) without disturbing unrelated
    problems sitting in the same workspace.
    """
    now = time.time()
    cd = cooldown_until or {}
    kb = kind_backoff or {}
    blocked = blocked_kinds or set()

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

    def admits(tid: str, kind: str) -> str:
        """The shared door predicate — see `admission`. Local copies of
        these two comparisons lived here and in the pop loop until
        2026-08-13, when the pop loop's absence of the per-target half
        let ten fast-fails land in 51 seconds."""
        return admission(tid, kind, cooldown_until=cd, kind_backoff=kb,
                         blocked_kinds=blocked, now=now)

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
        # Organic budget guard: an OPEN goal at/over SHELVE_THRESHOLD has
        # no organic budget left (the retry pre-loop would moot it with
        # budget<=0 and leave it open → re-enqueued next tick → hot moot
        # loop; putnam_2025_b6 2026-07-09, 4,317 moot pipelines). Such a
        # goal exists only via non-cascade paths (Inject force-reopen
        # keeps attempts; recovery reopen) — cascade itself routes to
        # review AT the threshold crossing. Send it to the same T2
        # review instead of dispatching: over-threshold means "the
        # Strategist decides", whichever door the goal came through.
        if int(g["attempts"]) >= thresholds.SHELVE_THRESHOLD:
            # One review per attempts value: if the Strategist already
            # answered a review for this goal since its last attempt
            # (e.g. Reopen — keep alive, nothing bfs-visible changes),
            # re-escalating every tick pumps a Strategist wake loop
            # (b6 2026-07-10). The goal holds quietly until an Inject
            # (which bypasses bfs) mints a new attempt.
            if db.goal_reviewed_at_current_attempts(conn, int(g["id"])):
                continue
            print(f"[bfs] g{gid} open with attempts={g['attempts']} >= "
                  f"shelve_threshold={thresholds.SHELVE_THRESHOLD} — "
                  f"routing to strategist review, not dispatch",
                  flush=True)
            transitions._enqueue_strategist_review(conn, int(g["id"]))
            continue
        kind = "Formalizer"
        if admits(gid, kind) != ADMIT:
            continue
        if in_flight(gid, kind) == 0:
            db.enqueue(conn, kind=kind, target_id=gid, priority=2,
                       problem=str(g["problem"]))


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def _ensure_top_groups(conn: sqlite3.Connection, *,
                       scope: str | None = None) -> None:
    """Every live problem has a top group — the v35 invariant every seat
    source depends on.

    A problem without one has NO Strategist seat at all (each trigger
    keys on a group) and the failure is silent. Both per-tick entry
    points call this, so no seat source is left depending on the other
    having run first: an ordering dependency whose breakage is invisible
    is the same shape as the bug it guards against.
    """
    sql = ("SELECT p.name FROM problems p"
           " WHERE p.ingested_at IS NULL AND NOT EXISTS ("
           "   SELECT 1 FROM groups g WHERE g.problem = p.name"
           "     AND g.parent_group_id IS NULL)")
    args: tuple = ()
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args = (scope,)
    rows = conn.execute(sql, args).fetchall()
    if not rows:
        return
    for r in rows:
        _groups.ensure_top_group(conn, str(r["name"]))
    conn.commit()


def _enqueue_strategist(conn: sqlite3.Connection, group_id: int,
                        problem: str, *, priority: int) -> None:
    """The ONE way a Strategist seat is queued (v35).

    Every trigger goes through here so the row shape stays in one place:
    the seat belongs to a GROUP (`target_kind='Group'`), while `problem`
    keeps the row scope-safe for pop / flush / recovery."""
    db.enqueue(conn, kind="Strategist", target_id=str(group_id),
               target_kind="Group", priority=priority, problem=problem)


def _strategist_inflight(conn: sqlite3.Connection, group_id: int,
                         running: "set[tuple]") -> bool:
    """A Strategist for this GROUP is already running or queued.

    The serialization invariant is per group (v35), not per problem: a
    group mutates its OWN Programme, plan note and clocks, and its own
    slice of the goal tree, so two runs of the SAME group would race
    while two different groups are exactly the concurrency the tree
    exists to buy. Checks BOTH the in-memory `running` set (in-flight)
    AND the DB queue (pending); the cascade-time
    `_enqueue_strategist_review` checked only the queue, which is the gap
    `reconcile_stuck_states` closes.

    Running key is (target_id, kind, decision_id) with target_id the
    queue row's string; Strategist rows always have decision_id=None
    (never spawned from an Inject), so matching on (group id, kind)
    covers the invariant.

    (Pre-v35 rows are problem-keyed with target_kind='Problem'. They are
    resolved to the top group at pop time, so the only place that still
    sees the old key is `is_in_queue` — hence the second probe, which
    keeps a queued legacy row from being duplicated by a fresh one.)"""
    key = str(group_id)
    in_running = any(
        r[0] == key and r[1] == "Strategist" for r in running
    )
    if in_running or db.is_in_queue(conn, target_id=key, kind="Strategist"):
        return True
    row = conn.execute("SELECT problem FROM groups WHERE id = ?",
                       (int(group_id),)).fetchone()
    if row is None:
        return False
    problem = str(row["problem"])
    return (any(r[0] == problem and r[1] == "Strategist" for r in running)
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
    _ensure_top_groups(conn, scope=scope)

    # 1 — pending_review: enqueue Strategist (spawn derives the trigger).
    from ..state import transitions as _transitions
    for prob in db.problems_with_pending_review(conn, scope=scope):
        if not _transitions.problem_accepts_wake(
                conn, prob, "pending_review"):
            continue
        if db.problem_has_awaiting_human(conn, prob):
            continue
        # v35 — route to the group that OWNS the pending goal, exactly as
        # the cascade-time path does. Two routes to two different homes
        # for one event is the shape this file has paid for three times:
        # the compensating path would seat the top group on a review only
        # a sub-group can answer.
        for r in conn.execute(
            "SELECT id FROM goals WHERE problem = ?"
            "   AND status = 'pending_strategist_review' ORDER BY id",
            (prob,),
        ).fetchall():
            owner = _groups.group_for_goal(conn, prob, int(r["id"]))
            gid = (int(owner["id"]) if owner is not None
                   else _groups.ensure_top_group(conn, prob))
            if _strategist_inflight(conn, gid, running):
                continue
            _enqueue_strategist(conn, gid, prob, priority=20)

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
                   decision_id=did, problem=spec["problem"])


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def strategist_triggers(conn: sqlite3.Connection,
                        running: set[tuple[str, str]],
                        *,
                        scope: str | None = None,
                        interval_min: float = 120.0,
                        daemon_start_iso: str | None = None,
                        ) -> None:
    """T1 (routine) + T4 (stall) enqueues for the Strategist pipeline.
    T2 (pending_review) is handled by `_enqueue_strategist_review` at
    cascade-time, not here.

    T1.5 (the separate epistemic-audit wake, v26) is RETIRED (user call
    2026-07-25): its belief-sweep duties are now phase 1 of every
    routine wake, so the routine clock is the only periodic seat
    source. Historic 'audit' trigger rows stay valid in the DB CHECK.

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
    _ensure_top_groups(conn, scope=scope)

    # Wake legality (FSM P3): every seat source consults the ONE matrix
    # — a non-'active' problem (awaiting_human / ingest_signoff /
    # ingested / revoked) takes no seats. The legacy per-carrier guards
    # (awaiting check, ingested exclusion) stay as belt during the
    # dual-write window.
    from ..state import transitions as _transitions

    # T1 — routine wake. v35: the clock is per GROUP (`groups_needing_t1`),
    # so sibling groups keep their own cadence instead of taking turns at
    # one problem-wide seat. With only top groups this yields exactly the
    # problems the old per-problem selector named.
    for row in db.groups_needing_t1(
        conn, scope=scope, max_age_sec=max_age_sec,
        since_iso=daemon_start_iso,
    ):
        prob = str(row["problem"])
        gid = int(row["id"])
        if not _transitions.problem_accepts_wake(conn, prob, "routine"):
            continue
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, gid, running):
            continue
        _enqueue_strategist(conn, gid, prob, priority=10)

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
    # v35 — stall is detected PER GROUP. The problem-wide reading cannot
    # see a child that ran out of moves while a sibling is busy (the
    # problem is not stalled, so nobody wakes), and when it does fire it
    # wakes the top group rather than the one that is actually stuck.
    for _row in db.groups_stalled(conn, scope=scope, running=running):
        prob = str(_row["problem"])
        gid = int(_row["id"])
        if not _transitions.problem_accepts_wake(
                conn, prob, "inject_batch_done"):
            continue
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, gid, running):
            continue
        # Observability (user-requested 2026-07-04): the stall wake's
        # trigger_kind is deliberately conflated with inject_batch_done
        # at spawn, so this line is the ONLY record distinguishing a T4
        # rescue from the cascade batch-done relay (which dedups this
        # enqueue away whenever it got there first). grep '[stall-wake]'
        # to measure the accidental-stall rate.
        print(f"[stall-wake] T4 enqueued Strategist for {prob} "
              f"group {gid} (no batch-done relay covered this stall)",
              flush=True)
        _enqueue_strategist(conn, gid, prob, priority=10)


# ---------------------------------------------------------------------
# Worker thread body
# ---------------------------------------------------------------------

def _routine_due(conn: sqlite3.Connection, problem: str,
                 interval_min: float,
                 since_iso: "str | None" = None,
                 group_id: "int | None" = None) -> bool:
    """Per-problem mirror of `db.problems_needing_t1`'s clock (the
    derivation-side twin the routine trigger never had — user ruling
    2026-07-12: the periodic wake outranks event classification).
    Anchor = the later of
    `problems.last_routine_at` (bumped only by a routine commit) and
    `since_iso` (daemon start — down-time excluded); NULL anchor with a
    running daemon means "never routine'd", due `interval_min` after
    start, exactly like the T1 enqueue side.

    v35 — `group_id` reads THAT group's clock instead of the problem's,
    keeping this twin aligned with the enqueue side now that the seat is
    per group. The two must agree or a wake gets classified against a
    clock that did not select it."""
    if not interval_min or interval_min <= 0:
        return False
    if group_id is not None:
        row = conn.execute(
            "SELECT last_routine_at FROM groups WHERE id = ?",
            (int(group_id),),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT last_routine_at FROM problems WHERE name = ?",
            (problem,),
        ).fetchone()
    if row is None:
        return False
    anchor = row["last_routine_at"]
    if since_iso and (not anchor or str(since_iso) > str(anchor)):
        anchor = since_iso
    if not anchor:
        return False
    try:
        anchor_dt = datetime.fromisoformat(str(anchor))
        now_dt = datetime.fromisoformat(db.now())
    except ValueError:
        return False
    return (now_dt - anchor_dt).total_seconds() >= interval_min * 60.0


def _warn_consecutive_strategist(conn: sqlite3.Connection, problem: str,
                                 trigger: str) -> None:
    """Observability probe (user call 2026-07-11): back-to-back Strategist
    pipelines on one problem are a design smell — the batch cycle exists
    to force a Strategist commit to be FOLLOWED by other pipelines; the
    only expected shape is a shelve-review wake followed by a stall wake.
    Print-only, never blocks: grep '[consecutive-strategist]' to measure
    the rate (same pattern as '[stall-wake]'). A problem with anything
    still in flight (leased queue row — v17 leases persist while a worker
    runs) is skipped: the in-between pipeline just has no row yet."""
    try:
        inflight = conn.execute(
            "SELECT 1 FROM queue q"
            " LEFT JOIN goals g ON q.target_kind = 'Goal'"
            "   AND g.id = CAST(q.target_id AS INTEGER)"
            " WHERE q.kind != 'Strategist'"
            "   AND ((q.target_kind = 'Goal' AND g.problem = ?)"
            "     OR (q.target_kind = 'Problem' AND q.target_id = ?))"
            " LIMIT 1", (problem, problem)).fetchone()
        if inflight is not None:
            return
        row = conn.execute(
            # v38: exclude in-flight rows — this probe runs INSIDE the
            # Strategist worker, whose own dispatch-time 'running' row
            # would otherwise always be the newest match.
            "SELECT p.kind, p.id FROM pipelines p"
            " LEFT JOIN goals g ON p.target_kind = 'Goal'"
            "   AND g.id = CAST(p.target_id AS INTEGER)"
            " WHERE p.status != 'running'"
            "   AND ((p.target_kind = 'Problem' AND p.target_id = ?)"
            "    OR (p.target_kind = 'Goal' AND g.problem = ?))"
            " ORDER BY p.started_at DESC LIMIT 1",
            (problem, problem)).fetchone()
        if row is not None and str(row["kind"]) == "Strategist":
            print(f"[consecutive-strategist] {problem}: this wake "
                  f"(trigger={trigger}) follows Strategist pipeline "
                  f"{row['id']} with no other pipeline in between — "
                  f"expected only for shelve-review → stall", flush=True)
    except Exception:  # noqa: BLE001 — probe must never break dispatch
        pass


def _strategist_target(conn: sqlite3.Connection, target_id: str,
                       target_kind: str) -> "tuple[int | None, str | None]":
    """Resolve a queued Strategist row to `(group_id, problem)`.

    v35 rows carry `target_kind='Group'` and the group id. Rows queued
    before v35 (or by any caller that still speaks the old shape) carry
    the problem name with `target_kind='Problem'`; those resolve to the
    problem's top group, which is what they always meant. Returns
    `(None, None)` when the row points at something that no longer
    exists — the caller reports `problem_not_found` rather than crashing
    the worker thread."""
    if target_kind == "Group":
        try:
            gid = int(target_id)
        except (TypeError, ValueError):
            return None, None
        row = conn.execute("SELECT problem FROM groups WHERE id = ?",
                           (gid,)).fetchone()
        if row is None:
            return None, None
        return gid, str(row["problem"])
    problem = str(target_id)
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (problem,)).fetchone() is None:
        return None, None
    return _groups.ensure_top_group(conn, problem), problem


def _derive_strategist_trigger(conn: sqlite3.Connection,
                                problem: str, *,
                                group_id: "int | None" = None,
                                routine_interval_min: float = 0.0,
                                since_iso: "str | None" = None,
                                ) -> tuple[str, int | None]:
    """Pick `trigger_kind` for a Strategist run on `problem`. Returns
    `(trigger, pending_review_id)` where pending_review_id is non-None
    iff a goal awaits review (regardless of the returned trigger).

    Priority order (user ruling 2026-07-12 — the PERIODIC wake outranks
    events): the design intent for routine is unconditional periodic
    dispatch; classifying it below the event conditions let a busy
    problem starve it indefinitely (stokes 2026-06-12: 0 routine over
    5h; b6 2026-07-12: a self-sustaining inject→reject→batch-done loop
    kept the belief-fixing wake out forever). Event conditions are
    PERSISTENT state (an unacknowledged batch / a pending goal does not
    evaporate), so losing one seat to the periodic wake only delays the
    event by one wake; the clock re-arms only on a routine commit, so a
    stolen seat re-fires the timer next tick. (The separate 'audit'
    trigger is retired 2026-07-25 — its belief sweep is phase 1 of the
    routine wake.)

      1. `routine` — the routine clock is due (`routine_interval_min`
         of RUNNING time since last routine commit; `since_iso`
         excludes down-time).
      2. `inject_batch_done` — unacknowledged Inject batch resolved.
      3. `pending_review` — a goal awaits a verdict.
      4. `inject_batch_done` again, on a structural STALL — the "empty
         batch done" reading (Phase 6, first_launch's replacement):
         only inject_batch_done.md carries the mandatory-advance rule,
         so classifying these wakes as routine invites a Noop →
         re-stall → re-wake livelock (P13 2026-06-13 shape).
      5. `routine` — residual (a seat whose reason resolved meanwhile).
    """
    # v35 — the lowest pending id in the PROBLEM may belong to another
    # group; handing it over asks group A to adjudicate B's goal. Pick
    # the lowest pending id this group actually owns.
    pending_id = None
    for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ?"
        "   AND status = 'pending_strategist_review' ORDER BY id",
        (problem,),
    ).fetchall():
        if group_id is None:
            pending_id = int(r["id"])
            break
        owner = _groups.group_for_goal(conn, problem, int(r["id"]))
        if owner is not None and int(owner["id"]) == int(group_id):
            pending_id = int(r["id"])
            break
    if _routine_due(conn, problem, routine_interval_min,
                    since_iso=since_iso, group_id=group_id):
        return ("routine", pending_id)
    unack_batches = db.unacknowledged_inject_batches(
        conn, problem, group_id)
    if unack_batches:
        return ("inject_batch_done", pending_id)
    if pending_id is not None:
        return ("pending_review", pending_id)
    # No running-set here (worker thread) — queue-only in-flight check;
    # a brief false-stall just classifies this wake as batch-done, which
    # is benign (same context, stricter advance rule). v35 — ask about
    # THIS group's slice, matching the T4 enqueue side.
    stalled = (db.is_group_stalled(conn, problem, group_id)
               if group_id is not None
               else db.is_problem_stalled(conn, problem))
    if stalled:
        return ("inject_batch_done", pending_id)
    return ("routine", pending_id)


def _strategist_row_is_stale(conn: sqlite3.Connection,
                             target_id: str, kind: str,
                             target_kind: str = "Problem") -> bool:
    """A queued Strategist whose problem has already committed `Ingest`
    has nothing left to decide — it would only spawn, Noop, and advance
    `last_strategist_at`. The dispatcher drops such a popped row.

    Phase 6 — the old drop condition (root goal `proved`) is exactly
    wrong now: a root-proved problem is where the Strategist must wake to
    judge the Manifest and commit `Ingest` (the only exit trigger), so
    the drop keys off the problem terminal state instead. If a rollback
    later revokes the Ingest (post-Ingest un-prove), the problem re-enters
    the live path and the normal triggers re-fire.

    v35 — a Strategist row is keyed by GROUP (`target_kind='Group'`,
    `target_id` the group id); pre-v35 rows carry the problem name with
    `target_kind='Problem'`. Both resolve through `_strategist_target`,
    so the terminal check keeps asking the same question of the same
    problem.

    The two unresolvable cases are NOT symmetric. A `Group` row naming a
    group that no longer exists is definitively garbage — group ids are
    never reused, so nothing can bring it back, and spawning would only
    fail. An unresolvable `Problem` row keeps the pre-v35 answer ("not
    stale"): that branch is reached by a name, and refusing to drop on a
    name we cannot resolve is the anti-wedge default it was given.
    """
    if kind != "Strategist":
        return False
    kind_str = str(target_kind or "Problem")
    _gid, problem = _strategist_target(conn, str(target_id), kind_str)
    if problem is None:
        return kind_str == "Group"
    return db.problem_ingested(conn, problem)


# ── run()-loop scheduling constants (hoisted from function locals, task #9) ──
SPAWN_COOLDOWN_SEC = 30.0

# Daemon start (ISO) — set once by run(); worker threads read it so the
# periodic clock (`_routine_due`) excludes down-time in the trigger
# derivation exactly as the T1 enqueue side does.
DAEMON_START_ISO: "str | None" = None

# v17 queue lease TTL: a lease older than this whose owner PID is dead OR
# recycled is reclaimable. Must exceed the longest legitimate pipeline wall
# (librarian audit / backward retry chains run for hours under load).
LEASE_TTL_SEC = 6 * 3600.0

# Re-export (tests + pop loop): the Lean/NL queue-kind partition lives
# in core/warmup.py with the background-warm machinery.
from .warmup import LEAN_QUEUE_KINDS  # noqa: E402


class WorkerDone(_typing.NamedTuple):
    """`_run_pipeline`'s result — NAMED so a new field can never silently
    outrun a positional unpack again (fc7445b: v17 grew the old 6-tuple,
    the worker-exception branch still destructured 5, and the daemon
    FATAL'd on the first worker exception; task #10(b))."""
    pipeline_id: str
    kind: str
    target_id: str
    target_kind: str
    outcome: str
    failure_reason: str


@_dc.dataclass(frozen=True)
class FutureMeta:
    """Per-future dispatch metadata (was a positional 6-tuple consumed by
    index — the annotated type had already drifted from reality once)."""
    pipeline_id: str
    kind: str
    target_id: str
    target_kind: str
    decision_id: "int | None"
    queue_row_id: int
CONSEC_SPAWN_FAIL_LIMIT = 10
CONSEC_GATEWAY_UNREACHABLE_LIMIT = 8
# Consecutive unclassified spawn deaths before the daemon stops and asks
# for a human (2026-08-08). Lower than the fast-fail limit on purpose:
# a fast-fail has a KNOWN shape and a known remedy (cooldown, or a quota
# wait), whereas "we do not know why this died" repeating is evidence of
# a fault nobody has diagnosed yet — grinding on it produces noise, not
# proofs, and the evidence rows are already in dead_attempts for
# whoever reads the log.
CONSEC_UNCLASSIFIED_LIMIT = 5
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
    # Per-kind rc=126 exponential RATE BRAKE (#103): kind → resume time.
    # NOT quota state — that is `core.quota.Ledger`'s, asked fresh each
    # tick and never mirrored here. The two shared this map until
    # 2026-08-13, and the mixing is why the release direction could not
    # be written safely: clearing the map would have released a live
    # rate brake, so `sync_quota_holds` cleared neither, and a Fable
    # weekly cap outlived the account switch that fixed it by eight
    # hours (2026-08-11).
    kind_backoff_until: "dict[str, float]" = field(default_factory=dict)
    consec_quota_per_kind: "dict[str, int]" = field(default_factory=dict)
    # Quota-wait (dispatch.quota_wait): global dispatch pause until the
    # subscription window resets. In-memory on purpose: a restart
    # re-probes the usage endpoint and re-enters the wait on the first
    # quota failure — same destination, fresh evidence.
    quota_wait_until: float = 0.0
    quota_wait_entered: float = 0.0
    quota_wait_logged_at: float = 0.0
    quota_wait_rechecked_at: float = 0.0  # early-recovery probe cadence
    quota_wait_paused: float = 0.0  # cumulative, excluded from budget
    # Global consecutive spawn_fast_fail counter; breaker exits the daemon
    # at CONSEC_SPAWN_FAIL_LIMIT (claude.exe persistently broken).
    consec_fast_fails: int = 0
    # How many times in a row the breaker tripped and the usage endpoint
    # refused to say whether it was quota (2026-08-13). Each one buys a
    # bounded hold instead of an exit; the count is what stops "cannot
    # tell" from becoming an indefinite silent wait. Cleared by any
    # spawn that succeeds — the same evidence that clears the others.
    consec_unconfirmed_trips: int = 0
    # Independent gateway_unreachable breaker (run #17: 48 strategies piled
    # up busy-looping against a dead gateway before this existed).
    consec_gateway_unreachable: int = 0
    # Consecutive `unclassified_spawn_failure` (2026-08-08). Unknown
    # causes no longer burn goal attempts, so nothing else would ever
    # stop a goal dying the same unexplained way forever. Escalation
    # goes to the OPERATOR, not the Strategist: a framework fault is
    # not something the Strategist can act on, and handing it one only
    # gets the fault rewritten as mathematics in the Programme. The
    # "machine never self-stops" promise is about hard PROBLEMS; broken
    # machinery is exactly when stopping loudly is correct.
    consec_unclassified: int = 0
    # DB write-through — see class docstring.
    librarian_fail_counts: "dict[str, int]" = field(default_factory=dict)
    # Lazy verify cache: problem → Defs/Root built clean (False =
    # quarantined for this daemon run).
    verified_problems: "dict[str, bool]" = field(default_factory=dict)


def _ensure_manifest(conn, manifests, problem: str) -> bool:
    """Late-registration guard (#125): the problems table can gain rows
    after daemon start (`asterism init` against a live daemon), which
    the startup manifest load never saw — every dispatch of the new
    problem then fast-failed `problem_not_found` in a T4-pumped loop,
    silently (the reason never reached the log). Register on first
    miss; a genuine ghost (row without a loadable Manifest) logs loudly
    and cools via TARGET_COOLDOWN_REASONS."""
    if problem in manifests:
        return True
    row = conn.execute(
        "SELECT manifest_path FROM problems WHERE name = ?",
        (problem,)).fetchone()
    if row is not None and hasattr(manifests, "load"):
        if manifests.load(problem, row["manifest_path"]) is not None:
            print(f"[manifest] late-registered {problem} "
                  f"(init after daemon start)", flush=True)
            return True
    print(f"[dispatch] {problem}: problem_not_found — no loadable "
          f"Manifest for this queue row (cooling target)", flush=True)
    return False


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
      - UPDATE the dispatch-time pipelines row (INSERTed 'running' by the
        pop loop via db.record_pipeline_start) to succeeded/failed
      - On failure: INSERT dead_attempt row with full artifacts JSON
        (per-retry rows are written eagerly by the retry helper itself)
      - Always rmtree .attempts/<pid>/ + .attempts/_backup_<pid>/ via WorkArea

    Phase 2 — `decision_id` carries the strategist_decisions row id
    when the spawning queue entry came from a Strategist Inject
    decision. Passed through to compile_context for the
    `## The argument for this brick` section, whose ancestor walk covers
    the rest. BFS-auto-dispatched pipelines have
    decision_id=None.

    NB: opens its own DB conn (sqlite3 thread safety)."""
    import json as _json
    conn = db.connect()
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
                # v35 — the seat belongs to a group; the row carries its
                # id. Legacy 'Problem' rows resolve to the top group.
                group_id, problem = _strategist_target(
                    conn, target_id, target_kind)
                if problem is None or not _ensure_manifest(
                        conn, manifests, problem):
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="failed", outcome="failed")
                    return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                mfst = manifests[problem]
                trigger, pending_id = _derive_strategist_trigger(
                    conn, problem, group_id=group_id,
                    routine_interval_min=config.get(
                        "strategist.interval_min", default=120.0,
                        env_var="ASTERISM_STRATEGIST_INTERVAL_MIN",
                        cast=float, workspace=workspace),
                    since_iso=DAEMON_START_ISO)
                _warn_consecutive_strategist(conn, problem, trigger)

                from ..pipeline import strategist
                r = strategist.run_strategist(
                    conn, problem=problem, trigger_kind=trigger,
                    tick=0,  # tick concept TBD; 0 as placeholder for now
                    workspace=workspace, mfst=mfst,
                    pipeline_id=pipeline_id,
                    pending_review_id=pending_id,
                    group_id=group_id,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                   status=status, outcome=r.outcome)
                if status == "failed":
                    # Problem-targeted forensic uses target_id=0 (INTEGER
                    # column; same convention as Forward below). Artifacts
                    # packed like every other branch (task #5 audit item h:
                    # this and Forward's final-failure record were the two
                    # that dropped them — a schema_invalid's decision.json
                    # IS the evidence, and the context/usage telemetry
                    # rides the same column).
                    _arts = pipeline.collect_artifacts(attempts_dir)
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind=target_kind,
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                        artifacts=(_json.dumps(_arts) if _arts else ""),
                    )
                return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            if (task_kind == "Forward"
                    or (task_kind == "Formalizer"
                        and target_kind == "Problem")):
                # Mint job: target = problem name (TEXT); no goal lookup.
                # 'Forward' = legacy queue rows (pre-merge recovery).
                problem = target_id
                if not _ensure_manifest(conn, manifests, problem):
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="failed", outcome="failed")
                    return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
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
                db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                   status=status, outcome=r.outcome)
                # Per-retry dead_attempts rows were written EAGERLY by
                # the retry helper (v38 — the dispatch-time pipelines
                # row satisfies the FK, so nothing is buffered any
                # more). Forward forensic rows use target_id=0 +
                # target_kind='Problem' (migration_plan §C option 1:
                # dead_attempts.target_id is INTEGER, so Problem-
                # targeted forensic uses 0 with the audit index living
                # on target_kind + decision_id).
                # Pipeline-level dead_attempt for the final outcome.
                # Skip when outcome is 'exhausted' — the helper has
                # already recorded the last retry's failure eagerly;
                # duplicating here would over-count.
                if (status == "failed"
                        and r.outcome != "exhausted"):
                    _arts = pipeline.collect_artifacts(attempts_dir)
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind=target_kind,
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                        artifacts=(_json.dumps(_arts) if _arts else ""),
                    )
                return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            if task_kind == "Scholar":
                # Paper v2 (D11): resolve + fetch a cited paper. Problem-
                # targeted like Forward; query/reason ride the FetchPaper
                # decision row (decision_id threaded from the queue).
                problem = target_id
                if not _ensure_manifest(conn, manifests, problem):
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="failed", outcome="failed")
                    return WorkerDone(pipeline_id, task_kind, target_id,
                                      target_kind, "failed",
                                      "problem_not_found")
                from ..pipeline import scholar
                r = scholar.run_scholar(
                    conn, problem=problem, workspace=workspace,
                    pipeline_id=pipeline_id, decision_id=decision_id,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                   status=status, outcome=r.outcome)
                if status == "failed":
                    _arts = pipeline.collect_artifacts(attempts_dir)
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind=target_kind,
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                        artifacts=(_json.dumps(_arts) if _arts else ""),
                    )
                return WorkerDone(pipeline_id, task_kind, target_id,
                                  target_kind, r.outcome,
                                  str(r.failure_reason or ""))

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
                if not _ensure_manifest(conn, manifests, problem):
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="failed", outcome="failed")
                    return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                if db.problem_ingest_signoff_pending(conn, problem):
                    # CONSUMER-side hard gate: while a problem awaits human
                    # sign-off, NO Librarian work runs — regardless of which
                    # path enqueued the row. The three scheduler-side checks
                    # (librarian_sched selfstart / refill / outstanding) are
                    # enqueue-suppression hints; this is the boundary. BUG3
                    # (149aec6) was exactly a dispatch path that forgot the
                    # check and drove harvest during sign-off — enforcing at
                    # the single consumption point closes the class, not the
                    # instance (2026-07-04 convention audit, finding 1).
                    print(f"[librarian] {problem}: dispatch blocked — "
                          f"ingest_signoff_pending (awaiting human sign-off)",
                          flush=True)
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="succeeded",
                                       outcome="success")
                    return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                            "success", "")
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
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="succeeded",
                                       outcome="success")
                    return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                            "success", "")
                # Per-file axiom check uses the operator's authorized
                # axioms via the ONE whitelist derivation
                # (`manifest.effective_axioms` — empty field falls back to
                # the framework default, never skips). Only migrate
                # consumes it.
                mfst = manifests[problem]
                whitelist = manifest.effective_axioms(
                    mfst, problem=problem)
                r = librarian.run_librarian(
                    conn, problem=problem, work_kind=work_kind,
                    workspace=workspace, pipeline_id=pipeline_id,
                    target=target, whitelist=whitelist,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                   status=status, outcome=r.outcome)
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
                return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            # Builder / Backward — Goal-targeted.
            goal_id = int(target_id)
            goal = db.get_goal(conn, goal_id)
            if goal is None:
                db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                   status="failed", outcome="failed")
                return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                        "failed", "goal_not_found")

            # Same late-registration guard as the Problem-target kinds —
            # without it a late-init problem's goal job died here on a
            # raw KeyError (worker-exception path) instead of a clean
            # problem_not_found.
            if not _ensure_manifest(conn, manifests, goal["problem"]):
                db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                   status="failed", outcome="failed")
                return WorkerDone(pipeline_id, task_kind, target_id,
                                  target_kind, "failed",
                                  "problem_not_found")
            mfst = manifests[goal["problem"]]

            if task_kind in ("Formalizer", "Backward", "Builder"):
                # Merged worker (update_plan_2026_07 #1): every goal job
                # runs the staged Formalizer engine (hint pre-pass →
                # intake → work loop in the strategy frame). 'Backward' /
                # 'Builder' = legacy queue rows from pre-merge recovery.
                r = pipeline.run_backward(
                    conn, goal_id=goal_id, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                    decision_id=decision_id,
                )
            else:
                r = pipeline.PipelineResult(outcome="failed",
                                            failure_reason="unknown_kind")

            status = "succeeded" if r.outcome in ("proved", "success") else "failed"
            db.finish_pipeline(conn, pipeline_id=pipeline_id,
                               status=status, outcome=r.outcome)

            # Phase 7 / v38 — per-retry failures are recorded EAGERLY by
            # the in-pipeline retry helper: one dead_attempts row + one
            # `goals.attempts++` per failed retry, in-helper, because
            # the pipelines row (FK target) exists from dispatch time.
            # Nothing to flush here — the pre-v38 buffer protocol lost
            # the rows whenever the worker thread died by exception
            # while the increments stayed banked (goal 7486,
            # 2026-08-08). A mid-loop moot after real failed retries
            # therefore now LEAVES their forensic rows in DB (they were
            # real LLM calls, and their attempts++ was always kept);
            # decision 2's "moot writes nothing" applies to the moot
            # detection itself, which still records nothing.

            # Capture artifacts from .attempts/<pid>/ before WorkArea rmtree.
            # Skip the pipeline-final dead_attempts INSERT for:
            #   - 'exhausted' outcome: helper already recorded the
            #     last retry's failure eagerly; duplicating here would
            #     violate the 1:1 attempts ↔ dead_attempts invariant.
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
                        "system_killed",   # OS/runtime death (2026-08-08)
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

            return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
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


def stop_file_path(workspace: Path) -> Path:
    """Graceful-stop signal (frontend charter §5-3): `asterism daemon
    stop` creates it; the tick loop stops spawning, drains in-flight
    workers, and exits cleanly — the mechanized form of the operator's
    'never kill a daemon with in-flight work' discipline."""
    return workspace / ".asterism" / "daemon.stop"


def _spawn_handoff_successor(workspace: Path, scope: "str | None") -> None:
    """Spawn the drift-handoff waiter: a detached `daemon start
    --wait-lock` that parks until THIS daemon's singleton lock frees,
    then boots a fresh daemon (current code, same scope) through
    daemon_start's usual relay. Must break away from our kill-on-close
    Job Object or it dies with us; best-effort — a failed spawn just
    means the operator restarts by hand (the drain already happened)."""
    import subprocess
    from . import process_group
    argv = [sys.executable, "-m", "Tooling.core.cli", "daemon", "start",
            "--wait-lock", "120"]
    if scope:
        argv += ["--scope", scope]
    flags = 0
    kwargs: dict = {}
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                 | process_group.breakaway_creationflags())
    else:
        kwargs["start_new_session"] = True
    try:
        # Waiter output goes to a logfile, not DEVNULL: the 2026-07-13
        # 21:01 handoff died without a trace (no successor log, no
        # process, nothing to autopsy) — whatever the waiter prints
        # (its REFUSED reason, a traceback) is the only evidence the
        # next failure will leave.
        logs_dir = workspace / ".asterism" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        waiter_log = open(logs_dir / "handoff-waiter.log", "ab")
        waiter_log.write(
            f"\n=== handoff waiter spawned {db.now()} ===\n".encode())
        waiter_log.flush()
        subprocess.Popen(argv, cwd=str(workspace),
                         stdout=waiter_log,
                         stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL,
                         creationflags=flags, **kwargs)
    except OSError as e:
        print(f"[dispatcher] handoff spawn failed ({e}) — restart the "
              f"daemon by hand (`asterism daemon start`)", flush=True)


def scope_mismatch_reason(workspace: Path,
                          scope: str) -> "str | None":
    """#158 pre-flight: None when `scope` (SQL LIKE, the same pattern
    dispatch filters on) matches at least one REGISTERED problem;
    otherwise a teaching refusal message.

    A no-match scope can never dispatch anything — the daemon boots,
    patrols an empty set forever, and the idle is indistinguishable
    from health (08-04 SLC: `reset` deletes the problems row; two
    restarts idled ~20min before the missing `init` was noticed).
    Registration — not goals — is the right predicate: a freshly
    init'd problem has no goals yet but is legitimately dispatchable
    (the Strategist bootstraps it).

    Read-only raw connection on purpose: this runs in the START
    caller's process while a daemon may be live, and a pre-flight must
    neither write nor auto-migrate (`db.connect` migrates)."""
    import sqlite3 as _sqlite3
    db_file = workspace / db.DB_PATH
    try:
        conn = _sqlite3.connect(
            f"file:{db_file.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM problems WHERE name LIKE ?",
                (scope,)).fetchone()[0]
        finally:
            conn.close()
    except _sqlite3.OperationalError:
        # No DB file / no problems table — same answer as 0 matches:
        # nothing is registered under this scope.
        n = 0
    if n:
        return None
    return (f"REFUSING to start: --scope {scope!r} matches no registered "
            f"problem — dispatch would idle forever and look healthy. "
            f"If this problem was just reset, `asterism reset` deletes "
            f"its registration: run `asterism init <problem>` first, "
            f"then start again (or fix the scope pattern).")


def run(workspace: Path, *, once: bool = False,
        scope: str | None = None) -> int:
    pid_lock = _acquire_singleton_lock(workspace)
    # The start-side anti-double-spawn marker is consumed here: the
    # singleton lock has settled the race either way. Tolerant unlinks
    # throughout the lifecycle files — the serve status poll reads them
    # every ~2s, and a bare unlink colliding with that read raises
    # WinError 32 (killed the 07-13 21:01 handoff waiter).
    fsutil.unlink_tolerant(
        workspace / ".asterism" / "daemon-starting.txt")
    if pid_lock is None:
        return 1
    import atexit
    atexit.register(lambda: fsutil.unlink_tolerant(pid_lock))
    # A stale stop file from a prior stop request must not insta-kill
    # this fresh daemon (the start side also clears it — belt+braces).
    fsutil.unlink_tolerant(stop_file_path(workspace))
    # Scope pointer is written by the DAEMON ITSELF (single truth): when
    # only the UI's daemon_start wrote it, a terminal-started run left
    # the UI reading the PREVIOUS run's scope — Stop on the wrong
    # problem page would have killed this run. "" = workspace-wide.
    from ..lsp import lifecycle as _gwl
    code_fp_at_boot = _gwl.code_fingerprint()
    # Config drift arms the same handoff as code drift (user call
    # 2026-07-18): config is process-cached, so a settings edit (UI
    # writes Asterism.yaml) only ever applies through a fresh process.
    # Kept OUT of daemon-fp.txt — the UI's "runs old code" comparison
    # and the gateway stale check stay code-only (a model change must
    # not cost a gateway re-warm).
    config_fp_at_boot = _gwl.config_fingerprint(workspace)
    try:
        _logs = workspace / ".asterism" / "logs"
        _logs.mkdir(parents=True, exist_ok=True)
        (_logs / "daemon-scope.txt").write_text(
            scope or "", encoding="utf-8")
        # boot fingerprint — daemon_status compares it against the
        # current tree so the UI can say "this daemon runs old code"
        # during the (self-resolving) drift window
        (_logs / "daemon-fp.txt").write_text(
            code_fp_at_boot, encoding="utf-8")
    except OSError:
        pass

    # Bind this process + every later spawn (claude / lake / lean / per-spawn
    # LSP) into a kill-on-close Job Object, so a hard daemon death reaps the
    # whole tree at the OS level — no manual orphan-cleanup ritual, no broad-kill
    # footgun (CLAUDE.md rule 8). The reusable LSP gateway breaks away (below) so
    # it survives. Soft: on failure the orphan-sweep below stays the safety net.
    from . import process_group
    if process_group.assign_self_to_kill_on_close_job():
        print("[daemon] process tree bound to kill-on-close job", flush=True)

    pool_size = config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=workspace)
    # The gateway RAM-clamps ITS worker pool with this same formula; a
    # daemon dispatching the un-clamped yaml value floods the smaller
    # slot pool and the register 500s read as gateway death (2026-07-19
    # 00:39 rc2: pool=6 vs 4 clamped slots → breaker exit). One formula,
    # both sides.
    _clamped, _clamp_msg = _gwl.ram_clamped_pool(
        pool_size, _gwl._interactive_slots(workspace))
    if _clamp_msg:
        print(f"[dispatcher] {_clamp_msg}", flush=True)
        pool_size = _clamped
    budget_sec = config.get(
        "dispatch.budget_sec", default=1800,
        env_var="ASTERISM_BUDGET_SEC", cast=int, workspace=workspace)
    # Quota-wait switch (user 2026-07-14): on = a CONFIRMED-exhausted
    # subscription window pauses dispatch until resets_at instead of
    # exiting (breaker consult + sleep-to-reset). Off = quota bursts
    # trip the fast-fail breaker and the daemon exits. Default OFF
    # (user 2026-07-18): an unattended run riding window after window
    # is opt-in — Settings toggle / yaml / env.
    quota_wait_enabled = str(config.get(
        "dispatch.quota_wait", default="false",
        env_var="ASTERISM_QUOTA_WAIT", workspace=workspace,
    )).strip().lower() in ("true", "1", "yes", "on")
    # `--once` runs are operator-attended experiments — finishing (with
    # the quota failure visible) beats silently parking for hours.
    quota_wait_enabled = quota_wait_enabled and not once
    # BUILDER_THRESHOLD routing retired with the Formalizer merge
    # (update_plan_2026_07 #1) — no Builder→Backward escalation exists;
    # `builder.threshold` / `dispatch.builder_threshold` config keys are
    # no longer read. `thresholds.BUILDER_THRESHOLD` survives only as an
    # internal small-retry-budget constant (librarian hole-fill + the
    # undispatched legacy builder module).
    thresholds.set_thresholds(
        shelve=config.get(
            "dispatch.shelve_threshold", default=8,
            env_var="ASTERISM_SHELVE_THRESHOLD", cast=int,
            workspace=workspace))
    # Phase 2 — T1 (wall-clock routine) interval in minutes. Default 60
    # per `docs/archive/design/phase2/pipelines.md` §5. Picked by `strategist_triggers`
    # each tick. Override via env var or Asterism.yaml for calibration.
    strategist_interval_min = config.get(
        "strategist.interval_min", default=120.0,
        env_var="ASTERISM_STRATEGIST_INTERVAL_MIN", cast=float,
        workspace=workspace,
    )
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
    # #158 authoritative check (the daemon-side twin of the
    # `daemon_start` pre-flight — this one also covers direct `run`
    # invocations and the code-drift handoff successor). Raising, not
    # returning: the CLI's except-path records the message in
    # daemon-exit.txt, so `daemon status` names the cause.
    if scope:
        _n_in_scope = conn.execute(
            "SELECT COUNT(*) FROM problems WHERE name LIKE ?",
            (scope,)).fetchone()[0]
        if not _n_in_scope:
            raise RuntimeError(
                f"--scope {scope!r} matches no registered problem — "
                f"dispatch would idle forever and look healthy. If this "
                f"problem was just reset, run `asterism init <problem>` "
                f"to re-register it, then start again.")
    # Restore the Librarian chain fail cap across restarts (#92 B#3): a stuck
    # unit's tally persists so it STALLs instead of looping forever.
    st.librarian_fail_counts.update(db.librarian_fail_counts_all(conn))
    # ManifestCache hot-reloads on Manifest.md mtime change at each
    # spawn-time access — daemon previously locked in the startup-time
    # parse, so user edits mid-run were invisible until restart. Cache
    # quacks like dict[str, Manifest] for downstream callers.
    manifests = manifest.ManifestCache(workspace)
    from ..state import settings as _settings
    _prob_rows = conn.execute(
        "SELECT name, manifest_path FROM problems").fetchall()
    for row in _prob_rows:
        mfst = manifests.load(row["name"], row["manifest_path"])
        if mfst is None:
            continue
        # Lazy settings migration (frontmatter dissolve): copy the
        # file's machine settings into problem_settings for keys with
        # no DB row yet. Idempotent — a UI edit is never clobbered by
        # a stale file; the daemon is the write side, so one run
        # migrates every problem it can load.
        try:
            _settings.migrate_from_manifest(conn, row["name"], mfst)
        except Exception as e:  # noqa: BLE001 — never blocks startup
            print(f"[settings-migrate] {row['name']}: "
                  f"{type(e).__name__}: {e}", flush=True)

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
    global DAEMON_START_ISO
    DAEMON_START_ISO = daemon_start_iso

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

    # Phase 1 gateway — NL-first background warm (core/warmup.py):
    # NL kinds dispatch immediately; Lean kinds gate on the ready
    # flip; warm/contract failure exits rc 2 after the NL drain. The
    # strategist commit path is gateway-free (dedupe defeq probes ride
    # the Forward side, which is gated).
    from . import warmup as _warmup
    gateway_warm = _warmup.start_background(workspace)

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

    stop_announced = False
    # Code-drift handoff: the daemon no longer dies with the serve
    # process (daemon_start's relay broke that chain), so "serve
    # restart" no longer implicitly means "daemon runs new code". The
    # MECHANISM replaces the discipline (owner): the daemon snapshots
    # the tree's fingerprint at boot, re-checks it on a slow cadence,
    # and on drift drains exactly like a graceful stop — then spawns a
    # lock-waiting successor that boots on current code with the same
    # scope. `--once` runs finish on their own and never hand off.
    handoff_enabled = (not once) and (
        str(config.get("dispatch.handoff_on_code_change", default="true",
                       env_var="ASTERISM_HANDOFF_ON_CODE_CHANGE",
                       workspace=workspace)).strip().lower()
        in ("true", "1", "yes", "on"))
    drifting = False
    fp_checked_at = time.monotonic()
    #: Last tick's quota-blocked kinds, for change-only logging. A local,
    #: not scheduler state, and deliberately so: nothing may mistake it
    #: for the authority. The ledger is the fact.
    _prev_blocked: "set[str]" = set()
    while True:
        # Graceful stop (charter §5-3): stop file present → no new
        # spawns; drain in-flight workers via the normal cascade below;
        # exit cleanly once empty. Never abandons a worker mid-proof.
        stopping = stop_file_path(workspace).exists()
        if stopping and not futures:
            print("[dispatcher] stop requested (daemon.stop) — no "
                  "in-flight work; exiting cleanly", flush=True)
            fsutil.unlink_tolerant(stop_file_path(workspace))
            _exit_pool_fast(pool)
            return 0
        if stopping and not stop_announced:
            print(f"[dispatcher] stop requested (daemon.stop) — draining "
                  f"{len(futures)} in-flight worker(s), no new spawns",
                  flush=True)
            stop_announced = True
        if (handoff_enabled and not drifting and not stopping
                and time.monotonic() - fp_checked_at >= _DRIFT_CHECK_SEC):
            fp_checked_at = time.monotonic()
            code_drift = _gwl.code_fingerprint() != code_fp_at_boot
            config_drift = (_gwl.config_fingerprint(workspace)
                            != config_fp_at_boot)
            if code_drift:
                drifting = True
                print(f"[dispatcher] code drift — the source tree changed "
                      f"under this daemon; draining {len(futures)} "
                      f"in-flight worker(s), then handing off to a fresh "
                      f"daemon on current code", flush=True)
            elif config_drift:
                drifting = True
                print(f"[dispatcher] config drift — Asterism.yaml/.env "
                      f"changed under this daemon; draining {len(futures)} "
                      f"in-flight worker(s), then handing off to a fresh "
                      f"daemon on current settings", flush=True)
        if drifting and not stopping and not futures:
            _spawn_handoff_successor(workspace, scope)
            print("[dispatcher] handoff successor spawned (waiting on the "
                  "singleton lock) — exiting cleanly", flush=True)
            _exit_pool_fast(pool)
            return 0

        # Cascade for any completed pipelines
        if futures:
            done, _ = wait(list(futures), timeout=0, return_when=FIRST_COMPLETED)
            for fut in done:
                meta = futures.pop(fut)
                # Phase 2.5 — running key includes decision_id so batch
                # Inject siblings (same target+kind, different
                # decision_id) don't share a slot.
                running.discard((meta.target_id, meta.kind,
                                 meta.decision_id))
                meta_decision_id = meta.decision_id
                # v17 lease completion: the pipeline finished (any
                # outcome — refill re-derives retries), release the
                # claimed queue row for good.
                db.complete_queue_row(conn, meta.queue_row_id)
                try:
                    done: WorkerDone = fut.result()
                    pid, kind, tid, tk, outcome, reason = done
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
                        st.kind_backoff_until[kind] = time.time() + backoff
                        # Tell the ledger what this spawn just learned.
                        # A provider with no usage API (agy has none —
                        # `agy --help` carries no quota subcommand) can
                        # only be known this way, and without it the
                        # signal died here as a single kind's backoff:
                        # the seat BOUND to this one kept running,
                        # manufacturing work for a pipeline that could
                        # not consume it. Same ledger as the probes, so
                        # the binding applies either way.
                        # Seat lookup by CONFIG key: `kind` here is the
                        # queue spelling ('Formalizer'), the seats are
                        # config keys ('formalizer'). Looking up the
                        # queue spelling is what silently disabled this
                        # in production (2026-08-07) — the miss returned
                        # None and the ledger never learned a thing.
                        _seat = _pipeline_seats().get(str(kind).lower())
                        if _seat is not None:
                            # A provider that STATES when its window
                            # reopens gets slept to; one that does not
                            # falls back to the blind backoff, which for
                            # agy's 3-hour wall meant probing it all the
                            # way down. Asked of the DECLARATION, not the
                            # name — this was `if seat == "antigravity"`
                            # inline until codex arrived and would have
                            # made it two branches.
                            _until = quota.reset_epoch(_seat[0])
                            _quota_ledger.observe(
                                _seat[0], _seat[1], until=_until,
                                detail=f"{kind} spawn refused on quota")
                        # Flush queued entries of this kind so the
                        # pop loop doesn't keep draining the backlog
                        # against an exhausted provider (each pop
                        # would re-fire and bump consec further).
                        flushed = db.flush_queue_kind(conn, kind=kind,
                                                      scope=scope)
                        print(f"[cooldown] {kind} quota_exhausted "
                              f"(consec={n}, backoff={backoff:.0f}s, "
                              f"flushed={flushed} queued; all {kind} "
                              f"dispatch suspended)", flush=True)
                        # Quota-wait: when the usage endpoint confirms
                        # a window is truly exhausted, sleep to its
                        # resets_at instead of blind-probing at the
                        # backoff cap. Unconfirmed (transient 429 /
                        # endpoint offline) keeps the exponential
                        # backoff above.
                        # classified=True: rc=126 means the spawn-side
                        # markers DID call this quota — no substitution.
                        quota_wait.maybe_enter(
                            st, enabled=quota_wait_enabled,
                            source=f"{kind} quota_exhausted",
                            trigger_quota_classified=True)
                    elif (outcome == "failed"
                          and reason in _failures.TARGET_COOLDOWN_REASONS):
                        st.cooldown_until[(tid, kind)] = (
                            time.time() + SPAWN_COOLDOWN_SEC)
                        if reason == "unclassified_spawn_failure":
                            st.consec_unclassified += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after an "
                                  f"UNCLASSIFIED spawn death (no attempts++"
                                  f"; consec={st.consec_unclassified})",
                                  flush=True)
                            if (st.consec_unclassified
                                    >= CONSEC_UNCLASSIFIED_LIMIT):
                                print(
                                    f"[dispatcher] "
                                    f"{st.consec_unclassified} consecutive "
                                    f"spawn deaths nobody can classify — "
                                    f"stopping. This is an OPERATOR "
                                    f"question, not a Strategist one: no "
                                    f"amount of re-planning fixes a fault "
                                    f"the framework cannot name. Read the "
                                    f"`unclassified_spawn_failure` rows in "
                                    f"dead_attempts (rc + duration + "
                                    f"stderr tail) and either classify the "
                                    f"cause in `state/failures.py` or fix "
                                    f"it.", flush=True)
                                return 2
                        elif reason == "spawn_fast_fail":
                            st.consec_fast_fails += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"spawn_fast_fail "
                                  f"(consec={st.consec_fast_fails})", flush=True)
                            if st.consec_fast_fails >= CONSEC_SPAWN_FAIL_LIMIT:
                                # Quota-wait: an exhausted subscription
                                # window shows up as a fast-fail burst
                                # whenever claude.exe dies without the
                                # rc=126 marker text. Ask the usage
                                # endpoint before declaring the exe
                                # broken — POSITIVE confirmation
                                # converts the trip into a wait; a
                                # healthy-quota answer keeps the exit
                                # (the breaker's actual job). Fetch
                                # failures get a retry budget (#115):
                                # the endpoint's own 429 at the moment
                                # quota dies is congestion, not
                                # evidence.
                                _trip = (f"{st.consec_fast_fails} "
                                         f"consecutive spawn_fast_fails")
                                # classified=False: these spawns were
                                # charged as exe breakage; a confirmed
                                # window means the markers missed a
                                # refusal, and maybe_enter says so.
                                _probe = quota_wait.maybe_enter(
                                    st, enabled=quota_wait_enabled,
                                    probe_attempts=(
                                        quota_wait.QUOTA_CONFIRM_ATTEMPTS),
                                    source=_trip,
                                    trigger_quota_classified=False)
                                if _probe:
                                    st.consec_fast_fails = 0
                                    st.consec_unconfirmed_trips = 0
                                elif (quota_wait_enabled
                                      and _probe.verdict == quota_wait.UNKNOWN
                                      and quota_wait.hold_unconfirmed(
                                          st, source=_trip)):
                                    # Held, not exited — see hold_unconfirmed.
                                    st.consec_fast_fails = 0
                                else:
                                    _why = (
                                        "the usage endpoint confirms quota is "
                                        "healthy, so this is the provider, "
                                        "not the window"
                                        if _probe.verdict == quota_wait.HEALTHY
                                        else "and the usage endpoint never "
                                             "answered, so quota could be "
                                             "neither confirmed nor ruled out")
                                    print(f"[dispatcher] "
                                          f"{st.consec_fast_fails} "
                                          f"consecutive spawn_fast_fails — "
                                          f"{_why}; exiting. Inspect "
                                          f".attempts/<pid>/_spawn.stderr "
                                          f"for the underlying error.",
                                          flush=True)
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
                        st.consec_unclassified = 0
                        st.consec_unconfirmed_trips = 0
                        # #103 — any non-quota, non-infra outcome on this
                        # kind proves the provider responded: release the
                        # rc=126 rate brake so dispatch resumes fresh.
                        # (Other infra reasons above are orthogonal to
                        # quota — handled in their own branch.) The
                        # QUOTA FACT is not touched here and never was
                        # ours to touch: the ledger holds it and is
                        # re-asked next tick.
                        if kind in st.consec_quota_per_kind:
                            st.consec_quota_per_kind.pop(kind, None)
                            st.kind_backoff_until.pop(kind, None)
                            print(f"[cooldown] {kind} rate brake released "
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
                    # A Goal-target failure lands in `dead_attempts`
                    # with its reason and detail; a Problem-target one
                    # (Strategist / Librarian) lands NOWHERE — the
                    # PipelineResult is dropped after this line and the
                    # attempts dir is rmtree'd on WorkArea exit. Two
                    # b6_1 wakes (07-30) failed with no trace at all,
                    # and reconstructing why cost a dig through the
                    # provider's private conversation store. One line
                    # is the whole fix.
                    if outcome == "failed" and tk != "Goal":
                        print(f"[cascade] {kind} {tk}={tid} "
                              f"reason={reason or '?'}", flush=True)
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
                    # fc7445b's class fix: named fields — this branch can
                    # never lag a growing record again (task #10(b)).
                    pid, kind, tid, tk = (meta.pipeline_id, meta.kind,
                                          meta.target_id, meta.target_kind)
                    infra_reason = _classify_worker_exception(exc)
                    # NB wording: an infra death adds no NEW attempts++,
                    # but any per-retry failures BEFORE the exception were
                    # already recorded eagerly in-loop (attempts++ AND the
                    # paired dead_attempts row — v38; pre-v38 the rows died
                    # with this stack frame while the increments stayed).
                    label = (f"{infra_reason} (infra — no further "
                             f"attempts++)"
                             if infra_reason
                             else "treating as failed (attempts++ paired "
                                  "with a worker_exception dead_attempt)")
                    print(f"[cascade] worker exception on {kind} "
                          f"{tk}={tid}: {exc}; {label}",
                          flush=True)
                    try:
                        # v38 — the dispatch-time 'running' row must not
                        # outlive its pipeline: finalize it here, or it
                        # sits 'running' until the next daemon start's
                        # recovery sweep.
                        db.finish_pipeline(conn, pipeline_id=pid,
                                           status="failed",
                                           outcome="failed")
                        # Non-infra exception on a Goal target: cascade_one
                        # below books one attempts++ with no worker left to
                        # write the forensic row — write it here (the
                        # pipelines row exists, so the FK holds; evidence
                        # before increment). Infra classifications skip
                        # both sides, mirroring the normal-return path.
                        if not infra_reason:
                            try:
                                _da_tid = (int(tid)
                                           if tk in ("Goal", "Strategy")
                                           else 0)
                            except (TypeError, ValueError):
                                _da_tid = 0
                            db.record_dead_attempt(
                                conn, target_id=_da_tid, target_kind=tk,
                                pipeline_id=pid,
                                failure_reason="worker_exception",
                                failure_detail=f"{type(exc).__name__}: "
                                               f"{exc}",
                            )
                        cascade_one(conn, pipeline_id=pid, kind=kind,
                                    target_id=tid, target_kind=tk,
                                    outcome="failed",
                                    failure_reason=infra_reason,
                                    decision_id=meta.decision_id)
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
                        if (kind in ("Backward", "Formalizer")
                                and tk == "Goal"):
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
                        if infra_reason == "gateway_unreachable":
                            if _gateway_unreachable_backoff(
                                    st, pool, kind=kind, tk=tk, tid=tid):
                                return 2
                        elif (infra_reason
                              in _failures.TARGET_COOLDOWN_REASONS):
                            # Registry-driven, like the normal-result path
                            # above — NOT a hand-written list. This branch
                            # used to name `transient_timeout` alone, so
                            # every other cooling reason arriving as a
                            # worker exception got re-dispatched on the
                            # very next tick with no back-off. It went
                            # unnoticed only because `_classify_worker_
                            # exception` returned exactly two reasons; the
                            # moment it learned a third (`verify_infra`,
                            # 2026-08-13) the omission would have turned a
                            # daemon that dies in 13 minutes into one that
                            # hot-loops full spawns forever, which is the
                            # more expensive failure.
                            st.cooldown_until[(tid, kind)] = (
                                time.time() + SPAWN_COOLDOWN_SEC)
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"{infra_reason} (no consec increment — "
                                  f"the circuit breaker is reserved for "
                                  f"true gateway death)",
                                  flush=True)
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
        # Library-ization chain — dedup→classify→migrate→bridge→marker —
        # has a chance to run, since that chain spans many ticks (Bug A).
        # `_harvest_outstanding`: durable-state backstop. `librarian_pending` is
        # a transient queue/running snapshot that can read False on the
        # proof→harvest handoff tick (root just integrity-verified, mechanical
        # dedup completing in a worker), letting the gate exit and kill the
        # in-flight Librarian — silently skipping harvest on a clean opted-in
        # proof. The marker/lifecycle/fail-count check is timing-independent and
        # holds the daemon until harvest actually finishes (or stalls).
        if (db.all_problems_ingested(conn, scope=scope)
                and not librarian_pending
                and not _harvest_outstanding(
                    conn, workspace, manifests, scope=scope,
                    fail_counts=st.librarian_fail_counts)):
            print("[dispatcher] all problems ingested", flush=True)
            _exit_pool_fast(pool)
            _released = db.release_own_leases(conn)
            if _released:
                print(f"[queue] released {_released} own lease(s) at "
                      f"graceful exit", flush=True)
            return 0

        # Quota-wait gate: while the subscription window is confirmed
        # exhausted, spawn nothing (refill + pop are the only spawn
        # sources). Triggers/reconcile/lease hygiene below still run —
        # they only touch the DB, and queued wakes fire the moment the
        # window resets.
        quota_waiting = quota_wait.tick(st, time.time(),
                                         enabled=quota_wait_enabled)

        # Per-(provider, model) quota, ahead of the global wait: a cap
        # that names ONE model must not stop the pipelines seated on a
        # different one. 2026-08-06 held a single boolean and paused a
        # whole run — formalizer on Gemini, judge movable to Opus, and
        # neither had a quota problem; eleven finished proposals were
        # discarded for a Fable weekly cap.
        #
        # ASKED, not mirrored (2026-08-13). This used to call
        # `sync_quota_holds`, a reconciler that copied the ledger's
        # answer into `st.quota_cooldown_kind` and popped it back out
        # again — a second home for one fact, and its release half
        # shipped broken: a Fable weekly cap held the Strategist for
        # eight hours across the account switch that had already lifted
        # it (2026-08-11). The ledger is now read directly, once per
        # tick, and there is no held state to forget to release.
        _blocks = quota.blocked_dispatch_kinds(
            _quota_ledger, _pipeline_seats())
        blocked_kinds = set(_blocks)
        _prev_blocked = quota.report_block_changes(_prev_blocked, _blocks)

        # Refill queue (uses in-memory `running` for dedup; st.cooldown_until
        # holds spawn_fast_fail back-offs; st.kind_backoff_until holds the
        # rc=126 rate brake; scope restricts to a benchmark subset like
        # `minif2f_%`).
        if not quota_waiting:
            bfs_refill(conn, running, st.cooldown_until, scope=scope,
                       kind_backoff=st.kind_backoff_until,
                       blocked_kinds=blocked_kinds,
                       verified_problems=st.verified_problems)

        # Phase 2 — Strategist T0/T1 triggers (T2 pending_review fires at
        # cascade time in `cascade_one` as the fast path). Skipped under
        # awaiting_human gate per-problem inside `strategist_triggers`.
        # Defaults to 120-min routine (`strategist.interval_min`).
        strategist_triggers(conn, running, scope=scope,
                            interval_min=strategist_interval_min,
                            daemon_start_iso=daemon_start_iso)

        # Per-tick stuck-state reconciler: the safety net for the two
        # mid-run-reachable stuck states the cascade fast paths can drop —
        # orphaned pending_review goals + NULL-outcome Inject wedges. Runs
        # every tick, in-flight gated, so a dropped wakeup self-heals within
        # one tick instead of waiting for restart / the 120-min routine.
        reconcile_stuck_states(conn, running, scope=scope)

        # v17 lease sweep: un-claim rows whose owner is provably gone —
        # dead PID OR lease older than the TTL (double guard: Windows
        # reuses PIDs). Covers a CONCURRENT dispatcher that crashed
        # mid-run (its startup recovery isn't coming); our own crashed
        # leases are handled by startup recovery. TTL must exceed the
        # longest legitimate pipeline wall (librarian audit / backward
        # retry chains run hours under load).
        from ..agent.sandbox import _pid_alive
        released = db.release_expired_leases(
            conn, scope=scope, ttl_sec=LEASE_TTL_SEC, pid_alive=_pid_alive)
        if released:
            print(f"[queue] released {released} expired lease(s) "
                  f"(dead owner or >{LEASE_TTL_SEC / 3600:.0f}h)",
                  flush=True)

        # Spawn from queue while pool has slots. Skip if a pipeline of
        # the same (target_id, kind) is already in flight in this
        # daemon — bfs_refill caps at 1 but daemon recovery + race
        # corners mean defense-in-depth here is cheap.
        # While the gateway is still warming, only NL kinds pop —
        # Lean rows stay queued (unleased) for the ready flip.
        # Rows popped this pass that are still cooling. Released AFTER
        # the loop, never inside it: releasing immediately would let the
        # very next `pop_queue` hand back the same row and spin.
        deferred_rows: "list[int]" = []
        while (not (stopping or drifting or quota_waiting
                    or gateway_warm["failed"])
                and len(futures) < pool_size):
            row = db.pop_queue(
                conn, scope=scope,
                exclude_kinds=(None if gateway_warm["ready"]
                               else LEAN_QUEUE_KINDS))
            if row is None:
                break
            qid = int(row["id"])
            target_id = str(row["target_id"])
            kind = str(row["kind"])
            # v17 — librarian per-file units carry the file in `payload`
            # JSON; the IN-PROCESS dispatch identity (running key,
            # _run_pipeline target, fail_counts key, logs) stays the
            # composed `problem\x1ffile` string, so everything downstream
            # of this point is unchanged. The \x1f encoding is retired
            # from the PERSISTED queue contract only.
            try:
                _payload = json.loads(row["payload"]) if row["payload"] \
                    else {}
            except (TypeError, ValueError):
                _payload = {}
            if kind == "Librarian" and _payload.get("file"):
                target_id = _lib_encode(str(row["problem"]),
                                        str(_payload["file"]))
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
            # Every skip below DISCARDS the claimed row (v17: pop leases,
            # it no longer deletes — an abandoned lease would sit until
            # TTL expiry and block refill dedup meanwhile). Matches the
            # old pop-deletes semantics exactly.
            if _dispatch_is_duplicate(running, target_id, kind, decision_id):
                db.complete_queue_row(conn, qid)
                continue
            # The door. `pool.submit(_run_pipeline` below is the only
            # spawn site in the codebase, so one predicate here governs
            # every dispatch there will ever be — including the next
            # path someone adds that re-enqueues directly and never
            # touches `bfs_refill`. Both refusals were previously
            # written out by hand in this loop, and the per-target half
            # was simply absent (2026-08-13: ten fast-fails in 51s).
            #
            # The two refusals part company in what they do to the ROW,
            # which is why `admission` returns a reason and not a bool:
            _verdict = admission(
                target_id, kind, cooldown_until=st.cooldown_until,
                kind_backoff=st.kind_backoff_until,
                blocked_kinds=blocked_kinds, now=time.time())
            if _verdict in (DENY_QUOTA, DENY_KIND_BACKOFF):
                # Kind-wide: DROP. The whole kind is parked, so refill
                # re-derives this row once it lifts, and holding a lease
                # meanwhile blocks refill's dedup.
                db.complete_queue_row(conn, qid)
                continue
            if _verdict == DENY_TARGET_COOLED:
                # Per-target back-off: PUT BACK. This exact row is still
                # wanted and only the clock is wrong — and it may have
                # come from a retry path that refill would never
                # re-derive. See `db.unclaim_queue_row`.
                deferred_rows.append(qid)
                continue
            # Drop a queued Strategist whose problem already committed
            # Ingest (e.g. a wake that raced the terminal commit). It
            # would only spawn + Noop. See `_strategist_row_is_stale`.
            if _strategist_row_is_stale(conn, target_id, kind, target_kind):
                print(f"[dispatch] skip Strategist "
                      f"{target_kind}={target_id} — already ingested "
                      f"(or its group is gone)", flush=True)
                db.complete_queue_row(conn, qid)
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
                db.complete_queue_row(conn, qid)
                continue
            if problem_name not in st.verified_problems:
                st.verified_problems[problem_name] = _verify_problem(
                    workspace, problem_name)
            if not st.verified_problems[problem_name]:
                db.complete_queue_row(conn, qid)
                continue
            pipeline_id = agent.new_pipeline_id()
            # v38 — the pipelines row is born HERE, status='running',
            # before the worker exists. dead_attempts (FK → pipelines.id)
            # can then be written eagerly during the pipeline, 1:1 with
            # every goals.attempts increment; the worker's completion
            # (or the exception handler / startup recovery) finalizes
            # this same row via db.finish_pipeline.
            db.record_pipeline_start(
                conn, pipeline_id=pipeline_id, kind=kind,
                target_id=target_id, target_kind=target_kind)
            running.add((target_id, kind, decision_id))
            fut = pool.submit(_run_pipeline, workspace, manifests,
                              kind, target_id, target_kind, pipeline_id,
                              decision_id)
            futures[fut] = FutureMeta(
                pipeline_id=pipeline_id, kind=kind, target_id=target_id,
                target_kind=target_kind, decision_id=decision_id,
                queue_row_id=qid)
            # Librarian per-file rows encode `problem\x1ffile` (#92); the
            # \x1f is non-printing, so render it readably in the log.
            _disp_prob, _disp_file = _lib_decode(target_id)
            _disp_tid = (f"{_disp_prob} file={_disp_file}"
                         if _disp_file else target_id)
            print(f"[dispatch] {kind} {target_kind}={_disp_tid} "
                  f"pid={pipeline_id[:8]}", flush=True)

        # Hand the still-cooling rows back, now that the pop loop cannot
        # immediately re-claim them. Release, not delete: the work is
        # still wanted (see `db.unclaim_queue_row`).
        for _qid in deferred_rows:
            db.unclaim_queue_row(conn, _qid)

        # Deferred warm-failure exit: keep the pre-NL-first semantics
        # (refuse to run without a healthy gateway + green contract),
        # but only after the in-flight NL work drains — its commits are
        # durable and the next start picks them up.
        if gateway_warm["failed"] and not futures:
            print(f"[gateway] warm-up failed: {gateway_warm['failed']} "
                  f"— NL work drained, exiting", flush=True)
            pool.shutdown(wait=True)
            db.release_own_leases(conn)
            return 2

        # Non-destructive emptiness check (v17): the old probing pop
        # silently DISCARDED a row whenever every popped row above had
        # been skipped (all-skips leaves `futures` empty with rows still
        # queued).
        if once and not futures and db.queue_size(
                conn, scope=scope, claimable_only=True) == 0:
            print("[dispatcher] --once and queue empty, exit")
            pool.shutdown(wait=True)
            db.release_own_leases(conn)
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
            db.release_own_leases(conn)
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

        # Budget clock excludes quota-wait time — a wait longer than
        # budget_sec must not read as budget exhaustion (that would be
        # exit-on-quota with extra steps).
        _now = time.time()
        if _now - start_time - quota_wait.paused_total(st, _now) > budget_sec:
            print(f"[dispatcher] {budget_sec}s budget exceeded; stopping",
                  flush=True)
            _exit_pool_fast(pool)
            _released = db.release_own_leases(conn)
            if _released:
                print(f"[queue] released {_released} own lease(s) at "
                      f"graceful exit", flush=True)
            return 1




def __getattr__(name):
    """Read-only aliases of the live thresholds (task #10(d)): historical
    call sites read `dispatcher.BUILDER_THRESHOLD`; the values live in
    `state.thresholds` (tune/monkeypatch THERE — setting an attribute on
    this module would shadow the live value)."""
    if name in ("BUILDER_THRESHOLD", "SHELVE_THRESHOLD"):
        return getattr(thresholds, name)
    raise AttributeError(name)
