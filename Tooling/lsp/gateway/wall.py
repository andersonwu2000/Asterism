"""The elaboration wall — compute to completion, then a verdict.

Owner design 2026-08-29: the old 120s early return handed the agent
"elaborating, 0 diagnostics" to misread as clean while the worker kept
the slot busy for the next call (~150 worker reports + 36 asking for a
cancel key, union_closed ring 2026-08-29). Past the wall the worker is
killed, its slot re-warmed in place, and the tool answers a hard
failure. A file that bought a large heartbeat budget through
`_heartbeat_gate` gets the heavy wall: 11 proved bricks in this
workspace needed ~240s checks at 4M.

Two meters, one loop (owner rulings 2026-08-29 / 2026-08-30):

* CPU — the WORKER'S CPU SECONDS, not wall-clock: on the 4-OCPU
  flagship, 2 elaboration lanes shared with 9 codex CLIs stretched a 60s
  elaboration past a 300s wall-clock wall and killed work that was
  converging. "Compute to completion" means the worker got its budget of
  compute; a merely crowded machine does not fail a proof. A loose
  wall-clock cap (×factor) still catches a worker that never runs; with
  no worker to meter (frozen slot, tests) the wall falls back to
  wall-clock. Client-side MCP timeouts sit above the clock cap.
* RAM — the worker's private-memory GROWTH WITHIN THIS ONE ELABORATION,
  never its absolute size. A worker that is fat because it grew slowly
  across earlier calls is the mid-lease rewarm's business (re-warmed and
  handed back, `governor._maybe_kick_midlease_rewarm`); only a single
  elaboration that inflates the worker past its allowance is walled, and
  the agent is told that computing harder will not pass. The allowance is
  derived from the machine (ledger budget / warm target × factor), not a
  pinned number of gigabytes.

Content that hit the wall is refused on resend before any elaboration
(`_walled_gate`): one session hit the CPU wall four times on the same
file, 2026-08-29. A worker crash carries the Lean server's stderr tail
so the cause is evidence, not a guess.
"""
from __future__ import annotations

import contextlib
import hashlib
import sys
import time

from .state import SessionMetadata, _state

ELAB_WALL_SEC = 300.0
ELAB_WALL_HEAVY_SEC = 900.0
#: Poll slice — how often the meters are read between waits.
ELAB_WALL_SLICE_SEC = 15.0
#: Wall-clock safety net as a multiple of the CPU budget.
ELAB_WALL_CLOCK_FACTOR = 4.0
#: Per-elaboration RAM allowance = (ledger budget / warm target) × this.
#: Three slots' worth of growth in one call is pathological on any
#: machine the ledger sized; the factor is machine-independent.
ELAB_RAM_WALL_FACTOR = 3.0


def _elab_wall_for(meta: SessionMetadata) -> float:
    from .rpc import _HB_ASK_ABOVE, _hb_rank  # lazy: rpc imports this module
    return (ELAB_WALL_HEAVY_SEC
            if _hb_rank(meta.hb_limit) > _HB_ASK_ABOVE else ELAB_WALL_SEC)


def _ram_wall_bytes() -> "int | None":
    """The per-elaboration RAM growth allowance in bytes, or None when
    the ledger has no budget (RAM meter off)."""
    budget = getattr(_state, "ram_budget_gb", None)
    if not budget:
        return None
    target = max(1, int(getattr(_state, "warm_target", 0) or 1))
    return int(budget / target * ELAB_RAM_WALL_FACTOR * 1024 ** 3)


def _worker_meter(slot_uri: str) -> "tuple[int, float, int] | None":
    """(pid, user+system CPU seconds, private bytes) of the ONE
    `lean --worker` serving `slot_uri` (the same exact argv match the
    governor kills by), or None when no such worker exists (frozen
    slot, backend not ours, the server between killing a worker and
    respawning it). The pid travels with the reading because the lean
    server REPLACES the worker on a header change: a new pid starts its
    clocks at zero and the old baselines must not be subtracted."""
    try:
        import os as _os
        import psutil
        me = psutil.Process(_os.getpid())
        for proc in me.children(recursive=True):
            try:
                argv = proc.cmdline()
                if "--worker" in argv and slot_uri in argv:
                    t = proc.cpu_times()
                    mem = proc.memory_info()
                    priv = getattr(mem, "private", None)
                    if priv is None:
                        try:
                            priv = proc.memory_full_info().uss
                        except (psutil.Error, OSError):
                            priv = mem.rss
                    return int(proc.pid), float(t.user + t.system), int(priv)
            except (psutil.Error, OSError):
                continue
    except Exception:  # noqa: BLE001 — meter unavailable → clock mode
        return None
    return None


def _reclaim_slot(backend, slot) -> bool:
    """Kill the slot's worker mid-elaboration (if one exists) and re-warm
    the slot in place — the caller holds the slot lock (the wedge
    recycler's close/re-open flow, in production since 2026-08-14). The
    session re-swaps its content on its next call: one cold
    elaboration, paid by the one session that overran, nobody else
    loses a claim. Returns whether the slot is back on warmup — a frozen
    slot has no worker to kill and still reclaims fine."""
    from .governor import _kill_worker_for_uri  # lazy: no import cycle
    from .state import WARMUP_CONTENT
    _kill_worker_for_uri(slot.slot_uri)
    try:
        with contextlib.suppress(Exception):
            backend.did_close(slot.slot_path)
        backend.did_open(slot.slot_path, WARMUP_CONTENT)
        slot.file_version = 1
        with contextlib.suppress(Exception):
            backend.wait_for_file_done(slot.slot_uri, timeout=120)
    except Exception as exc:  # noqa: BLE001 — reported, never raised
        print(f"[gateway] slot {getattr(slot, 'slot_id', '?')} re-warm after "
              f"the wall FAILED ({type(exc).__name__}: {exc})",
              file=sys.stderr, flush=True)
        return False
    slot.content_pipeline_id = None
    slot.line_map = None
    return True


def _content_key(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _walled_gate(meta: SessionMetadata, content: str) -> "str | None":
    """Refuse content that already hit the wall in this session, before
    any elaboration. A changed file gets its elaboration."""
    if _content_key(content) not in getattr(meta, "walled", ()):
        return None
    return ("This exact file already hit the elaboration wall in this "
            "session — resending it will not pass; the machine does not "
            "have the compute or memory for it as written. Change the "
            "proof: split the finite case into smaller bricks, bound the "
            "quantity instead of evaluating it, lift the heavy step into "
            "its own `new_<slug>.lean` with a small context and cite it — "
            "or return the goal to NL (decline with this reason) so the "
            "Strategist can re-plan it.")


def _teaching(reason: str, wall: float, mode: str, *, ram: bool) -> str:
    what = (f"grew the Lean worker past its RAM allowance ({reason})"
            if ram else
            f"did not finish within its budget of {wall:.0f} "
            f"{'CPU-seconds' if mode == 'cpu' else 'seconds'} ({reason})")
    return (f"Lean {what}; the worker was killed and its slot re-warmed, so "
            "this result is a FAILURE, not 'no news yet'. It will not pass "
            "by computing harder: split the finite case into smaller "
            "bricks, bound the quantity instead of evaluating it, lift the "
            "heavy step into its own `new_<slug>.lean` with a small context "
            "and cite it — or return the goal to NL (decline with this "
            "reason). Your file content is kept; the next call "
            "re-elaborates it cold, and this exact content is refused on "
            "resend.")


def _await_elaboration(backend, slot, meta, content: "str | None" = None,
                       ) -> "tuple[bool, dict | None]":
    """Block until the slot's file is fully elaborated, or hit the wall.
    Returns `(True, None)` on convergence; on the wall the worker is
    killed and the slot re-warmed, and `(False, info)` carries the
    verdict the caller MUST surface as a hard failure with no
    diagnostic count (an empty list here is not "clean", it is a
    failure)."""
    wall = _elab_wall_for(meta)
    clock_cap = wall * ELAB_WALL_CLOCK_FACTOR
    ram_wall = _ram_wall_bytes()
    t0 = time.monotonic()
    first = _worker_meter(slot.slot_uri)
    mode = "cpu" if first is not None else "clock"
    base_pid, base_cpu, base_priv = first if first is not None else (0, 0.0, 0)
    used = 0.0
    growth = 0
    gone = 0
    reason = ""
    ram_hit = False
    crash_tail = None
    while True:
        elapsed = time.monotonic() - t0
        if mode == "cpu":
            slice_s = min(ELAB_WALL_SLICE_SEC, max(0.01, clock_cap - elapsed))
        else:
            slice_s = min(ELAB_WALL_SLICE_SEC, max(0.01, wall - elapsed))
        t_slice = time.monotonic()
        try:
            backend.wait_for_diagnostics(slot.slot_uri, slot.file_version,
                                         timeout=slice_s)
            return True, None
        except TimeoutError:
            # the loop paces ITSELF at one meter read per slice — a
            # backend that gives up early (a fake, a wedge) must not
            # turn the wait into a busy-loop
            spent = time.monotonic() - t_slice
            if spent < slice_s:
                time.sleep(slice_s - spent)
        except RuntimeError as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if "crash" in str(exc).lower() and hasattr(backend, "stderr_tail"):
                with contextlib.suppress(Exception):
                    crash_tail = backend.stderr_tail()
            break
        elapsed = time.monotonic() - t0
        if mode == "cpu":
            reading = _worker_meter(slot.slot_uri)
            if reading is None:
                # no worker right now: the server may be respawning it
                # (header change) — two slices of grace, then it is gone
                # for good (wedge kill, freeze) and there is nothing
                # left to meter
                gone += 1
                if gone >= 2:
                    reason = "worker gone"
                    break
                continue
            gone = 0
            pid, cpu, priv = reading
            if pid != base_pid:
                # a replacement worker: its clocks started at zero on
                # this very elaboration, so its whole CPU time counts
                # and its first reading is the RAM baseline
                base_pid, base_cpu, base_priv = pid, 0.0, priv
            used = max(used, cpu - base_cpu)
            growth = max(growth, priv - base_priv)
            if used >= wall:
                reason = f"{used:.0f} CPU-seconds consumed"
                break
            if ram_wall is not None and growth >= ram_wall:
                reason = (f"grew {growth // (1024 * 1024)} MB in this "
                          f"elaboration; RAM allowance "
                          f"{ram_wall // (1024 * 1024)} MB")
                ram_hit = True
                break
            if elapsed >= clock_cap:
                reason = (f"{elapsed:.0f}s wall-clock with only "
                          f"{used:.0f} CPU-seconds — starved or hung")
                break
        elif elapsed >= wall:
            reason = f"{elapsed:.0f}s wall-clock (no CPU meter)"
            break
    rewarmed = _reclaim_slot(backend, slot)
    if content is not None:
        with contextlib.suppress(AttributeError):
            meta.walled.add(_content_key(content))
    print(f"[gateway] elaboration wall hit on slot "
          f"{getattr(slot, 'slot_id', '?')} ({reason}; budget {wall:.0f}"
          f"{' CPU-s' if mode == 'cpu' else 's'}"
          f"{', RAM ' + str(ram_wall // (1024 * 1024)) + ' MB' if ram_wall else ''}) — slot "
          f"{'re-warmed' if rewarmed else 'NOT re-warmed'}"
          + (f"\n[gateway] worker stderr tail:\n{crash_tail[-1500:]}"
             if crash_tail else ""),
          file=sys.stderr, flush=True)
    info = {
        "wall_s": wall,
        "mode": mode,
        "cpu_s": round(used, 1),
        "ram_growth_mb": growth // (1024 * 1024),
        "elapsed_s": round(time.monotonic() - t0, 1),
        "reason": reason,
        "worker_reclaimed": rewarmed,
        "teaching": _teaching(reason, wall, mode, ram=ram_hit),
    }
    if crash_tail:
        info["crash_tail"] = crash_tail[-1500:]
    return False, info
