"""The /health payload, and the snapshot the governor keeps warm.

Split out of `gateway.py` 2026-08-29 (A1-3) unchanged: the pool walk
that builds the payload, the snapshot that caches it, and the
governor-thread refresh that rebuilds it every pass. The `/health` route
itself stays in the package `__init__` with the rest of the HTTP surface
and reads these names through the facade.

Naming: the `/health` route handler is `health_route`, renamed away from
the bare `health` that used to shadow this module on the package
namespace (a `monkeypatch.setattr(gateway.health, ...)` would have set
an attribute on a coroutine function and patched nothing). Patch these
names on the facade, which is where `/health`'s own consumer resolves
them. Nothing
here is rebound after import — `_HEALTH_SNAPSHOT` is mutated in place,
never replaced — so the facade's binding cannot go stale.
"""
from __future__ import annotations

import os
import threading
import time

from .elab import elab_gate_stats
from .governor import _pressure_debt
from .state import _CODE_FINGERPRINT, _state
from .weigh import _slot_private_mb_cached


def _health_payload() -> dict:
    backend_ok = _state.backend is not None and bool(_state.workers)
    with _state.sessions_lock:
        n_sessions = len(_state.sessions)
    # workers_total counts the PIPELINE pool only — the daemon's reuse
    # gate compares it against dispatch.pool; reserved interactive
    # slots report separately.
    n_workers = sum(1 for s in _state.workers if not s.reserved)
    n_open = sum(1 for s in _state.workers
                 if not s.reserved and not s.closed)
    n_interactive = sum(1 for s in _state.workers if s.reserved)
    n_busy = sum(1 for s in _state.workers if s.lock.locked())
    n_frozen = sum(1 for s in _state.workers if s.frozen)
    # claimable slots — same predicate as /warm_target's `free`; the
    # daemon-status `slots` field reads it here (frontend, 2026-08-25)
    n_free = sum(1 for s in _state.workers
                 if not s.reserved and not s.closed
                 and s.claimed_by is None)
    with _state.counters_lock:
        counters = {
            "n_hot": _state.n_hot,
            "n_cold_warmup": _state.n_cold_warmup,
            "n_cold_noswap": _state.n_cold_noswap,
            "n_busy_polls": _state.n_busy_polls,
        }
    total_acq = (counters["n_hot"] + counters["n_cold_warmup"]
                 + counters["n_cold_noswap"])
    counters["hot_rate"] = (
        counters["n_hot"] / total_acq if total_acq else None
    )
    return {
        "backend_ready": backend_ok,
        "workers_total": n_workers,
        # The pre-RAM-clamp dispatch.pool this process launched under —
        # the daemon's reuse gate compares its yaml against THIS (a
        # clamped effective pool is a healthy state, not drift).
        "workers_configured": (_state.workers_configured
                               if _state.workers_configured is not None
                               else n_workers),
        "workers_interactive": n_interactive,
        "workers_busy": n_busy,
        "workers_frozen": n_frozen,
        # RAM-ledger surface (owner design 2026-08-25): open = slots
        # with a live worker (closed ones freed their RAM); target =
        # what the dispatcher's ledger last asked for (None = static
        # mode). The cockpit reads WHICH AXIS binds from these.
        "workers_open": n_open,
        "workers_free": n_free,
        "warm_target": _state.warm_target,
        # The serialized outlet's open kills: effective allowance =
        # warm_target - this (0 = no pressure episode in flight).
        "pressure_debt": _pressure_debt(),
        **elab_gate_stats(),
        "sessions_active": n_sessions,
        "init_error": _state.init_error,
        "acquires": counters,
        # Per-slot PRIVATE bytes (MB), the reading the recycle policy
        # runs on. Until 2026-08-14 slot memory was on no surface at
        # all: a 2.7 GB slot against a 0.67 GB baseline was found by
        # hand-walking the process table, and could only be found that
        # way. None = could not measure this slot.
        "slot_private_mb": _slot_private_mb_cached(),
        # PID so a reusing daemon can detect a stale worker-count (≠
        # dispatch.pool) and kill+relaunch this gateway to match the yaml.
        "pid": os.getpid(),
        # Source fingerprint at THIS process's start — the reuse gate
        # relaunches on drift (version-skew guard).
        "code_fingerprint": _CODE_FINGERPRINT,
    }


#: /health snapshot, rebuilt by the governor thread every pass. The
#: payload walk is cheap, but under a saturated accept queue every
#: cycle the event loop does NOT spend is a cycle it can spend
#: accepting — and the double-fetching status pollers were feeding the
#: very backlog they measured (frontend finding, 2026-08-27).
_HEALTH_SNAPSHOT_LOCK = threading.Lock()
_HEALTH_SNAPSHOT: "dict" = {"at": 0.0, "val": None}


def _refresh_health_snapshot() -> None:
    if not _state.first_warm_done:
        return
    val = _health_payload()
    with _HEALTH_SNAPSHOT_LOCK:
        _HEALTH_SNAPSHOT["val"] = val
        _HEALTH_SNAPSHOT["at"] = time.monotonic()
