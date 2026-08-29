"""Backend + worker pool lifecycle — start the pool, wait it out, and
tree-kill/re-warm a wedged one.

Split out of `gateway.py` 2026-08-29 (A1-1) unchanged. `_await_backend`
is consumed only by the two readiness functions in this module, so it
is deliberately not re-exported by the package facade — patch it here.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from ..client import LspClient
from .state import WARMUP_CONTENT, WorkerSlot, _state


# ─── Backend + worker pool lifecycle ──────────────────────

def _start_workers(workspace: Path, w_count: int,
                   n_interactive: int = 0) -> None:
    """Pre-warm `w_count` workers at gateway startup. Each worker is a
    didOpen on a distinct slot URI (`_gateway_slot_<i>.lean`) with
    `import Mathlib\\n` content. Lean elaborates Mathlib once per
    worker (parallel by Lean's worker model, serial-waited by us);
    after this, each slot can serve any pipeline's content via
    didChange in ~3-4s instead of paying the ~27s fresh-worker cost.

    Sets `_state.ready_event` regardless of outcome — error captured
    in `_state.init_error`. Daemon's gateway_lifecycle.start_gateway
    polls /health and refuses to dispatch if init failed."""
    try:
        t0 = time.perf_counter()
        client = LspClient(workspace)
        client.start()
        client.initialize(timeout=60)
        _state.backend = client
        _state.workspace = workspace

        # Slot files are framework runtime artifacts (per-worker warmup
        # surface for didOpen). Kept under `.asterism/runtime_slots/` so
        # they don't pollute the workspace root and don't get glob'd by
        # lake's `lean_lib` Asterism/Problems/Library blocks. The
        # workspace root remains the cwd for lake serve, so import
        # resolution is unaffected — file location only matters for the
        # URI, not for Lean's LEAN_PATH.
        slots_dir = workspace / ".asterism" / "runtime_slots"
        slots_dir.mkdir(parents=True, exist_ok=True)
        slots: list[WorkerSlot] = []
        for i in range(w_count + n_interactive):
            slot_path = slots_dir / f"_gateway_slot_{i}.lean"
            slot_path.write_text(WARMUP_CONTENT, encoding="utf-8")
            slot = WorkerSlot(
                slot_id=i,
                slot_path=slot_path,
                slot_uri=slot_path.as_uri(),
                # trailing slots are the serve UI's interactive pool
                reserved=(i >= w_count),
            )
            client.did_open(slot_path, WARMUP_CONTENT)
            slots.append(slot)

        # Lean processes didOpens in parallel across worker processes
        # (one per slot); we serial-wait each one's elaborate done.
        # The fileProgress=[] signal means "this file's elaborate
        # finished" — sufficient for "the worker is warm". We do NOT
        # also wait_for_diagnostics_settled here because for plain
        # `import Mathlib` Lean keeps emitting incremental info
        # publishDiagnostics as transitive modules load, which on
        # multi-worker machines (CPU contention) can trickle for many
        # minutes and never reach 3s-stable. fileProgress is the
        # canonical "elaborate done" signal at this layer; per-tool
        # operations (apply_edit / validate_file / verify) still
        # use wait_for_diagnostics_settled for their POST-edit reads
        # because at that point the file is small and diagnostics
        # converge fast.
        for slot in slots:
            t_slot = time.perf_counter()
            try:
                client.wait_for_file_done(slot.slot_uri, timeout=300)
                print(f"[gateway] slot {slot.slot_id} warmed in "
                      f"{time.perf_counter() - t_slot:.1f}s",
                      file=sys.stderr, flush=True)
            except TimeoutError:
                # NOT warm — say so (the old print reported the timeout
                # as 'warmed in 300.0s', which read as success in jtyy's
                # triage). The slot stays in the pool; its first tool
                # call waits out the remaining elaboration.
                print(f"[gateway] slot {slot.slot_id} warm TIMEOUT "
                      f"after {time.perf_counter() - t_slot:.1f}s — "
                      f"continuing; still elaborating in background "
                      f"(machine under-spec for this pool size?)",
                      file=sys.stderr, flush=True)

        _state.workers = slots
        elapsed = time.perf_counter() - t0
        print(f"[gateway] {w_count} workers warmed in {elapsed:.1f}s",
              file=sys.stderr, flush=True)
    except Exception as e:
        _state.init_error = f"{type(e).__name__}: {e}"
        print(f"[gateway] worker pool init failed: {_state.init_error}",
              file=sys.stderr, flush=True)
    finally:
        _state.ready_event.set()


#: What every Lean surface says while the pool has never been up. Not
#: a bare "unavailable": this state ends by itself, and the caller's
#: right move is to wait rather than to conclude damage.
WARMING_MSG = (
    "the Lean worker pool is still warming (first start of this gateway "
    "— minutes, not seconds). This is the framework starting up, not a "
    "problem with the request: Lean-side work is queued until it "
    "finishes, while `compute` and the other non-Lean tools work now.")


def _await_backend(timeout: float) -> "str | None":
    """The blocking primitive: wait out an init/re-init and report."""
    if not _state.ready_event.wait(timeout=timeout):
        return f"backend not ready after {timeout}s"
    if _state.backend is None or not _state.workers:
        return _state.init_error or "backend init failed"
    return None


def _ensure_backend_ready(timeout: float = 240.0) -> str | None:
    """Every Lean surface's readiness gate. None on success, else the
    reason — and during the FIRST warm the reason arrives instantly.

    HTTP now opens before that warm (2026-08-12) so the NL layer, which
    the dispatcher deliberately runs in exactly that window, can reach
    `compute`. That also makes every Lean surface reachable minutes
    before it can work, and the old answer was to BLOCK up to 240s. On
    `/verify` and `/verify_session` — async routes calling this
    straight from the event loop — one stray Lean POST would then wedge
    the very endpoint the change exists to serve. A hang is worse than
    the refusal it replaces, which was at least instant.

    The fast no is gated on `first_warm_done`, NOT on
    `ready_event.is_set()`: the wedge watchdog clears that event to
    swap a hung backend, and a caller waiting through THAT is right to
    wait — its work is real and in flight. Only the first warm, when by
    construction no Lean work exists yet, gets the instant answer."""
    if not _state.first_warm_done:
        return WARMING_MSG
    return _await_backend(timeout)


def _watch_initial_warm(budget: float, marker: "Path") -> None:
    """Wait out the first warm on a thread, so HTTP can serve during it.

    Runs beside the serving loop, never on it. Opens the Lean surfaces
    when the pool is up, and keeps a failed warm exactly as fatal as it
    was when `main` blocked here and called `sys.exit(3)`."""
    err = _await_backend(budget)
    if err:
        # The only way a thread can end this process without cutting
        # ahead of `main`'s finally — which reaps the Lean subtree.
        print(f"[gateway] FATAL: {err}", file=sys.stderr, flush=True)
        _state.warm_failed = err
        srv = _state.http_server
        if srv is not None:
            srv.should_exit = True              # type: ignore[attr-defined]
        return
    _state.first_warm_done = True
    print("[gateway] worker pool warm — Lean surfaces now open",
          file=sys.stderr, flush=True)
    # The marker's job ends only HERE, not when HTTP opened. `/health`
    # answers 503 for the whole warm, so `_ping_health` sees nothing
    # and this file stays the presence signal — and
    # `_wait_for_starting_gateway` reads its disappearance as "that
    # gateway is up". Removing it at HTTP-open would tell a second
    # daemon to spawn a rival into an occupied port.
    marker.unlink(missing_ok=True)


# ─── Wedge recovery (2026-06-12 gateway-hang fix) ─────────
# A non-terminating Lean elaborate (runaway typeclass search / loop)
# pins a worker forever: `wait_for_diagnostics` only stops *waiting*
# (the 120s/300s timeout returns stale), but the worker keeps burning
# the slot. With one shared backend that eventually starves every slot
# and the dispatcher freezes (observed: a ~2h hang). The watchdog spots
# a slot stuck in-flight past `_BACKEND_WEDGE_SEC` and replaces the
# backend; `LspClient.shutdown` now tree-kills lake serve's whole
# `lean --server`/`--worker` subtree so the runaway is actually reaped.

_BACKEND_WEDGE_SEC = 1200.0  # > rpc.ELAB_WALL_HEAVY_SEC (900): the per-op wall reclaims first
_restart_lock = threading.Lock()


def _restart_backend(reason: str) -> None:
    """Tree-kill the wedged backend and re-warm a fresh worker pool.
    Sessions lose their slot claims (fresh slots are unowned) — their
    next tool call re-claims or gets a clear error → spawn retry. A
    last-resort recovery, far cheaper than an indefinite hang."""
    if not _restart_lock.acquire(blocking=False):
        return
    try:
        old = _state.backend
        ws = _state.workspace
        if ws is None:
            return
        n_res = sum(1 for s in _state.workers
                    if getattr(s, "reserved", False))
        # OPEN slots only — the roster remembers every slot the ledger
        # ever warmed, and re-warming the closed ones here would
        # resurrect a field the target shrank (external review
        # 2026-08-25; the converger regrows toward the live target if
        # it is higher).
        n = sum(1 for s in _state.workers
                if not getattr(s, "reserved", False)
                and not getattr(s, "closed", False)) or 1
        print(f"[gateway] backend restart — {reason} "
              f"({n}+{n_res} slots)",
              file=sys.stderr, flush=True)
        _state.ready_event.clear()
        if old is not None:
            try:
                old.shutdown()
            except Exception:
                try:
                    old._kill_tree()
                except Exception:
                    pass
        _start_workers(ws, n, n_res)
    finally:
        _restart_lock.release()
