"""The dispatcher main loop — run().

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
                quota_wait, spawn_registry as _spawn_registry)
from ..admission import (ADMIT, DENY_KIND_BACKOFF, DENY_QUOTA,
                         DENY_TARGET_COOLED, admission)
from ..warmup import LEAN_QUEUE_KINDS, NL_QUEUE_KINDS  # noqa: E402
from ..librarian_sched import (_advance_librarian_chain, _harvest_outstanding,  # noqa: E402
                               _lib_decode, _lib_encode, _librarian_refill)
from ...state.transitions import cascade_one, _reconcile_goal_after_strategy_loss  # noqa: E402
from ...state.recovery import recover_at_startup as _recover_at_startup  # noqa: E402
from . import (TICK_TIMEOUT, _DRIFT_CHECK_SEC, _quota_ledger,  # noqa: E402
               _pipeline_seats, _exit_pool_fast)
from . import worker  # noqa: E402 — DAEMON_START_ISO's one owner (module-attr write)
from .worker import (WorkerDone, FutureMeta, SchedulerState, _run_pipeline,  # noqa: E402
                     _classify_worker_exception, _gateway_unreachable_backoff,
                     SPAWN_COOLDOWN_SEC, LEASE_TTL_SEC, CONSEC_SPAWN_FAIL_LIMIT,
                     CONSEC_UNCLASSIFIED_LIMIT, GATEWAY_DOWN_GRACE_SEC,
                     QUOTA_BACKOFF_BASE_SEC, QUOTA_BACKOFF_CAP_SEC)
from .refill import (bfs_refill, _verify_problem, _problem_of_target,  # noqa: E402
                     env_blocked_kinds,
                     _dispatch_is_duplicate)
from .triggers import (reconcile_stuck_states, strategist_triggers,  # noqa: E402
                       strategist_has_nothing_to_deliver, _row_is_stale)
from .lock import stop_file_path, _acquire_singleton_lock, _spawn_handoff_successor  # noqa: E402
from ...state import db, thresholds, transitions, tree
from ...state import commands as _commands
from ...state import intent as intent_mod
from ...state import failures as _failures
from ...state import groups as _groups
from ...quality import prune, verify


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------

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
    from ...lsp import lifecycle as _gwl
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
    # fresh silent-degradation ledger — `daemon status`'s `degraded`
    # field describes THIS run (core/degraded.py)
    from .. import degraded as _degraded
    _degraded.reset(workspace)
    # Same contract, same reason: `promotion_gate.json` is this run's
    # in-flight cold builds, and a daemon killed mid-build leaves a row
    # that no process is running behind (`pipeline/_olean_warm.py`).
    from ...pipeline import _olean_warm as _promotion_state
    _promotion_state.reset_state(workspace)

    # Bind this process + every later spawn (claude / lake / lean / per-spawn
    # LSP) into a kill-on-close Job Object, so a hard daemon death reaps the
    # whole tree at the OS level — no manual orphan-cleanup ritual, no broad-kill
    # footgun (CLAUDE.md rule 8). The reusable LSP gateway breaks away (below) so
    # it survives. Soft: on failure the orphan-sweep below stays the safety net.
    from .. import process_group
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
    # Adaptive RAM ledger (owner design 2026-08-25): with
    # `dispatch.ram_budget` set, the ledger paces both worlds BENEATH
    # `pool_size` (a hard ceiling): Lean admission follows the gateway's
    # ledger-driven open-slot count, NL admission follows measured
    # available RAM (NL priority; claimed slots finish first).
    ledger = None
    from .. import ram_ledger
    _budget_spec = ram_ledger.env_budget_spec(workspace)
    if _budget_spec:
        _machine_gb = ram_ledger.total_gb()
        _budget_gb = ram_ledger.parse_budget(_budget_spec, _machine_gb)
        if _budget_gb:
            ledger = ram_ledger.DispatcherLedger(
                _budget_gb, _machine_gb,
                idle_spares=ram_ledger.idle_spares(workspace),
                pressure_headroom_gb=config.get(
                    "ledger.pressure_headroom_gb",
                    default=ram_ledger.DispatcherLedger.PRESSURE_HEADROOM_GB,
                    env_var="ASTERISM_PRESSURE_HEADROOM_GB",
                    cast=float, workspace=workspace),
                pressure_release_slack_gb=config.get(
                    "ledger.pressure_release_slack_gb",
                    default=ram_ledger.DispatcherLedger.PRESSURE_RELEASE_SLACK_GB,
                    env_var="ASTERISM_PRESSURE_RELEASE_SLACK_GB",
                    cast=float, workspace=workspace))
            print(f"[dispatcher] RAM ledger active — budget "
                  f"{_budget_gb:.1f} GB of {_machine_gb:.1f} GB; "
                  f"Lean width follows the ledger's target_slots"
                  f"; in-flight ceiling = dispatch.pool ({pool_size})",
                  flush=True)
        else:
            print(f"[dispatcher] dispatch.ram_budget={_budget_spec!r} "
                  f"unparseable — staying on static dispatch.pool",
                  flush=True)
    # Batch builds borrow lanes from the gateway (owner ruling
    # 2026-08-30): every daemon-side `lake build` — dedupe pre-flight,
    # Backward batch, commit verify, Librarian — asks /build/lease for
    # threads and the ledger for RAM headroom before it runs. Installed
    # lazily: the gate only talks to the gateway at build time and bounds
    # the build locally while the gateway is unreachable.
    from ...pipeline import _lake as _lake_gate
    _machine_for_builds = ram_ledger.total_gb()
    _lake_gate.install_build_gate(_lake_gate.GatewayBuildGate(
        f"http://127.0.0.1:{_gwl._gateway_port(workspace)}",
        owner=f"daemon-{os.getpid()}",
        ram_fit=lambda n: ram_ledger.build_threads_fit(
            n, machine_gb=_machine_for_builds)))
    budget_sec = config.get(
        "dispatch.budget_sec", default=1800,
        env_var="ASTERISM_BUDGET_SEC", cast=int, workspace=workspace)
    # One work unit's worth of time — what a relaunched gateway must
    # outlive (or beat with a finished pipeline) to earn its self-heal
    # credit back. Same field the spawns themselves are capped by, so
    # the two cannot drift into disagreeing about what "long enough to
    # be doing something" means.
    spawn_budget_sec = config.get(
        "dispatch.spawn_timeout_sec", default=1800,
        env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int, workspace=workspace)
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
    # In ledger mode the executor is a thread-count backstop, not the
    # admission mechanism — sized to what the budget could ever admit
    # (Lean ceiling at zero NL demand + the NL hard cap).
    _executor_cap = pool_size if ledger is None else min(
        160,
        ram_ledger.compute_target_slots(
            budget_gb=ledger.budget_gb, nl_demand=0)
        + ledger.nl_hard_cap())
    pool = ThreadPoolExecutor(max_workers=_executor_cap)
    # Promotion cold-build gate (owner ruling 2026-08-30, task #231; was
    # the #103 best-effort .olean warmer): verify_housekeeping promotes a
    # strategy (parent → alias rewrite) and the status flip waits for a
    # cold `lake build` of the alias plus every strategy that imports it,
    # run on the gate's own daemon thread — off the main thread AND off
    # this LLM worker pool (#118) — through the build lease. Disabled
    # (`verify.olean_warm=false`) the gate answers "built" at once: the
    # pre-2026-08-30 shape, for debugging only.
    from ...pipeline._olean_warm import PromotionGate
    _olean_warm_raw = config.get(
        "verify.olean_warm", default=True,
        env_var="ASTERISM_OLEAN_WARM", workspace=workspace)
    olean_warm_enabled = (
        _olean_warm_raw if isinstance(_olean_warm_raw, bool)
        else str(_olean_warm_raw).strip().lower() in ("true", "1", "yes", "on"))
    promotion_gate = PromotionGate(workspace, enabled=olean_warm_enabled)
    atexit.register(lambda: promotion_gate.shutdown(wait=False))
    futures: dict[Future, tuple[str, str, str, str]] = {}
    # HID §3.7 — the kill signal's daemon half. `apply_pending` runs in
    # this loop and needs two facts only the loop has (is that pipeline in
    # THIS daemon's flight, and what process tree is it), so they are
    # handed down rather than reached up for.
    signals = _spawn_registry.SignalSink(
        _spawn_registry.in_flight_over(futures))
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
        _sc, _sa = db.scope_sql(scope, "name")
        _n_in_scope = conn.execute(
            f"SELECT COUNT(*) FROM problems WHERE {_sc}",
            _sa).fetchone()[0]
        if not _n_in_scope:
            raise RuntimeError(
                f"--scope {scope!r} matches no registered problem — "
                f"dispatch would idle forever and look healthy. If this "
                f"problem was just reset, run `asterism init <problem>` "
                f"to re-register it, then start again.")
    # Restore the Librarian chain fail cap across restarts (#92 B#3): a stuck
    # unit's tally persists so it STALLs instead of looping forever.
    st.librarian_fail_counts.update(db.librarian_fail_counts_all(conn))
    # IntentCache reads the DB fresh at each spawn-time access — a UI
    # or CLI charter/word edit is live on the very next access. Cache
    # quacks like dict[str, ProblemIntent] for downstream callers.
    intents = intent_mod.IntentCache(workspace)
    _prob_rows = conn.execute("SELECT name FROM problems").fetchall()
    for row in _prob_rows:
        intents.load(row["name"])

    _recover_at_startup(conn, workspace, scope=scope)

    # Spawn-sandbox sweep: clean any orphan sandboxes left by SIGKILL'd
    # spawns from a prior daemon run (per docs/archive/spawn_sandbox.md §3.3).
    # Runs after _recover_at_startup so DB state is consistent before
    # filesystem state is reconciled. Sweep skips sandboxes whose owner
    # daemon is alive (guards against concurrent daemons).
    from ...agent import sandbox as _spawn_sandbox
    _sb_counters = _spawn_sandbox.sweep_orphan_sandboxes(workspace)
    if any(_sb_counters[k] for k in
           ("rolled_back", "deleted_committed", "corrupt_manifest",
            "drift_warnings", "skipped_alive_owner")):
        print(f"[sandbox-sweep] startup: {_sb_counters}", flush=True)

    # Refresh BRIEF.md for every registered problem at startup. Covers
    # charter/word edits + Library promotes since the last daemon run
    # (daemon has no hot-reload; startup is the canonical refresh point).
    # Lemma resolution can take ~30s when lemma hints are dense; only
    # paid once per startup, off the dispatch path.
    from ...state import brief
    brief.write_for_all_problems(conn, workspace, intents)

    scope_label = f", scope={scope!r}" if scope else ""
    if ledger is not None:
        print(f"[dispatcher] ledger pools: executor cap "
              f"{_executor_cap}, nl hard cap {ledger.nl_hard_cap()}",
              flush=True)
    print(f"[dispatcher] start, pool={pool_size}, "
          f"problems={list(intents)}{scope_label}",
          flush=True)
    start_time = time.time()
    # Daemon start as an ISO timestamp — the T1 routine clock baseline, so
    # paused/down time between runs is excluded from the routine interval.
    from datetime import datetime as _dt, timezone as _tz
    daemon_start_iso = _dt.fromtimestamp(start_time, tz=_tz.utc).isoformat()
    # B4: the flag's one owner is worker.py — a bare `global` here
    # would rebind loop's own module and starve worker's reader.
    worker.DAEMON_START_ISO = daemon_start_iso

    # Surface problems paused on an unresolved RequestUserAmend up front.
    # bfs_refill silently skips these (awaiting_human gate), so without
    # this line a scoped daemon whose only in-scope problem is paused is
    # indistinguishable from a hang — 2026-06-12 a paused P12
    # (stokes_induced_orient) read as a multi-hour gateway/tree-render
    # hang across two sessions. Operator must resolve the amend (apply
    # the proposed body, clear the decision) then
    # re-run. Cheap: idx_sd_outcome backs the filter.
    _paused_q = ("SELECT DISTINCT problem FROM strategist_decisions "
                 "WHERE outcome = 'awaiting_human'")
    _sc, _paused_params = db.scope_sql(scope)
    if _sc:
        _paused_q += f" AND {_sc}"
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
    from .. import warmup as _warmup
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
        tree_problems = list(intents)

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
            if os.environ.get("INVOCATION_ID"):
                # Under systemd the unit supervises ONLY the main PID: a
                # self-spawned successor is an unsupervised orphan, and
                # its crash is a silent fleet stop (measured 2026-08-24,
                # Oracle boarding — the successor died on a gateway port
                # race and nothing restarted anything). Exit non-zero
                # instead: Restart=on-failure relaunches THIS unit on
                # current code, supervision intact. 75 = EX_TEMPFAIL.
                print("[dispatcher] drift handoff under systemd — exiting "
                      "rc=75 so the unit's Restart relaunches on current "
                      "code", flush=True)
                _exit_pool_fast(pool)
                return 75
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
                    # A worker a person killed does not know it was
                    # killed; §3.7's signal is what its ending means.
                    outcome, reason = _commands.finalise_signalled(
                        conn, signals, pid, outcome, reason)
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
                        if reason == "provider_network":
                            # A named transport failure: probe, and park
                            # when the probe confirms the network is
                            # gone — never the unclassified breaker
                            # (2026-08-18; the 08-17 outage exited rc=2
                            # on twelve of these needing an operator on
                            # site). A positive probe = blip: keep the
                            # ordinary cooldown and move on.
                            network_wait.maybe_enter(
                                st, kind=kind,
                                source=f"{kind} {tk}={tid} network "
                                       f"failure")
                        elif reason == "unclassified_spawn_failure":
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
                        # A pipeline finished, so a relaunched gateway
                        # has earned its credit back (gateway_health).
                        st.gateway_relaunched_at = None
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
                                   intents=intents,
                                   promotion_gate=promotion_gate)

        # Per-problem post-proved gate. Only problems whose root just
        # flipped to 'proved' AND haven't yet passed integrity_gate
        # under this DB are visited — `db.unverified_proved_roots`
        # returns at most that subset, dropping to [] once every root
        # is verified. The earlier formulation iterated `intents`
        # every tick and paid one gateway-driven axiom_probe per
        # proved root every loop iteration (244 miniF2F roots stalled
        # dispatch for ~115min on every restart); the marker in
        # `goals.integrity_verified` is what keeps this O(unverified)
        # instead of O(all proved). Rollback paths flip the marker off
        # transparently via `db.update_goal_status` whenever a goal
        # leaves 'proved', so a once-failed root re-enters this gate
        # on the next tick after cascade rollback.
        for problem_name in db.unverified_proved_roots(conn):
            if problem_name not in intents:
                # Root proved for a problem we do not have an intent
                # for in-process (CLI invoked with a scope filter that
                # excluded it, or the row was never registered).
                # Skip without flipping the marker — it'll get picked
                # up the next run that loads this problem.
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
                conn, workspace, problem_name, intents[problem_name])
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
            conn, workspace, running, intents, scope=scope,
            fail_counts=st.librarian_fail_counts)

        # Workspace-wide exit (Phase 6): every problem has committed its
        # `Ingest` terminal (the Strategist's charter-satisfied judgment —
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
                    conn, workspace, intents, scope=scope,
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
        # Network-wait gate, same contract: while the network is down,
        # spawn nothing; DB-only housekeeping below still runs.
        network_waiting = network_wait.tick(st, time.time())

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
        blocked_kinds |= env_blocked_kinds()
        _prev_blocked = quota.report_block_changes(_prev_blocked, _blocks)

        # Human commands (human_interface_design.md §3.3): serve only
        # INSERTs the queue row — this is the half that applies it,
        # through the Strategist's own appliers (actor='human'). Ahead
        # of the refill so a command's dispatch joins THIS tick's fan-out
        # instead of waiting for the next one. Guarded: the queue is a
        # guest in this loop and must never be able to wedge it.
        try:
            _human = _commands.apply_pending(conn, workspace,
                                             signal_sink=signals)
            for _c in _human:
                print(f"[commands] #{_c['id']} {_c['kind']} → "
                      f"{_c['status']}: {_c['outcome']}", flush=True)
        except Exception as exc:  # noqa: BLE001 — never wedge the tick
            print(f"[commands] apply pass failed: {exc}", flush=True)
            _degraded.record(workspace, "human_commands_apply", str(exc))

        # Refill queue (uses in-memory `running` for dedup; st.cooldown_until
        # holds spawn_fast_fail back-offs; st.kind_backoff_until holds the
        # rc=126 rate brake; scope restricts to a benchmark subset like
        # `minif2f_%`).
        if not (quota_waiting or network_waiting):
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
                            daemon_start_iso=daemon_start_iso,
                            suppress_stall=promotion_gate.has_pending())

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
        from ...agent.sandbox import _pid_alive
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
        # Free liveness check, dormant until a spawn has already told us
        # the gateway is unreachable. See `core.gateway_health`.
        gateway_down = gateway_health.liveness_gate(st)
        while not (stopping or drifting or quota_waiting
                   or network_waiting or gateway_down
                   or gateway_warm["failed"]):
            if ledger is None:
                # Legacy static pool: one number for both worlds.
                if len(futures) >= pool_size:
                    break
                _exclude = (None if gateway_warm["ready"]
                            else LEAN_QUEUE_KINDS)
            else:
                # RAM ledger: the two worlds admit independently. Lean
                # gates on the gateway's CONFIRMED open slots (the
                # /register free-slot contract), NL gates on measured
                # available RAM against the budget's leftover.
                _lean_fly = sum(1 for _m in futures.values()
                                if _m.kind in LEAN_QUEUE_KINDS)
                _nl_fly = len(futures) - _lean_fly
                # Demand over forecast (owner ruling 2026-08-26): the
                # target reserves for IN-FLIGHT NL only — queue length
                # never predicted simultaneous NL (admission is paced),
                # so the queued-wakes reserve paid throughput for a
                # forecast wrong in both directions. A blocked wake
                # yields a slot instead (request_nl_yield below).
                ledger.tick(
                    nl_demand=_nl_fly,
                    push=lambda t, f: _gwl.push_warm_target(
                        t, f, workspace=workspace))
                if ledger.dispatch_paused:
                    # Measured pressure (cgroup footprint or available
                    # RAM): NOTHING dispatches into a squeeze — in-
                    # flight work keeps its seats, releases shed
                    # (owner-spotted hole 2026-08-26).
                    break
                if len(futures) >= pool_size:
                    # `dispatch.pool` is a HARD CEILING over both worlds
                    # (owner 2026-09-06): on a subscription board the
                    # binding resource is the five-hour quota window, not
                    # RAM — full ledger width burned one out in 3.5h.
                    break
                _lean_ok = (gateway_warm["ready"]
                            and _lean_fly < ledger.open_slots)
                _nl_ok = ledger.nl_admissible(_nl_fly)
                if (not _nl_ok and ledger.nl_blocked_by_budget
                        and ledger.free_slots > 0
                        and db.queue_size(
                            conn, scope=scope, kinds=NL_QUEUE_KINDS,
                            claimable_only=True) > 0):
                    ledger.request_nl_yield()
                if not (_lean_ok or _nl_ok):
                    break
                _exclude = (LEAN_QUEUE_KINDS if not _lean_ok
                            else (NL_QUEUE_KINDS if not _nl_ok
                                  else None))
            row = db.pop_queue(
                conn, scope=scope, exclude_kinds=_exclude)
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
            # Drop a row whose target settled between enqueue and pop:
            # a Strategist for an ingested problem / retired group, or
            # a Formalizer/Builder for a goal an OR-parallel racer or a
            # cascade already settled. See `_row_is_stale`.
            if _row_is_stale(conn, target_id, kind, target_kind):
                print(f"[dispatch] skip {kind} "
                      f"{target_kind}={target_id} — target already "
                      f"settled (terminal / retired / gone)", flush=True)
                db.complete_queue_row(conn, qid)
                continue
            # …and the row whose REASON settled, not its target: a
            # batch-done seat whose batch was acknowledged by the wake
            # that was in flight when it was enqueued. Same door, its
            # own sentence — the two say different things to whoever
            # reads the log.
            if kind == "Strategist" and strategist_has_nothing_to_deliver(
                    conn, target_id, target_kind,
                    routine_interval_min=strategist_interval_min,
                    since_iso=daemon_start_iso):
                print(f"[dispatch] skip Strategist "
                      f"{target_kind}={target_id} — nothing to deliver",
                      flush=True)
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
                verdict = _verify_problem(workspace, problem_name)
                if verdict is None:
                    # fenced out for lack of room: no verdict, no cache —
                    # PUT BACK like a cooled target (only the room is wrong)
                    deferred_rows.append(qid)
                    continue
                st.verified_problems[problem_name] = verdict
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
            fut = pool.submit(_run_pipeline, workspace, intents,
                              kind, target_id, target_kind, pipeline_id,
                              decision_id)
            futures[fut] = FutureMeta(
                pipeline_id=pipeline_id, kind=kind, target_id=target_id,
                target_kind=target_kind, decision_id=decision_id,
                queue_row_id=qid)
            if ledger is not None and kind not in LEAN_QUEUE_KINDS:
                # Ledger credit: this spawn's RSS is not in the system
                # counters yet — debit it so the tight loop cannot
                # burst past the measured floor.
                ledger.note_nl_admit()
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

        # Deferred gateway exit — warm-up failure, or a hold that
        # outlived its grace (`gateway_health.fatal_reason` owns WHICH
        # endings exist; this owns the ending). Keeps the pre-NL-first
        # semantics, but only after in-flight NL work drains: those
        # commits are durable and the next start picks them up.
        _healed, _fatal = (None, None) if futures else \
            gateway_health.resolve_fatal(
                st, workspace, warm_failed=gateway_warm["failed"],
                holding=gateway_down, now=time.time(),
                grace_sec=GATEWAY_DOWN_GRACE_SEC,
                budget_sec=spawn_budget_sec)
        if _healed is not None:
            gateway_warm = _healed
        elif _fatal:
            print(f"[gateway] {_fatal} — NL work drained, exiting",
                  flush=True)
            pool.shutdown(wait=True)
            db.release_own_leases(conn)
            return 2

        # Non-destructive emptiness check (v17): the old probing pop
        # silently DISCARDED a row whenever every popped row above had
        # been skipped (all-skips leaves `futures` empty with rows still
        # queued).
        # A promotion in the cold-build gate is work in flight (2026-08-30):
        # its flip lands on a later tick, so neither exit may fire before
        # the gate has answered.
        if promotion_gate.has_pending():
            time.sleep(0.2)
            continue
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
        if (_now - start_time - quota_wait.paused_total(st, _now)
                - network_wait.paused_total(st, _now)) > budget_sec:
            print(f"[dispatcher] {budget_sec}s budget exceeded; stopping",
                  flush=True)
            _exit_pool_fast(pool)
            _released = db.release_own_leases(conn)
            if _released:
                print(f"[queue] released {_released} own lease(s) at "
                      f"graceful exit", flush=True)
            return 1




