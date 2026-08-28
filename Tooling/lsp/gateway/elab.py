"""Elaboration CPU gate — the semaphore that turns concurrent Lean
elaborations into a queue, plus the queue-credit file the provider wall
reads back.

Split out of `gateway.py` 2026-08-29 (A1-1) unchanged. `_ELAB_SEM`,
`_ELAB_BUSY`, `_ELAB_WAITING` and `_ELAB_QUEUE_TIMEOUT_SEC` are read
and rebound HERE, so they are deliberately not re-exported by the
package facade — patch them on this module.
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
import time

from .state import _state


# ─── Elaboration CPU gate (owner call 2026-08-25) ────────────────────
#
# Warm slots are RAM; ELABORATION is CPU. Each elaboration runs one
# core flat-out (Lean is single-threaded per file), so N slots
# elaborating on C cores don't share politely — they thrash: every
# elaboration runs at C/N speed, and everything AROUND them starves
# (codex's fixed 30s MCP handshake, heartbeats, the event loop).
# Measured on the flagship, 2026-08-25: ~93 concurrent formalizer
# sessions drove load to 41 on 8 cores, 50+ spawns died on handshake
# timeouts, and the dispatcher's unclassified breaker halted the
# fleet. The semaphore converts thrash into a queue: same total work,
# each elaboration at full speed, the machine keeps breathing. Idle
# warm slots stay free (measured: 100 warm slots, 0.30 cores) — this
# gates CONCURRENT ELABORATIONS, not the pool.
_ELAB_CONCURRENCY = int(
    os.environ.get("ASTERISM_LEAN_ELAB_CONCURRENCY") or 0) or max(
        2, (os.cpu_count() or 4) - 2)
_ELAB_QUEUE_TIMEOUT_SEC = float(
    os.environ.get("ASTERISM_ELAB_QUEUE_TIMEOUT_SEC") or 600)
_ELAB_SEM = threading.BoundedSemaphore(_ELAB_CONCURRENCY)
_ELAB_CTR_LOCK = threading.Lock()
_ELAB_BUSY = 0
_ELAB_WAITING = 0


#: Upper bound on how long a watcher escorts a runaway elaboration's
#: permit after its caller stopped waiting (see _elab_gate).
_ELAB_ESCORT_BOUND_SEC = float(
    os.environ.get("ASTERISM_ELAB_ESCORT_BOUND_SEC") or 600)


def _release_permit() -> None:
    global _ELAB_BUSY
    with _ELAB_CTR_LOCK:
        _ELAB_BUSY -= 1
    _ELAB_SEM.release()


def _escort_runaway_permit(slot_uri: str) -> None:
    """The caller's wait timed out but the Lean worker is still burning
    a core (`wait_for_diagnostics` only stops WAITING — the worker
    elaborates on, gateway.py's own long-standing note). Releasing the
    permit here would let a fresh elaboration in beside the runaway and
    the busy count would quietly exceed the cap (external review
    2026-08-25). The permit stays held until fileProgress actually
    clears, bounded so a wedged worker cannot strand it forever."""
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < _ELAB_ESCORT_BOUND_SEC:
            backend = _state.backend
            if backend is None:
                break
            try:
                if slot_uri not in backend.busy_uris():
                    break
            except Exception:  # noqa: BLE001 — backend mid-restart
                break
            time.sleep(2.0)
        else:
            print(f"[gateway] elab permit escort gave up after "
                  f"{_ELAB_ESCORT_BOUND_SEC:.0f}s — {slot_uri} still "
                  f"reports busy; releasing anyway (recycle policy owns "
                  f"the runaway)", file=sys.stderr, flush=True)
    finally:
        _release_permit()


#: Queue-credit file, written into a pipeline's attempts dir: the
#: cumulative seconds its tool calls spent WAITING at this gate. The
#: provider wall reads it and extends by the same amount (capped) —
#: queue time is machine congestion, not the agent's (owner design
#: 2026-08-26; agent_timeout ×223 in the 08-25 crush were sessions
#: burning their wall in exactly these queues).
ELAB_CREDIT_FILENAME = "_elab_queue_credit"
_ELAB_CREDIT_LOCK = threading.Lock()


def _record_queue_credit(meta, waited_sec: float) -> None:
    if meta is None or waited_sec < 0.05:
        return
    try:
        d = meta.target_path.parent
        if ".attempts" not in d.parts:
            return  # verify probes point at proofs/ — no wall, no file
        p = d / ELAB_CREDIT_FILENAME
        with _ELAB_CREDIT_LOCK:
            try:
                cur = float(p.read_text(encoding="utf-8").strip() or 0)
            except (OSError, ValueError):
                cur = 0.0
            p.write_text(f"{cur + waited_sec:.1f}", encoding="utf-8")
    except Exception:  # noqa: BLE001 — credit is best-effort
        pass


@contextlib.contextmanager
def _elab_gate(slot_uri: "str | None" = None, meta=None):
    """Hold one elaboration ticket for the did_change→wait critical
    section. Acquire AFTER the slot lock (never while queuing for a
    slot — head-of-line blocking), release when the elaboration is
    actually done: if the caller's wait timed out while Lean still
    reports the slot busy, a watcher escorts the permit until
    fileProgress clears. A saturated queue past the timeout fails LOUD
    with a retryable message instead of burning the caller's wall.
    Time spent queuing is credited back to the session's wall via
    `_record_queue_credit`."""
    global _ELAB_BUSY, _ELAB_WAITING
    with _ELAB_CTR_LOCK:
        _ELAB_WAITING += 1
    _q0 = time.monotonic()
    try:
        ok = _ELAB_SEM.acquire(timeout=_ELAB_QUEUE_TIMEOUT_SEC)
    finally:
        with _ELAB_CTR_LOCK:
            _ELAB_WAITING -= 1
        _record_queue_credit(meta, time.monotonic() - _q0)
    if not ok:
        raise RuntimeError(
            f"Lean elaboration queue saturated "
            f"({_ELAB_CONCURRENCY} concurrent, waited "
            f"{_ELAB_QUEUE_TIMEOUT_SEC:.0f}s) — the machine is over "
            f"capacity, not your file. Retry this call; if it repeats, "
            f"report it as framework feedback.")
    with _ELAB_CTR_LOCK:
        _ELAB_BUSY += 1
    try:
        yield
    finally:
        still_busy = False
        if slot_uri is not None:
            backend = _state.backend
            try:
                still_busy = (backend is not None
                              and slot_uri in backend.busy_uris())
            except Exception:  # noqa: BLE001
                still_busy = False
        if still_busy:
            threading.Thread(target=_escort_runaway_permit,
                             args=(slot_uri,), daemon=True).start()
        else:
            _release_permit()


def elab_gate_stats() -> "dict":
    with _ELAB_CTR_LOCK:
        return {"elab_cap": _ELAB_CONCURRENCY, "elab_busy": _ELAB_BUSY,
                "elab_waiting": _ELAB_WAITING}
