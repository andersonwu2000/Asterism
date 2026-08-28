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

from ... import agent, pipeline
from .. import config, fsutil, gateway_health, network_wait, quota, quota_wait
from ..admission import (ADMIT, DENY_KIND_BACKOFF, DENY_QUOTA,
                        DENY_TARGET_COOLED, admission)
from ...state import db, thresholds, transitions, tree
from ...state import intent as intent_mod
from ...state import failures as _failures
from ...state import groups as _groups
from ...quality import prune, verify


#: The quota ledger, one per process (its probes are network calls and
#: it caches). Blocks are re-read on the tick cadence, not per spawn.
_quota_ledger = quota.Ledger()

#: Every pipeline that spawns a model, and therefore every seat that can
#: run out of quota independently. `presearch` burns its own cheap model
#: (research_mode_design §0) — a seat even though it is not a
#: decision-maker. (`scholar` retired 2026-08-22: paper fetching became
#: the Strategist's own tool surface.)
_QUOTA_SEATS = ("strategist", "adversary", "formalizer", "presearch",
                "librarian", "paper_index")


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
from ..librarian_sched import (  # noqa: E402 — historical names, tests + runbooks use them
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

    Fix: kill every in-flight agent subprocess (the registry spans every
    provider) via `claude_cli.request_shutdown`. Workers unblock from
    `proc.wait`, return through their dead_attempt cleanup paths (per-thread
    DB conns make this concurrent-safe), and on next retry-loop entry
    see the shutdown event and bail with `daemon_shutdown`. Pool joins
    in seconds; atexit cleanup (gateway terminate, pid_lock unlink)
    runs as designed.
    """
    from ...llm import claude_cli
    killed = claude_cli.request_shutdown()
    if killed:
        print(f"[dispatcher] killed {killed} in-flight agent "
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
from ...state.recovery import recover_at_startup as _recover_at_startup  # noqa: E402,F401
from ...state.recovery import sweep_lean_backups as _sweep_lean_backups  # noqa: E402,F401


# ---------------------------------------------------------------------
# State-transition machine relocated to state/transitions.py (#11 P2).
# Re-exported under the original names so callers / tests that reference
# `dispatcher.<name>` (verify, strategist, the test suite) keep working.
from ...state.transitions import (  # noqa: E402,F401
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




# ─── package facade: the split axes re-exported (B4) ───────────────
# Bodies live in the submodules; this module keeps the head (seats,
# quota ledger, pool helpers, back-compat re-exports) and the
# threshold __getattr__ aliases. noqa: E402 — after the head by design.
from .refill import (  # noqa: E402,F401
    _problem_of_target,
    _verify_problem,
    _dispatch_is_duplicate,
    bfs_refill,
)
from .triggers import (  # noqa: E402,F401
    _ensure_top_groups,
    _enqueue_strategist,
    _strategist_inflight,
    reconcile_stuck_states,
    strategist_triggers,
    _routine_due,
    _warn_consecutive_strategist,
    _strategist_target,
    _derive_strategist_trigger,
    _row_is_stale,
)
from .worker import (  # noqa: E402,F401
    LEAN_QUEUE_KINDS,
    NL_QUEUE_KINDS,
    SPAWN_COOLDOWN_SEC,
    LEASE_TTL_SEC,
    # DAEMON_START_ISO deliberately NOT re-exported: it is run()-
    # rebound mutable state owned by worker.py — a facade copy
    # would freeze at None. Read it as worker.DAEMON_START_ISO.
    _classify_worker_exception,
    WorkerDone,
    FutureMeta,
    CONSEC_SPAWN_FAIL_LIMIT,
    CONSEC_GATEWAY_UNREACHABLE_LIMIT,
    CONSEC_UNCLASSIFIED_LIMIT,
    QUOTA_BACKOFF_BASE_SEC,
    QUOTA_BACKOFF_CAP_SEC,
    SchedulerState,
    _ensure_intent,
    GATEWAY_DOWN_GRACE_SEC,
    _gateway_unreachable_backoff,
    _run_pipeline,
)
from .lock import (  # noqa: E402,F401
    _pid_alive,
    _proc_start_time,
    _cmdline_is_daemon,
    _lock_held_by_live_daemon,
    _acquire_singleton_lock,
    stop_file_path,
    _spawn_handoff_successor,
    scope_mismatch_reason,
)
from .loop import (  # noqa: E402,F401
    run,
)


def __getattr__(name):
    """Read-only aliases of the live thresholds (task #10(d)): historical
    call sites read `dispatcher.BUILDER_THRESHOLD`; the values live in
    `state.thresholds` (tune/monkeypatch THERE — setting an attribute on
    this module would shadow the live value)."""
    if name in ("BUILDER_THRESHOLD", "SHELVE_THRESHOLD"):
        return getattr(thresholds, name)
    raise AttributeError(name)
