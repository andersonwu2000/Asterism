"""Worker thread body — the pipeline runner and its result types.

Carved move-only from the dispatcher monolith (B4, 2026-08-29); bodies are
verbatim — see git history of core/dispatcher.py for provenance.
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

from ... import agent, pipeline
from .. import (config, fsutil, gateway_health, network_wait, quota,
                quota_wait, spawn_registry)
from ..admission import (ADMIT, DENY_KIND_BACKOFF, DENY_QUOTA,
                         DENY_TARGET_COOLED, admission)
from ..librarian_sched import _lib_decode, _derive_librarian_work  # noqa: E402
from . import _exit_pool_fast  # noqa: E402 — package-head helper
from .triggers import (_strategist_target, _warn_consecutive_strategist,  # noqa: E402
                       _derive_strategist_trigger)
from ...state import db, thresholds, transitions, tree
from ...state import intent as intent_mod
from ...state import failures as _failures
from ...state import groups as _groups
from ...quality import prune, verify


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
    from ...lsp.lifecycle import GatewayRefused
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
from ..warmup import LEAN_QUEUE_KINDS, NL_QUEUE_KINDS  # noqa: E402


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
    # Two clocks owned by `core.gateway_health`, both None when idle.
    # `gateway_down_since`: when `/health` first went silent after a
    # spawn reported the gateway unreachable (None = not holding).
    # `gateway_relaunched_at`: when the one self-heal credit was spent
    # (None = unspent, or earned back by a successful pipeline).
    gateway_down_since: "float | None" = None
    gateway_relaunched_at: "float | None" = None
    # Consecutive `unclassified_spawn_failure` (2026-08-08). Unknown
    # causes no longer burn goal attempts, so nothing else would ever
    # stop a goal dying the same unexplained way forever. Escalation
    # goes to the OPERATOR, not the Strategist: a framework fault is
    # not something the Strategist can act on, and handing it one only
    # gets the fault rewritten as mathematics in the Programme. The
    # "machine never self-stops" promise is about hard PROBLEMS; broken
    # machinery is exactly when stopping loudly is correct.
    consec_unclassified: int = 0
    # Network-wait state (`core/network_wait`, 2026-08-18): a spawn
    # death whose stderr names a transport failure parks dispatch until
    # a connectivity probe answers, instead of feeding the unclassified
    # breaker.
    net_wait_down: bool = False
    net_wait_entered: float = 0.0
    net_wait_probed_at: float = 0.0
    net_wait_logged_at: float = 0.0
    net_wait_paused: float = 0.0
    net_wait_hosts: "tuple[str, ...]" = ()
    #: When the park was triggered by the LOCAL channel (the zen shim),
    #: this holds its probe URL and resume requires THAT to answer —
    #: internet anchors answering is exactly what failed to protect the
    #: fleet on 2026-08-22.
    net_wait_channel: "str | None" = None
    net_chan_checked_at: float = 0.0
    # DB write-through — see class docstring.
    librarian_fail_counts: "dict[str, int]" = field(default_factory=dict)
    # Lazy verify cache: problem → Defs/Root built clean (False =
    # quarantined for this daemon run).
    verified_problems: "dict[str, bool]" = field(default_factory=dict)


def _ensure_intent(conn, intents, problem: str) -> bool:
    """Late-registration guard (#125): the problems table can gain rows
    after daemon start (`asterism init` against a live daemon), which
    the startup intent load never saw — every dispatch of the new
    problem then fast-failed `problem_not_found` in a T4-pumped loop,
    silently (the reason never reached the log). Register on first
    miss; a genuine ghost (queue row whose problems row is gone) logs
    loudly and cools via TARGET_COOLDOWN_REASONS."""
    if problem in intents:
        return True
    row = conn.execute(
        "SELECT 1 FROM problems WHERE name = ?", (problem,)).fetchone()
    if row is not None and hasattr(intents, "load"):
        if intents.load(problem) is not None:
            print(f"[intent] late-registered {problem} "
                  f"(init after daemon start)", flush=True)
            return True
    print(f"[dispatch] {problem}: problem_not_found — no problems row "
          f"for this queue row (cooling target)", flush=True)
    return False


#: How long the free `/health` probe may keep answering nothing before
#: the daemon gives up. DERIVED, not chosen: it is exactly the wall
#: clock the spawn-counting breaker would have spent reaching its limit,
#: so the moment of death does not move — only its price does. Pinned by
#: a test, because two constants that must stay in step are precisely
#: the pair someone tunes one of (the 900s/780s lesson).
GATEWAY_DOWN_GRACE_SEC = CONSEC_GATEWAY_UNREACHABLE_LIMIT * SPAWN_COOLDOWN_SEC


def _gateway_unreachable_backoff(st: "SchedulerState", pool, *,
                                 kind: str, tk: str, tid: str) -> bool:
    """Policy wrapper over `gateway_health.unreachable_backoff`: this
    file owns the numbers and the one place that may end a run."""
    if gateway_health.unreachable_backoff(
            st, kind=kind, tk=tk, tid=tid,
            cooldown_sec=SPAWN_COOLDOWN_SEC,
            limit=CONSEC_GATEWAY_UNREACHABLE_LIMIT):
        _exit_pool_fast(pool)
        return True
    return False


def _run_pipeline(workspace: Path,
                  intents: "intent_mod.IntentCache | dict[str, intent_mod.ProblemIntent]",
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
    # Claim this thread for this pipeline BEFORE anything below can
    # spawn: it is what lets a person's kill signal (HID §3.7) find the
    # process tree of THIS worker and no other. Pool threads are reused,
    # so the release in the `finally` is not optional.
    spawn_registry.bind(pipeline_id)
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
                if problem is None or not _ensure_intent(
                        conn, intents, problem):
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="failed", outcome="failed")
                    return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                intent = intents[problem]
                trigger, pending_id = _derive_strategist_trigger(
                    conn, problem, group_id=group_id,
                    routine_interval_min=config.get(
                        "strategist.interval_min", default=120.0,
                        env_var="ASTERISM_STRATEGIST_INTERVAL_MIN",
                        cast=float, workspace=workspace),
                    since_iso=DAEMON_START_ISO)
                _warn_consecutive_strategist(conn, problem, trigger)

                from ...pipeline import strategist
                r = strategist.run_strategist(
                    conn, problem=problem, trigger_kind=trigger,
                    tick=0,  # tick concept TBD; 0 as placeholder for now
                    workspace=workspace, intent=intent,
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
                if not _ensure_intent(conn, intents, problem):
                    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                       status="failed", outcome="failed")
                    return WorkerDone(pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                intent = intents[problem]
                from ...pipeline import forward
                r = forward.run_forward(
                    conn, problem=problem, workspace=workspace,
                    intent=intent, pipeline_id=pipeline_id,
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
                if not _ensure_intent(conn, intents, problem):
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
                from ...pipeline import librarian
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
                # (`intent_mod.effective_axioms` — empty field falls back to
                # the framework default, never skips). Only migrate
                # consumes it.
                intent = intents[problem]
                whitelist = intent_mod.effective_axioms(
                    intent, problem=problem)
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
            if not _ensure_intent(conn, intents, goal["problem"]):
                db.finish_pipeline(conn, pipeline_id=pipeline_id,
                                   status="failed", outcome="failed")
                return WorkerDone(pipeline_id, task_kind, target_id,
                                  target_kind, "failed",
                                  "problem_not_found")
            intent = intents[goal["problem"]]

            if task_kind in ("Formalizer", "Backward", "Builder"):
                # Merged worker (update_plan_2026_07 #1): every goal job
                # runs the staged Formalizer engine (hint pre-pass →
                # intake → work loop in the strategy frame). 'Backward' /
                # 'Builder' = legacy queue rows from pre-merge recovery.
                r = pipeline.run_backward(
                    conn, goal_id=goal_id, workspace=workspace,
                    intent=intent, pipeline_id=pipeline_id,
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
        spawn_registry.unbind()
        conn.close()


