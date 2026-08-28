"""The governor's measuring tape — per-slot PRIVATE bytes (plus page
tables), raw and TTL-cached.

Split out of `gateway.py` 2026-08-29 (A1-1) unchanged. `_SLOT_MB_CACHE`
is mutated in place and never rebound, so the facade re-export and this
module's own binding are the same dict.
"""
from __future__ import annotations

import os
import threading
import time

from .state import _state


def _vm_pte_bytes(pid: int) -> int:
    """VmPTE of one process, in bytes (0 where /proc is absent)."""
    try:
        with open(f"/proc/{pid}/status", "rb") as fh:
            for ln in fh:
                if ln.startswith(b"VmPTE:"):
                    return int(ln.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _slot_private_mb() -> "dict[int, int | None]":
    """slot_id -> the worker's PRIVATE bytes, in MB. None = not measured.

    The mapping is free and exact: Lean runs one worker per open
    document and puts the document's URI on its own command line
    (`lean-asterism-server --worker file:///…/_gateway_slot_3.lean`),
    so nothing here depends on process order or on counting.

    PRIVATE, never RSS. The mathlib olean region is mmap'd shared across
    every worker, and working-set counts it once per process: measured
    2026-08-14, five workers reported 17.93 GB of working set against
    5.38 GB private, on a box with 11.5 GB actually in use. An earlier
    pass at this investigation reported a 20 GB phantom for exactly that
    reason.

    Never raises and never blocks: `/health` is a liveness probe, and a
    reader that cannot tell "the gateway is dead" from "psutil hiccuped"
    is worse than no reading at all. A slot that cannot be measured
    reports None — which is not zero.
    """
    out: "dict[int, int | None]" = {s.slot_id: None for s in _state.workers}
    try:
        import psutil
        by_uri: "dict[str, int]" = {}
        me = psutil.Process(os.getpid())
        for proc in me.children(recursive=True):
            try:
                argv = proc.cmdline()
            except (psutil.Error, OSError):
                continue
            if "--worker" not in argv:
                continue
            uri = next((a for a in argv if a.startswith("file://")), None)
            if uri is None:
                continue
            try:
                mem = proc.memory_info()
            except (psutil.Error, OSError):
                continue
            # `private` is Windows-only; elsewhere USS is the same
            # question ("pages this process alone would free").
            priv = getattr(mem, "private", None)
            if priv is None:
                try:
                    priv = proc.memory_full_info().uss
                except (psutil.Error, OSError):
                    continue
            # Page tables are per-worker weight the heap numbers miss:
            # Lean's sparse mappings cost ~180 MB of VmPTE per worker
            # (census 2026-08-26: 13.3 GB across 77 workers — the
            # fleet's second-largest tenant). They die with the worker,
            # so both the recycle threshold and the ledger's slot price
            # honestly include them. /proc is Linux-only; Windows
            # reports heap alone as before.
            by_uri[uri] = int(priv) + _vm_pte_bytes(proc.pid)
        for slot in _state.workers:
            hit = by_uri.get(slot.slot_uri)
            if hit is not None:
                out[slot.slot_id] = hit // (1024 * 1024)
    except Exception:  # noqa: BLE001 — health must answer regardless
        pass
    return out


#: /health used to run the smaps scan INLINE on the event loop: on
#: Linux `memory_full_info` walks /proc/<pid>/smaps_rollup, and a pool
#: of 2 GB Lean workers turns one call into seconds — the daemon's 1s
#: ready-poll then times out, retries, and the loop never drains its
#: own backlog (gateway pegged at 96% CPU, /health dark, dispatch
#: frozen 25 minutes; Oracle boarding, 2026-08-24 — Windows psutil is
#: cheap, which is why the home fleet never saw it). Health reads a
#: cache a throwaway thread refreshes at most once per TTL; the event
#: loop never pays for the scan. The recycle path keeps the raw call —
#: it runs on worker threads and needs a fresh number.
_SLOT_MB_TTL = 20.0
_SLOT_MB_CACHE: "dict" = {"at": 0.0, "val": {}, "refreshing": False}
_SLOT_MB_LOCK = threading.Lock()


def _slot_private_mb_cached() -> "dict[int, int | None]":
    now = time.monotonic()
    with _SLOT_MB_LOCK:
        if (now - _SLOT_MB_CACHE["at"] < _SLOT_MB_TTL
                or _SLOT_MB_CACHE["refreshing"]):
            return dict(_SLOT_MB_CACHE["val"])
        _SLOT_MB_CACHE["refreshing"] = True

    def _refresh() -> None:
        try:
            val = _slot_private_mb()
        except Exception:  # noqa: BLE001 — health must answer regardless
            val = {}
        with _SLOT_MB_LOCK:
            _SLOT_MB_CACHE["val"] = val
            _SLOT_MB_CACHE["at"] = time.monotonic()
            _SLOT_MB_CACHE["refreshing"] = False

    threading.Thread(target=_refresh, name="slot-mb-refresh",
                     daemon=True).start()
    with _SLOT_MB_LOCK:
        return dict(_SLOT_MB_CACHE["val"])
