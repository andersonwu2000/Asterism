"""LSP Gateway — long-living HTTP MCP server with shared worker pool.

Phase 2: 1 server + W persistent workers + content swap on tool call.
N pipelines compete for W workers via tool-call-level LRU (not pipeline
hold). See `docs/archive/lsp_gateway.md` for design rationale.

Lifecycle:
  1. Daemon startup: launch this module as subprocess.
     `main()` starts ONE lake serve, then didOpens W slot files
     (`_gateway_slot_0.lean` ... `_gateway_slot_{W-1}.lean`) each with
     `import Mathlib\n` warmup. Each slot's worker pre-warms Mathlib
     namespace state so subsequent didChange swaps complete in ~3-4s.
  2. Per-spawn: framework POSTs /register with {pipeline_id,
     target_path, problem, workspace}. Gateway reads target_path off
     disk into an in-memory mirror, returns session_token. NO didOpen
     yet — that happens lazily at first tool call.
  3. Tool call: gateway resolves session via X-Asterism-Session header,
     borrows a slot (preferring one already loaded with this pipeline's
     content; LRU-evicts otherwise), didChange if needed, runs the LSP
     op against that slot's URI.
  4. Spawn end: framework POSTs /release/{token}. Gateway drops session
     metadata. Slot content stays loaded — next tool call from another
     pipeline will swap-in.

Wire format (MCP):
  POST http://127.0.0.1:8765/mcp
  Header: X-Asterism-Session: <token>
  Body:   JSON-RPC over streamable-http (FastMCP)

Wire format (REST):
  POST /register      JSON body {pipeline_id, target_path, problem,
                                 workspace, log_path?}
  POST /release/{tok} no body
  GET  /health        worker pool status + active session count
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import functools
import hashlib
import json
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import edits as _edits
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..state import assemble, db, metaprog, transitions
from ..state import intent as intent_mod
from .client import LspClient


# ─── Worker slot ────────────────────────────────────────────────

WARMUP_CONTENT = "import Mathlib\n"


@dataclass
class WorkerSlot:
    """One persistent lean --worker holding a slot URI. Pre-warmed at
    startup with `import Mathlib`; subsequent loads are didChange swaps
    on this URI (~3-4s vs ~27s fresh worker).

    1:1 lifecycle (#118): each spawn claims one slot at register_session
    and holds it until release_session. `claimed_by` tracks ownership;
    `content_pipeline_id` tracks which pipeline's content is actually
    didChanged in (may lag `claimed_by` until the first tool call).
    """
    slot_id: int
    slot_path: Path
    slot_uri: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Lifetime ownership. None = available for claim. Set at
    # register_session, cleared at release_session.
    claimed_by: str | None = None
    # Reserved for the serve UI's interactive editor (owner's
    # pipeline=slot identity, both directions): pipeline claims skip
    # reserved slots, interactive claims take ONLY reserved slots, and
    # borrow probes never touch them.
    reserved: bool = False
    # Whose content is currently didChanged in this slot. May lag
    # `claimed_by` until the first tool call (warmup state has neither
    # set). Stale after release — next claim's first tool call rewrites.
    content_pipeline_id: str | None = None
    # Monotonic version for LSP didChange. Starts at 2 (didOpen was 1).
    file_version: int = 2
    # Wall-clock time of last release, kept for diagnostics.
    last_used_ts: float = 0.0
    # line_map of the compilation unit currently didChanged in (merged
    # line → session-content line, None for framework-prefix / sibling
    # region). Set whenever content is swapped in; tools translate their
    # positions / diagnostics through it. None until the first swap.
    line_map: "list[int | None] | None" = None
    # RAM-ledger lifecycle (2026-08-25): a closed slot keeps its roster
    # entry but has no live worker (did_close freed its RAM) and is
    # skipped by every claim. The warm-target converger re-opens it —
    # or extends the roster — when the target rises.
    closed: bool = False


# ─── Session metadata ────────────────────────────────────────

@dataclass
class SessionMetadata:
    """Per-pipeline state held in gateway. file_content is the mirror
    of the agent's accumulated edits; slot URIs are transient stages
    we push this content onto for elaboration. target_path is the
    real on-disk goal_lean — write-through ensures the framework's
    post-spawn cascade reads the agent's final state.

    `last_active` is the activity-TTL liveness signal: updated by
    `_acquire_slot` on every successful tool acquire and consumed by
    the `_sweep_stale_claims` background loop to reclaim leaked
    slots. Initialized to register-time so a fresh session that
    hasn't issued a tool call yet still gets the full LEASE_TTL grace
    window."""
    pipeline_id: str
    target_path: Path
    problem: str
    workspace: Path
    log_path: Path | None = None
    file_content: str = ""
    last_active: float = field(default_factory=time.monotonic)
    # Pipeline kind ('Backward' / 'Builder' / 'Forward' / …) — lets the
    # submission mirror give pipeline-ACCURATE verdicts (a non-proved
    # citation is a warn for a Backward decomposition but a hard commit
    # reject for Builder). Optional: an old client that doesn't send it
    # gets the kind-agnostic mirror, never an error.
    kind: str | None = None
    # Fingerprint of the attempts dir's `new_*.lean` stub set (name,
    # mtime_ns, size). A freshly WRITTEN stub changes the merged
    # compilation unit, but slot ownership never noticed — errors_at /
    # goal_at elaborated the PREVIOUS unit and reported phantom unknown
    # identifiers on citations validate_file accepted (agent_feedback
    # 2026-07-09/10, ~32 reports). `_resync_buffer_from_disk` compares
    # and invalidates the slot on change.
    stub_fingerprint: tuple = ()
    # --- heartbeat-budget gate (2026-08-12) -------------------------
    #: A heartbeat timeout has been reported to this agent at least once.
    hb_saw_timeout: bool = False
    #: The `maxHeartbeats` this session's content last asked for (None =
    #: never set it, i.e. Lean's default).
    hb_limit: "int | None" = None
    #: Wall seconds the last diagnostics call took — the number the gate
    #: quotes, because a machine-measured cost cannot drift the way a
    #: hard-coded "4M ≈ 8 minutes" would.
    hb_last_check_s: float = 0.0
    #: Content hashes already warned about: the SAME write resent is the
    #: confirmation, so the gate asks once and then gets out of the way.
    hb_confirmed: set = field(default_factory=set)


# ─── Gateway global state ─────────────────────────────────

@dataclass
class GatewayState:
    backend: LspClient | None = None
    workspace: Path | None = None
    workers: list[WorkerSlot] = field(default_factory=list)
    sessions: dict[str, SessionMetadata] = field(default_factory=dict)
    sessions_lock: threading.Lock = field(default_factory=threading.Lock)
    ready_event: threading.Event = field(default_factory=threading.Event)
    init_error: str | None = None
    # Slot acquire path counters (visible via /health). Under 1:1
    # binding (#118), cold_evicted never fires — slots are owned by a
    # single pipeline for their lifetime and never serve another's
    # content. Hot vs cold_warmup distinguishes first-tool-call (must
    # didChange) from later calls on the same claim.
    counters_lock: threading.Lock = field(default_factory=threading.Lock)
    n_hot: int = 0           # this slot already has our content loaded
    n_cold_warmup: int = 0   # first tool call on this slot for this claim
    n_cold_noswap: int = 0   # swap_in=False (apply_edit / validate_file)
    n_busy_polls: int = 0    # times we slept 0.1s waiting for our slot's lock
    # The dispatch.pool value this process launched under, BEFORE any
    # RAM clamp — the daemon's reuse gate compares yaml-to-yaml against
    # this, so a clamped pool doesn't read as a stale gateway.
    workers_configured: int | None = None
    # Absolute age past which a claim is reclaimed even from a LIVE
    # owner. Derived from `dispatch.spawn_timeout_sec` at startup (see
    # `_sweep_stale_claims`); the default matches a 1800s spawn.
    claim_ceiling_sec: float = 3600.0
    # One-way latch: the FIRST warm has finished (whatever happens to
    # the backend later). HTTP now opens before that warm, so this is
    # what separates "the pool has never been up" from "a wedge restart
    # cleared `ready_event` and Lean work is legitimately waiting for
    # the replacement". Lean surfaces refuse fast in the first case and
    # keep blocking in the second — `_ensure_backend_ready` alone can't
    # tell them apart, and blocking through the initial warm would put
    # a 240s wait on the event loop where `/compute` lives.
    first_warm_done: bool = False
    #: Set by the warm watcher when the initial warm fails; `main`
    #: turns it into the same rc 3 the blocking version exited with.
    warm_failed: str | None = None
    #: The uvicorn Server, so the watcher can ask it to stop rather
    #: than `os._exit` past the Lean-subtree reap in `main`'s finally.
    http_server: object | None = None
    #: Adaptive RAM ledger (owner design 2026-08-25). None = static
    #: mode: the pool is exactly what launch warmed, nothing closes.
    #: Set via POST /warm_target by the dispatcher's ledger tick; the
    #: converger warms toward it, the release path sheds above it.
    warm_target: "int | None" = None
    #: Measured veto the dispatcher sends with the target: never start
    #: a warm when the machine's available RAM (GB) is below this.
    warm_min_available_gb: float = 0.0
    #: Single-flight latch for the background converger thread.
    warm_converger_on: bool = False


_state = GatewayState()

# Source-tree fingerprint at THIS process's import time (version-skew
# guard). The gateway deliberately outlives daemons; a reusing daemon
# compares this /health field against the CURRENT tree (lifecycle.
# code_fingerprint) and relaunches the gateway on any drift — a stale
# process answers /health 200 while its tool calls 500 on new-code
# requests (sphere daemon #5, 2026-07-05). Computed once: it must
# describe the code THIS process loaded, not the disk's later state.
from .lifecycle import code_fingerprint as _code_fp
_CODE_FINGERPRINT = _code_fp()
del _code_fp
_session_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "asterism_session", default=None
)


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


@contextlib.contextmanager
def _elab_gate(slot_uri: "str | None" = None):
    """Hold one elaboration ticket for the did_change→wait critical
    section. Acquire AFTER the slot lock (never while queuing for a
    slot — head-of-line blocking), release when the elaboration is
    actually done: if the caller's wait timed out while Lean still
    reports the slot busy, a watcher escorts the permit until
    fileProgress clears. A saturated queue past the timeout fails LOUD
    with a retryable message instead of burning the caller's wall."""
    global _ELAB_BUSY, _ELAB_WAITING
    with _ELAB_CTR_LOCK:
        _ELAB_WAITING += 1
    try:
        ok = _ELAB_SEM.acquire(timeout=_ELAB_QUEUE_TIMEOUT_SEC)
    finally:
        with _ELAB_CTR_LOCK:
            _ELAB_WAITING -= 1
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


# ─── Logging ─────────────────────────────────────────────

def _log_for(meta: SessionMetadata | None, event: dict) -> None:
    """Best-effort per-session JSONL log. Silent on missing log_path
    or any write failure — never crash a tool call over a log hiccup."""
    if meta is None or meta.log_path is None:
        return
    event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    try:
        meta.log_path.parent.mkdir(parents=True, exist_ok=True)
        with meta.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str))
            f.write("\n")
    except Exception:
        pass


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

_BACKEND_WEDGE_SEC = 600.0
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


#: One targeted rescue per slot per window: a SECOND wedge of the same
#: slot this soon smells like server state rot, not one runaway
#: elaboration — that shape escalates to the full restart.
_WEDGE_TARGETED_HISTORY: "dict[str, float]" = {}
_WEDGE_REPEAT_WINDOW_SEC = 1800.0


def _kill_worker_for_uri(uri: str) -> bool:
    """Tree-kill the ONE `lean --worker` process serving `uri`.

    The mapping is exact for the same reason `_slot_private_mb`'s is:
    Lean puts the document URI on the worker's own command line, so
    nothing depends on process order. Returns whether a worker was
    actually killed."""
    try:
        import psutil
        me = psutil.Process(os.getpid())
        killed = False
        for proc in me.children(recursive=True):
            try:
                argv = proc.cmdline()
            except (psutil.Error, OSError):
                continue
            if "--worker" not in argv or uri not in argv:
                continue
            for child in proc.children(recursive=True):
                with contextlib.suppress(Exception):
                    child.kill()
            with contextlib.suppress(Exception):
                proc.kill()
                killed = True
        return killed
    except Exception:  # noqa: BLE001 — the caller escalates instead
        return False


def _recycle_wedged_slot(uri: str) -> bool:
    """Targeted wedge recovery: kill the one runaway worker and re-warm
    ITS slot, leaving every other slot's claim intact.

    Scale motive (owner ruling 2026-08-24): 166 whole-pool restarts on
    record, each stripping EVERY in-flight session of its slot claim
    plus a cold content re-warm (420 victims at pool 4-12) — at cloud
    pool sizes one wedge would take ~50 live formalizers' Lean surface
    down at once. The close/re-open flow is `_recycle_slot_if_heavy`'s,
    in production since 2026-08-14.

    Returns True when the slot is back in the pool. False hands the
    wedge to `_restart_backend` — the pre-2026-08-24 behavior, kept as
    the escalation for every shape this path cannot prove it fixed
    (repeat wedge of the same slot, claim-lock held by a live request,
    worker not found, re-open failure)."""
    now = time.monotonic()
    last = _WEDGE_TARGETED_HISTORY.get(uri)
    if last is not None and now - last < _WEDGE_REPEAT_WINDOW_SEC:
        return False
    backend = _state.backend
    slot = next((s for s in _state.workers if s.slot_uri == uri), None)
    if backend is None or slot is None:
        return False
    if not slot.lock.acquire(blocking=False):
        # A request thread is mid-call on this slot; yanking the worker
        # under it risks a half-state the full restart already handles.
        return False
    try:
        if not _kill_worker_for_uri(uri):
            return False
        try:
            with contextlib.suppress(Exception):
                backend.did_close(slot.slot_path)
            backend.did_open(slot.slot_path, WARMUP_CONTENT)
            backend.wait_for_file_done(slot.slot_uri, timeout=300)
        except Exception:  # noqa: BLE001 — escalation handles it
            return False
        # Claim cleared: the owning session re-claims on its next call
        # and pays ONE cold content warm — the price every session paid
        # under the whole-pool restart, now paid by one.
        slot.claimed_by = None
        slot.content_pipeline_id = None
        _WEDGE_TARGETED_HISTORY[uri] = now
        print(f"[gateway] wedged worker on slot {slot.slot_id} killed "
              f"and recycled — every other slot keeps its claim",
              file=sys.stderr, flush=True)
        return True
    finally:
        slot.lock.release()


def _wedge_watchdog_loop() -> None:
    """Replace the backend if any slot's Lean elaborate has been in-flight
    past `_BACKEND_WEDGE_SEC` — a non-terminating elaborate, well beyond
    the 120s per-op / 300s warmup waits."""
    nonempty_since: dict[str, float] = {}
    while True:
        time.sleep(30.0)
        backend = _state.backend
        if backend is None or not _state.ready_event.is_set():
            nonempty_since.clear()
            continue
        now = time.monotonic()
        try:
            busy = backend.busy_uris()
        except Exception:
            continue
        for uri in list(nonempty_since):
            if uri not in busy:
                nonempty_since.pop(uri, None)
        wedged = None
        for uri in busy:
            t0 = nonempty_since.setdefault(uri, now)
            if now - t0 > _BACKEND_WEDGE_SEC:
                wedged = uri
                break
        if wedged is not None:
            nonempty_since.clear()
            if not _recycle_wedged_slot(wedged):
                _restart_backend(
                    f"elaborate on {wedged} wedged "
                    f">{int(_BACKEND_WEDGE_SEC)}s")


# ─── Slot acquisition (the heart of Phase 2) ─────────────

def _borrow_order(workers):
    """Slot preference for a borrow probe: UNCLAIMED slots first (evicting a
    registered session's warm content costs its owner a cold_warmup and can
    block it behind our lock — the 2026-06-29 slot-thrash shape), LRU within
    each group. A claimed slot is reachable only when every unclaimed slot is
    lock-busy — liveness for housekeeping probes when the whole pool is
    registered. Extracted for direct unit-testing of the ordering invariant."""
    # `closed` slots have no live worker (RAM-ledger shed) — a borrow
    # would didChange a did_close'd URI. They are also unclaimed, so
    # without the filter they would be picked FIRST (external review
    # 2026-08-25: the third acquisition path the claim-site fix missed).
    return sorted((s for s in workers
                   if not getattr(s, "reserved", False)
                   and not getattr(s, "closed", False)),
                  key=lambda s: (s.claimed_by is not None, s.last_used_ts))


@contextlib.contextmanager
def _acquire_slot(meta: SessionMetadata, *, swap_in: bool = True,
                  borrow: bool = False):
    """Acquire a worker slot for one tool op.

    Two modes:

      Default (`borrow=False`) — for registered sessions only. The
      session has previously claimed a slot at `register_session`;
      this function locks the claimed slot for the duration of one
      tool op:
        * Hot path:  slot already has our content didChanged in
                     (`content_pipeline_id == pipeline_id`) → no swap.
        * Cold path: first tool call on this claim, or content was
                     cleared by a probe → didChange + set content_pipeline_id.

      Probe mode (`borrow=True`) — for one-shot RPCs that don't have a
      registered session (notably the framework's `/verify` endpoint).
      Borrows any free-lock slot, didChanges the probe's content in,
      and clears `content_pipeline_id` after release so the slot's
      registered owner re-loads its own content on its next acquire.
      Used sparingly; each borrow imposes one cold_warmup on the
      owner's subsequent acquire.

    `swap_in=False` skips the didChange — used by apply_edit which
    will overwrite content via its own RPC.
    """
    backend = _state.backend
    if backend is None:
        raise RuntimeError("backend not ready")
    if not _state.workers:
        raise RuntimeError("no workers in pool")

    if borrow:
        # Probe mode: find an unlocked slot via _borrow_order. The docstring
        # always promised "prefer unclaimed" but the code only implemented
        # "lock not held": a borrow could land on (and evict the warm content
        # of) a registered session's slot even while free slots sat idle —
        # and the plain-LRU order actively PREFERRED the slot of a pipeline
        # in a long think (oldest last_used_ts), the 2026-06-29 slot-thrash
        # shape. Claimed slots are now the fallback only when every unclaimed
        # slot is lock-busy (liveness: a housekeeping probe must still get a
        # slot when the whole pool is registered). Re-sort each poll so
        # claims/releases during the 120s window are observed.
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            for slot in _borrow_order(_state.workers):
                if slot.lock.acquire(blocking=False):
                    try:
                        if swap_in:
                            with _elab_gate(slot.slot_uri):
                                slot.file_version += 1
                                backend.clear_diagnostics(slot.slot_uri)
                                backend.did_change_full(
                                    slot.slot_path, meta.file_content,
                                    slot.file_version,
                                )
                                try:
                                    backend.wait_for_diagnostics(
                                        slot.slot_uri, slot.file_version,
                                        timeout=120,
                                    )
                                except (TimeoutError, RuntimeError):
                                    pass
                            # Probe owns content for the borrow only;
                            # clearing here forces the slot's registered
                            # owner (if any) to didChange its own
                            # content back in on its next acquire.
                            slot.content_pipeline_id = None
                            kind = "cold_warmup"
                            with _state.counters_lock:
                                _state.n_cold_warmup += 1
                        else:
                            kind = "cold_noswap"
                            with _state.counters_lock:
                                _state.n_cold_noswap += 1
                        yield (slot, kind)
                        slot.last_used_ts = time.time()
                        return
                    finally:
                        slot.lock.release()
            with _state.counters_lock:
                _state.n_busy_polls += 1
            time.sleep(0.1)
        raise RuntimeError(
            "no slot available for probe within 120s "
            "(all slots locked by their registered sessions' tool ops)"
        )

    # Claimed-session mode: locate this pipeline's claimed slot.
    my_slot: WorkerSlot | None = None
    for slot in _state.workers:
        if slot.claimed_by == meta.pipeline_id:
            my_slot = slot
            break
    if my_slot is None:
        # The claim is gone but the SESSION is not — an unregistered
        # token never reaches here (`no session`, :1659). The identity
        # and the resource are two layers, and only the resource was
        # destroyed: `_restart_backend` builds a whole fresh slot list,
        # so every live session's claim disappears with the old pool
        # while `_state.sessions` keeps every one of them. Re-claim is
        # what that function's own docstring has promised since it was
        # written ("their next tool call re-claims or gets a clear
        # error") — only the second half was ever implemented.
        #
        # Measured cost of the missing half: two death CLUSTERS, each
        # trailing a restart by minutes — 08-11 14:47:17Z → three deaths
        # 14:53/14:55/14:57, 08-12 06:06:43Z → two at 06:10/06:15. One
        # restart orphans every in-flight pipeline at once and they fall
        # over one by one as each next touches Lean.
        #
        # A session the stale-claim sweep took is `pop`ped from
        # `_state.sessions` outright (:844), so it cannot come back this
        # way — a reclaimed slot stays reclaimed.
        want_reserved = (meta.kind == "interactive")
        free: WorkerSlot | None = None
        with _state.sessions_lock:
            free = next((s for s in _state.workers
                         if s.claimed_by is None and not s.closed
                         and s.reserved == want_reserved), None)
            if free is not None:
                free.claimed_by = meta.pipeline_id
        if free is not None:
            # LOUD on purpose. Replacing the pool left no trace at all,
            # which is why this took two days and two clusters to find;
            # a self-healing path that swallows its own evidence just
            # moves the next investigation further from the cause.
            print(f"[gateway] pipeline {meta.pipeline_id[:8]} re-claimed "
                  f"slot {free.slot_id} — its previous claim is gone "
                  f"(backend restart replaces the whole pool). One cold "
                  f"warmup follows: the old slot's content died with the "
                  f"old backend.", file=sys.stderr, flush=True)
            my_slot = free

    if my_slot is None:
        # Everything else now has its own exit, so one cause is left:
        # the session is registered, the claim is gone, and there is no
        # free slot to give it. The two causes this message used to name
        # (register_session never called / release racing a use) were
        # wrong for every occurrence anyone investigated, and it sent
        # three separate investigations down the wrong path before
        # 2026-08-11; the sweep it then named was wrong for the two
        # clusters above. Third time: say only what is reachable.
        raise RuntimeError(
            f"no slot claimed for pipeline {meta.pipeline_id} and no free "
            f"slot to re-claim — every one of the {len(_state.workers)} "
            "worker slots is held by another session. This is a framework "
            "resource shortage, not anything in the file you are editing "
            "and nothing your patch can fix: retry this call, and if it "
            "repeats, report it as framework feedback."
        )

    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        if my_slot.lock.acquire(blocking=False):
            try:
                if swap_in:
                    if my_slot.content_pipeline_id == meta.pipeline_id:
                        kind = "hot"
                        with _state.counters_lock:
                            _state.n_hot += 1
                    else:
                        # First tool call on this claim — slot is either
                        # in warmup state, carries a prior claim's
                        # stale content, or had its content cleared by a
                        # /verify probe borrow.
                        kind = "cold_warmup"
                        with _state.counters_lock:
                            _state.n_cold_warmup += 1
                        with _elab_gate(my_slot.slot_uri):
                            my_slot.file_version += 1
                            backend.clear_diagnostics(my_slot.slot_uri)
                            merged, line_map = _compilation_for(meta)
                            backend.did_change_full(
                                my_slot.slot_path, merged,
                                my_slot.file_version,
                            )
                            try:
                                backend.wait_for_diagnostics(
                                    my_slot.slot_uri, my_slot.file_version,
                                    timeout=120,
                                )
                            except (TimeoutError, RuntimeError):
                                pass
                        my_slot.content_pipeline_id = meta.pipeline_id
                        my_slot.line_map = line_map
                else:
                    kind = "cold_noswap"
                    with _state.counters_lock:
                        _state.n_cold_noswap += 1
                meta.last_active = time.monotonic()
                yield (my_slot, kind)
                my_slot.last_used_ts = time.time()
                meta.last_active = time.monotonic()
                return
            finally:
                my_slot.lock.release()
        # Slot is locked by a concurrent tool op from this same pipeline
        # (single-threaded spawn ⇒ this should be rare and brief).
        with _state.counters_lock:
            _state.n_busy_polls += 1
        time.sleep(0.1)
    raise RuntimeError("claimed slot still busy after 120s")


# ─── Session ops ────────────────────────────────────

def _register_session_internal(
    pipeline_id: str, target_path: Path,
    problem: str, workspace: Path,
    log_path: Path | None,
    kind: str | None = None,
    interactive: bool = False,
) -> tuple[str, str | None]:
    """Stash session metadata AND eagerly claim a worker slot
    (#118, 1:1 binding). The claim is registered by setting
    `slot.claimed_by`; the slot's `content_pipeline_id` stays at its
    prior value until the first tool call's didChange. NO didOpen here
    — that's lazy-deferred to first tool call. Returns (session_token,
    error). `interactive=True` claims ONLY a reserved slot (the serve
    UI's editor) and pipeline claims only unreserved ones — the
    pipeline=slot identity holds in both directions."""
    err = _ensure_backend_ready()
    if err:
        return "", err
    target_path = target_path.resolve()
    if not target_path.exists():
        return "", f"target file not found: {target_path}"
    content = target_path.read_text(encoding="utf-8")
    token = uuid.uuid4().hex
    meta = SessionMetadata(
        pipeline_id=pipeline_id,
        target_path=target_path,
        problem=problem,
        workspace=workspace.resolve(),
        log_path=log_path.resolve() if log_path else None,
        file_content=content,
        kind=kind,
    )
    # Claim a free worker slot for this session's lifetime. With
    # dispatch.pool == workers, there is always one free slot when a
    # spawn is dispatched (the dispatcher's ThreadPoolExecutor caps
    # in-flight spawns at pool size). If we still fail, that's a
    # dispatcher misconfiguration, not a runtime contention case.
    with _state.sessions_lock:
        free_slot = next(
            (s for s in _state.workers
             if s.claimed_by is None and not s.closed
             and s.reserved == interactive), None,
        )
        if free_slot is None:
            return "", (
                "interactive slot busy — another editor session holds it"
                if interactive else
                "no free worker slot — pool exhausted "
                "(dispatch.pool must not exceed actual worker count)"
            )
        free_slot.claimed_by = pipeline_id
        _state.sessions[token] = meta
    _log_for(meta, {"event": "session_registered",
                    "pipeline_id": pipeline_id,
                    "claimed_slot": free_slot.slot_id,
                    "target": str(target_path)})
    return token, None


#: A slot whose worker holds more private bytes than this is recycled
#: when it next falls idle and unclaimed. 0 disables.
#:
#: DELIBERATELY far below `gateway.lean_memory_cap_mb` (8192), because
#: the two answer different questions and must not be collapsed:
#:
#:   the job cap   how much may ONE elaboration commit before the OS
#:                 kills it — a hard ceiling against the 102 GB worker
#:                 that took the box down on 2026-08-10.
#:   this          how fat may a slot get ACROSS elaborations before it
#:                 is cheaper to start it over. Soft, and it swaps a
#:                 process rather than killing work.
#:
#: Measured 2026-08-14 on union_closed: baseline 0.65-0.8 GB (Mathlib +
#: the problem's 285-brick closure), and a claimed slot serving the
#: `decide`-heavy 634 family reached 2.58 GB in ~36 minutes and then sat
#: flat. 1500 sits above every observed baseline and below every
#: observed fat slot.
SLOT_RECYCLE_MB_DEFAULT = 1500


def _recycle_slot_if_heavy(slot: "WorkerSlot") -> None:
    """Restart one slot's worker if it has grown fat — close the
    document, re-open it warm.

    WHEN. Only at this boundary, and only on a slot that is unclaimed
    and not busy. That makes the timing free without having to detect
    it: the NL layer (Strategist, Adversary, Scholar, Librarian) never
    registers a session at all — `write_tools_mcp_config`, not
    `_write_mcp_config` — so a debate round is minutes of Lean idleness,
    and this lands in it by construction rather than by asking what
    time it is.

    WHY A CLOSE. `did_change_full` swaps the content and keeps the
    process; the heap is what needs to go, so the document has to.

    NOT THE OTHER TWO MECHANISMS. The job cap kills a runaway single
    elaboration; the wedge watchdog restarts the backend when an
    elaborate hangs past 600s — and that one, by construction, only ever
    fires while Lean is BUSY. Neither can do this and this can do
    neither: a slot at 2.6 GB is not wedged and not over any cap, it is
    just expensive to keep.

    Failure leaves the slot OPEN. A recycle that half-completes would
    take a worker out of the pool for the rest of the run, which is a
    worse outcome than any amount of memory, so the re-open is attempted
    again on the error path and the failure is printed rather than
    raised.
    """
    cap_mb = SLOT_RECYCLE_MB_DEFAULT
    try:
        from ..core import config as _cfg
        cap_mb = int(_cfg.get("gateway.slot_recycle_mb",
                              default=SLOT_RECYCLE_MB_DEFAULT,
                              env_var="ASTERISM_SLOT_RECYCLE_MB",
                              cast=int))
    except Exception:  # noqa: BLE001 — a policy knob may not halt release
        pass
    if cap_mb <= 0 or _state.backend is None:
        return
    if not slot.lock.acquire(blocking=False):
        return                      # busy: not ours to touch
    try:
        if slot.claimed_by is not None:
            return                  # re-claimed between release and here
        mb = _slot_private_mb().get(slot.slot_id)
        if mb is None or mb < cap_mb:
            return
        print(f"[gateway] slot {slot.slot_id} recycling — {mb} MB private "
              f"(> {cap_mb} MB) and idle. Its worker restarts; no session "
              f"holds it.", file=sys.stderr, flush=True)
        t0 = time.perf_counter()
        try:
            _state.backend.did_close(slot.slot_path)
            _state.backend.did_open(slot.slot_path, WARMUP_CONTENT)
            _state.backend.wait_for_file_done(slot.slot_uri, timeout=300)
            after = _slot_private_mb().get(slot.slot_id)
            print(f"[gateway] slot {slot.slot_id} recycled in "
                  f"{time.perf_counter() - t0:.1f}s — "
                  f"{mb} MB -> {after if after is not None else '?'} MB",
                  file=sys.stderr, flush=True)
        except Exception as exc:  # noqa: BLE001 — never lose a slot
            print(f"[gateway] slot {slot.slot_id} recycle FAILED "
                  f"({type(exc).__name__}: {exc}) — re-opening so the "
                  f"slot stays in the pool", file=sys.stderr, flush=True)
            try:
                _state.backend.did_open(slot.slot_path, WARMUP_CONTENT)
            except Exception:  # noqa: BLE001
                print(f"[gateway] slot {slot.slot_id} could not be "
                      f"re-opened — it will cold-warm on its next claim",
                      file=sys.stderr, flush=True)
    finally:
        slot.lock.release()


# ─── Adaptive warm target (RAM ledger, owner design 2026-08-25) ──
#
# The dispatcher's ledger computes how many Lean slots the RAM budget
# affords once the NL layer's reserve is taken out, and POSTs it to
# /warm_target. Convergence is asymmetric on purpose:
#   * UP: a background converger re-opens closed slots (or extends the
#     roster) one warm at a time, vetoed by measured available RAM.
#   * DOWN: nothing is revoked — a claimed slot finishes its work; the
#     shed lands at release time, where closing the slot (did_close)
#     actually frees the worker's heap.
# Static mode (warm_target is None) leaves all of this dormant.


def _open_pipeline_slots_locked() -> int:
    """Non-reserved slots with a live worker. Caller holds
    sessions_lock."""
    return sum(1 for s in _state.workers
               if not s.reserved and not s.closed)


def _shed_slot_if_over_target(slot: WorkerSlot) -> bool:
    """Close a just-released slot when the warm target sits below the
    open count — its worker exits and the RAM returns to the ledger's
    NL side. Returns whether the slot was shed. The floor of one open
    slot is the Lean side's anti-starvation guarantee (owner ruling:
    NL has priority, but never to zero)."""
    target = _state.warm_target
    if target is None or _state.backend is None:
        return False
    if not slot.lock.acquire(blocking=False):
        return False                # busy: not ours to touch
    try:
        with _state.sessions_lock:
            if slot.claimed_by is not None or slot.closed or slot.reserved:
                return False
            if _open_pipeline_slots_locked() <= max(1, target):
                return False
            slot.closed = True      # invisible to claims from here on
        try:
            _state.backend.did_close(slot.slot_path)
            print(f"[gateway] slot {slot.slot_id} shed — open count above "
                  f"warm target {target}; its worker exits and the RAM "
                  f"returns to the ledger", file=sys.stderr, flush=True)
            return True
        except Exception as exc:  # noqa: BLE001 — never lose a slot
            with _state.sessions_lock:
                slot.closed = False
            print(f"[gateway] slot {slot.slot_id} shed FAILED "
                  f"({type(exc).__name__}: {exc}) — slot stays open",
                  file=sys.stderr, flush=True)
            return False
    finally:
        slot.lock.release()


def _kick_warm_converger() -> None:
    """Start the background convergence loop (single-flight)."""
    with _state.sessions_lock:
        if _state.warm_converger_on:
            return
        _state.warm_converger_on = True
    threading.Thread(target=_warm_converger_run,
                     name="warm-converger", daemon=True).start()


def _warm_converger_run() -> None:
    """Converge the open-slot count toward the target, one slot at a
    time — BOTH directions: warms below it, sheds idle FREE slots above
    it (a target drop with 20 already-free slots must return their RAM
    now, not wait for sessions that will never release them — external
    review 2026-08-25). Busy/claimed slots above target still shed at
    their own release. Exits when converged, when the measured-RAM veto
    fires, or in static mode; the dispatcher re-pushes the target on
    its ledger tick, so an early exit is re-kicked within seconds."""
    try:
        while True:
            target = _state.warm_target
            if target is None or _state.backend is None \
                    or _state.workspace is None \
                    or not _state.first_warm_done:
                # Never converge concurrently with the INITIAL warm —
                # both would mint slot ids from the same (still empty)
                # roster and race on the same slot files.
                return
            with _state.sessions_lock:
                open_n = _open_pipeline_slots_locked()
            if open_n > max(1, target):
                # Downward FIRST, and never vetoed: shedding is how
                # RAM pressure gets relieved — gating it on available
                # RAM would deadlock exactly when it matters. The shed
                # helper re-checks claim/busy/floor under its own
                # locks; nothing idle left → the release path owns
                # the rest.
                shed_any = False
                for s in list(_state.workers):
                    if s.reserved or s.closed or s.claimed_by is not None:
                        continue
                    if _shed_slot_if_over_target(s):
                        shed_any = True
                        break
                if not shed_any:
                    return
                continue
            # Upward from here — the measured veto applies to WARMS
            # only.
            floor = _state.warm_min_available_gb
            if floor > 0:
                try:
                    from ..core import ram_ledger
                    if ram_ledger.available_gb() < floor \
                            + ram_ledger.SLOT_GB_FALLBACK:
                        print(f"[gateway] warm-converger paused — "
                              f"available RAM under the ledger floor "
                              f"({floor:.1f} GB + one slot)",
                              file=sys.stderr, flush=True)
                        return
                except Exception:  # noqa: BLE001 — veto is best-effort
                    pass
            slot: "WorkerSlot | None" = None
            with _state.sessions_lock:
                if _open_pipeline_slots_locked() >= target:
                    return
                slot = next((s for s in _state.workers
                             if s.closed and not s.reserved), None)
                if slot is None:
                    new_id = max((s.slot_id for s in _state.workers),
                                 default=-1) + 1
                    slots_dir = (_state.workspace / ".asterism"
                                 / "runtime_slots")
                    slot_path = slots_dir / f"_gateway_slot_{new_id}.lean"
                    slot = WorkerSlot(
                        slot_id=new_id, slot_path=slot_path,
                        slot_uri=slot_path.as_uri(), closed=True)
                    _state.workers.append(slot)
            if not slot.lock.acquire(blocking=False):
                time.sleep(0.5)
                continue
            try:
                t0 = time.perf_counter()
                slot.slot_path.parent.mkdir(parents=True, exist_ok=True)
                slot.slot_path.write_text(WARMUP_CONTENT, encoding="utf-8")
                _state.backend.did_open(slot.slot_path, WARMUP_CONTENT)
                _state.backend.wait_for_file_done(slot.slot_uri,
                                                  timeout=300)
                with _state.sessions_lock:
                    slot.closed = False
                print(f"[gateway] slot {slot.slot_id} warmed by the "
                      f"converger in {time.perf_counter() - t0:.1f}s "
                      f"(target {target})", file=sys.stderr, flush=True)
            except Exception as exc:  # noqa: BLE001 — keep converging
                print(f"[gateway] converger warm of slot {slot.slot_id} "
                      f"FAILED ({type(exc).__name__}: {exc}) — slot stays "
                      f"closed; next ledger tick retries",
                      file=sys.stderr, flush=True)
                try:
                    _state.backend.did_close(slot.slot_path)
                except Exception:  # noqa: BLE001
                    pass
                return
            finally:
                slot.lock.release()
    finally:
        with _state.sessions_lock:
            _state.warm_converger_on = False


def _release_session_internal(token: str) -> None:
    """Drop session metadata and release this pipeline's claimed worker
    slot (1:1 lifecycle, #118). `content_pipeline_id` is left untouched
    — the next claim will didChange its own content in regardless, so
    clearing it eagerly buys nothing. Idempotent on unknown tokens."""
    freed: "WorkerSlot | None" = None
    with _state.sessions_lock:
        meta = _state.sessions.pop(token, None)
        if meta is None:
            return
        # Clear claim under sessions_lock so a concurrent register
        # cannot grab the slot before we release it.
        for slot in _state.workers:
            if slot.claimed_by == meta.pipeline_id:
                slot.claimed_by = None
                freed = slot
                break
    _log_for(meta, {"event": "session_released",
                    "pipeline_id": meta.pipeline_id})
    # OUTSIDE sessions_lock: the recycle re-warms a worker (tens of
    # seconds) and must not hold the lock every register waits on.
    # Ledger shed first: a slot the target no longer affords is CLOSED
    # (RAM back to the NL side) — recycling it would re-warm a worker
    # we are about to kill.
    if freed is not None:
        if not _shed_slot_if_over_target(freed):
            _recycle_slot_if_heavy(freed)


def _current_session() -> SessionMetadata | None:
    token = _session_ctx.get()
    if token is None:
        return None
    with _state.sessions_lock:
        return _state.sessions.get(token)


# ─── Stale-claim sweep (#118 follow-up) ────────────────

# A silence threshold that no longer gates anything, kept for one job:
# it is the floor under `claim_ceiling_sec` (see `main`). The history is
# worth keeping because the constant got demoted twice, both times for
# the same reason.
#
# It began as the reclaim threshold, justified by "worker timeouts are
# 600s (main) + 180s (postmortem), so 900s is well above
# WORKER_TIMEOUT". Then `dispatch.spawn_timeout_sec` went 960 → 1800
# and the premise inverted — the TTL became HALF the life a worker is
# granted, and the sweep started taking slots from workers that were
# merely waiting on a heavy elaboration. Measured: 57 reclaims in one
# day, all in the 900-960s band, including pipeline d9c3e052 which went
# on issuing tool calls for another 20 minutes afterwards. Its next call
# got "no slot claimed", charged to the goal as a `lake_build_error` —
# infra death wearing mathematics' clothes. 2026-08-11 demoted it from
# "when to reclaim" to "when to start asking".
#
# 2026-08-13 removed the second role too. Silence is measured on the
# TOOL clock (`last_active`, updated in `_acquire_slot`), and a worker
# waiting on Lean is silent by definition — so silence was never
# evidence about the owner in either direction. Making it the
# PRECONDITION for asking meant a process that died at second one was
# not asked about until 900s, which is how a leak outlived the daemon
# that could have survived it. The question is cheap and the answer is
# on disk: `_sweep_stale_claims` now asks every pass.
_LEASE_TTL_SEC = 900.0
_SWEEP_INTERVAL_SEC = 60.0


#: Head and tail of the echo of a removed region. A head-only cap put
#: the truncation exactly where the evidence lives: an edit that reaches
#: further than intended shows the opening the agent expected and hides
#: the tail it did not mean to lose. Both ends, plus the count of what
#: sits between them, so "I removed more than I thought" is legible
#: without shipping the whole region back (2026-08-11).
_ECHO_END_CHARS = 160


def _echo_removed(removed: str) -> str:
    """What an edit took out, as the agent needs to see it."""
    if len(removed) <= 2 * _ECHO_END_CHARS:
        return removed
    head = removed[:_ECHO_END_CHARS]
    tail = removed[-_ECHO_END_CHARS:]
    n_lines = removed.count("\n") - head.count("\n") - tail.count("\n")
    return (f"{head}\n… [{len(removed) - 2 * _ECHO_END_CHARS} chars / "
            f"{max(n_lines, 0)} lines removed here too] …\n{tail}")


def _owner_alive(meta: SessionMetadata) -> bool:
    """Is the process that claimed this slot still running?

    Same evidence as `state.recovery._attempt_owner_alive` (the
    `owner_pid` every SpawnWorkspace writes into its sandbox manifest)
    but the OPPOSITE default when the evidence is missing, and the
    difference is deliberate. There, unknown means "safe to delete an
    orphan directory", so unknown → dead. Here, unknown means "take a
    quarter of the pool away from something that may be working", so
    unknown → alive. Sessions with no attempts dir at all (the serve
    UI's editor, agy's LSP bridge) live in that gap.

    What keeps that default from becoming a leak is the ceiling in
    `_sweep_stale_claims`: an unknown owner holds its slot for at most
    `claim_ceiling_sec`, never forever.
    """
    try:
        import json as _json
        from ..agent.sandbox import MANIFEST_NAME, _pid_alive
        manifest_path = (Path(meta.workspace) / ".attempts"
                         / meta.pipeline_id / "sandbox" / MANIFEST_NAME)
        data = _json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return True         # no evidence — the ceiling bounds this
    try:
        return bool(_pid_alive(data.get("owner_pid")))
    except Exception:  # noqa: BLE001 — a probe must not halt the sweep
        return True


def _sweep_stale_claims() -> int:
    """One sweep pass: walk active sessions, reclaim any claim whose
    `last_active` is older than LEASE_TTL. Returns the count of slots
    reclaimed (0 in the steady-state hot path).

    Reclaim semantics match `_release_session_internal` — pop from
    `sessions` + clear `claimed_by` on the matching slot. We DO NOT
    clear `content_pipeline_id` (mirrors release semantics; the next
    claim's first tool call will didChange its own content in
    regardless).

    Brouwer 2026-05-23: observed 4/4 slots claimed but only 2 active
    spawn dirs on disk + workers_busy=0. /release urlopen failures
    silently leaked claims; the daemon eventually self-exited via
    CONSEC_GATEWAY_UNREACHABLE_LIMIT=8 once concurrent dispatches
    couldn't find any free slot.

    That last sentence used to end "Activity-TTL self-heals before that
    safety net trips." 2026-08-13 falsified it, and not narrowly: a
    killed daemon left 3 of 4 slots claimed, the next daemon REUSED the
    gateway (same code fingerprint, so the version-skew gate passed),
    every /register answered "no free worker slot", and the breaker
    fired at ~780s. The cure could not have raced the disease, because
    the cure was not running: the owner-liveness question was gated
    behind `_LEASE_TTL_SEC` of silence, so a process that had been dead
    since second one was not even ASKED about until 900s — and with its
    attempts dir already deleted by the next daemon's recovery sweep,
    the answer would have been "unknown → alive", holding the slot to
    the 3600s ceiling.

    So the gate is gone. Death is not a function of silence: ask every
    pass. Silence still governs the LIVE and UNKNOWN owners, via the
    ceiling — that part was always the point."""
    now = time.monotonic()
    reclaimed = 0
    with _state.sessions_lock:
        # Snapshot then mutate — we hold the lock for the whole sweep
        # because reclaim writes `claimed_by` and `sessions.pop` need
        # the same lock that /register / /release use to serialize
        # claim transitions. The work per session is O(workers) for
        # the slot lookup which is bounded (~4 in production), so
        # holding the lock for the full pass is cheap — and so is the
        # liveness probe (one small JSON read + one pid check), which
        # is why asking every pass costs nothing worth gating.
        for tok, meta in list(_state.sessions.items()):
            inactive_for = now - meta.last_active
            over_ceiling = inactive_for > _state.claim_ceiling_sec
            # Two independent grounds, neither derived from the other:
            #   * the owner is PROVABLY gone — reclaim now, at any age.
            #     A dead process will not issue another tool call, so
            #     there is nothing to protect and nothing to wait for.
            #   * the claim is past the absolute ceiling — reclaim
            #     regardless of liveness. A slot is 25% of the pool and
            #     an orphan (a daemon that died outside its Job Object)
            #     would otherwise hold one forever with nobody left to
            #     sweep it. A LIVE owner older than the spawn budget
            #     means the watchdog that should have killed it did
            #     not, and that is worth both the slot and a loud line.
            # An owner we cannot identify (the serve UI's editor, agy's
            # LSP bridge — no attempts dir at all) reads as alive by
            # `_owner_alive`'s deliberate default, so only the ceiling
            # ever takes its slot.
            owner_gone = not _owner_alive(meta)
            if not (owner_gone or over_ceiling):
                continue
            _state.sessions.pop(tok, None)
            for slot in _state.workers:
                if slot.claimed_by == meta.pipeline_id:
                    slot.claimed_by = None
                    break
            reclaimed += 1
            if over_ceiling:
                print(
                    f"[gateway] ANOMALY: reclaimed slot for pipeline "
                    f"{meta.pipeline_id[:8]} at {inactive_for:.0f}s "
                    f"inactive — past the {_state.claim_ceiling_sec:.0f}s "
                    f"ceiling, so the claim goes whether or not the owner "
                    f"still runs. An owner alive past its spawn budget "
                    f"means the watchdog did not fire; check it.",
                    file=sys.stderr, flush=True,
                )
            else:
                print(
                    f"[gateway] reclaimed leaked slot for "
                    f"pipeline {meta.pipeline_id[:8]} "
                    f"(owner pid is gone; it had been silent "
                    f"{inactive_for:.0f}s, which is NOT why — death is "
                    f"not a function of silence)",
                    file=sys.stderr, flush=True,
                )
    return reclaimed


def _stale_claim_sweep_loop() -> None:
    """Background daemon thread. Runs every `_SWEEP_INTERVAL_SEC`
    forever; any per-pass exception is logged and swallowed so a
    bad-state session can't crash the sweeper."""
    while True:
        try:
            time.sleep(_SWEEP_INTERVAL_SEC)
            _sweep_stale_claims()
        except Exception as exc:  # noqa: BLE001 — keep loop alive
            print(f"[gateway] stale-claim sweep raised: {exc}",
                  file=sys.stderr, flush=True)


# ─── Diag + import helpers ─────────────────────────

def _ts_now() -> str:
    """High-precision UTC ISO timestamp for server-side stamping into
    tool responses. Pairs with claude.exe's session jsonl message
    timestamps to localize MCP transport / claude-internal latency
    versus actual gateway processing time. Cheap (<1µs)."""
    return datetime.now(timezone.utc).isoformat()


def _format_diag(d: dict) -> dict:
    rng = d.get("range") or {}
    start = rng.get("start") or {}
    sev_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
    return {
        "line": (start.get("line", 0) or 0) + 1,
        "col": start.get("character", 0) or 0,
        "severity": sev_map.get(d.get("severity", 0), str(d.get("severity"))),
        "message": d.get("message", ""),
    }


def _collapse_repeats(formatted: "list[dict]") -> "list[dict]":
    """Fold diagnostics that repeat the same message verbatim into one
    entry carrying `repeats` + `also_lines`. Nothing is hidden — the
    payload is the same information at one tenth the reading cost
    (07-29 feedback: three identical `push_neg` deprecation warnings on
    every probe, competing with the real ok/error signal)."""
    out: "list[dict]" = []
    seen: "dict[tuple[str, str], dict]" = {}
    for f in formatted:
        key = (str(f.get("severity")), str(f.get("message")))
        first = seen.get(key)
        if first is None:
            seen[key] = f
            out.append(f)
            continue
        first["repeats"] = int(first.get("repeats", 1)) + 1
        first.setdefault("also_lines", []).append(f.get("line"))
    return out


def _metaprog_error(text: str, where: str) -> "str | None":
    """Readable form of the metaprogramming gate (`state.metaprog`), or
    None when `text` is clean.

    Every gateway path that hands agent text to Lean calls this FIRST.
    The hard backstop lives one layer down in `client._guard_
    metaprogramming` (raised from `did_open`/`did_change_full`, so no
    elaboration can happen without a scan at all); these call sites exist
    to turn that into an answer the agent can act on — being stopped is a
    teaching moment, not a stack trace. `tests/test_metaprog_guard.py`
    pins both layers.

    Why the gateway and not only the commit gate: elab-time code runs
    with the FRAMEWORK's privileges the moment a tool touches the file —
    the danger is being elaborated, not being committed, and every
    in-spawn tool elaborates long before any commit gate looks.
    """
    token = metaprog.scan_metaprogramming(text)
    if token is None:
        return None
    return metaprog.blocked_detail(token, where=where)


def _needed_imports(content: str, problem: str, workspace: Path) -> list[str]:
    """Single impl in `state.assemble` — the SAME function the commit paths
    run (task #5 Step A: no more hand-mirroring of the pipeline's injection
    rules). Used by `_ensure_imports` and the sibling-inlining path (which
    hoists these into the merged import block)."""
    return assemble.needed_framework_imports(
        content, problem=problem, workspace=workspace)


def _ensure_imports(content: str, problem: str, workspace: Path) -> str:
    """Single impl in `state.assemble` (= commit's `_ensure_imports_subgoal`)."""
    return assemble.ensure_framework_imports(
        content, problem=problem, workspace=workspace)


def _inline_sibling_stubs(
    content: str, sibling_texts: "list[str]", extra_imports: "list[str]",
    opens: "list[str]" = (),
) -> "tuple[str, list[int | None]]":
    """Build a single elaboration unit where sibling stub declarations
    precede `content`, so `<slug>` citations to freshly-declared sibling
    sub-goals resolve. Those `new_<slug>.lean` stubs live in the spawn's
    attempts dir — off the lake source path — so they cannot be imported
    pre-commit (the framework only appends their imports at commit time);
    an agent assembling the final linked patch.lean therefore can't verify
    citation arg-order / arity until after submit (agent_feedback T3).

    Lean requires every `import` at the top of the file, so all import
    lines (the siblings' own, plus `extra_imports` = the Mathlib/Defs the
    framework would inject) are hoisted and de-duped; the siblings' bodies
    (`namespace … theorem <slug> … := by sorry … end` — re-opening the
    same namespace is legal) are placed before `content`'s body.

    Returns `(merged, line_map)` where `line_map[i]` is the 1-indexed line
    of the ORIGINAL `content` that merged line `i + 1` corresponds to, or
    `None` for a framework / sibling-stub line. A hoisted import that the
    AGENT wrote keeps its original line number (a bad `import` line is the
    agent's own diagnostic, not sibling noise). The caller remaps
    diagnostics back to the agent's content frame and tags / drops the
    sibling-region ones, so line numbers stay meaningful (it must NOT
    reintroduce the very buffer/line desync T1 just fixed).

    Each sibling block is wrapped in an anonymous `section … end`: a
    stub's file-scope `open`/`variable` commands are module-local after
    commit (`import` does not propagate them), so letting them leak into
    later siblings / `content` in the single unit was a false-green class
    — content leaning on a sibling's `open` validated green here and died
    at the post-commit lake build. Declarations are unaffected by
    `section`, so citations still resolve."""
    all_imports: "list[tuple[str, int | None]]" = []  # (line, content origin)

    def _add_import(line: str, origin: "int | None" = None) -> None:
        for i, (ln, org) in enumerate(all_imports):
            if ln == line:
                if org is None and origin is not None:
                    all_imports[i] = (ln, origin)
                return
        all_imports.append((line, origin))

    for imp in extra_imports:
        _add_import(imp)

    # content: hoist its imports (keeping their original line numbers),
    # keep the body with a back-map to the agent's 1-indexed lines.
    content_body: list[tuple[str, int]] = []
    for idx, ln in enumerate(content.split("\n")):
        if ln.startswith("import "):
            _add_import(ln, idx + 1)
        else:
            content_body.append((ln, idx + 1))

    sib_body: list[str] = []
    for text in sibling_texts:
        block: list[str] = []
        for ln in text.split("\n"):
            if ln.startswith("import "):
                _add_import(ln)
            else:
                block.append(ln)
        sib_body.append("section")
        sib_body.extend(block)
        sib_body.append("end")
        sib_body.append("")  # blank line between sibling blocks

    merged: list[str] = []
    line_map: list[int | None] = []
    for imp, origin in all_imports:
        merged.append(imp)
        line_map.append(origin)
    merged.append("")
    line_map.append(None)
    # File-level `open`s (from Defs.lean) belong above any `namespace`, so
    # they sit between the hoisted imports and the sibling/content bodies.
    # All map to None — they are framework prefix, not the agent's content.
    for op in opens:
        merged.append(op if op.startswith("open ") else f"open {op}")
        line_map.append(None)
    if opens:
        merged.append("")
        line_map.append(None)
    for ln in sib_body:
        merged.append(ln)
        line_map.append(None)
    if sib_body:
        merged.append("")
        line_map.append(None)
    for ln, orig in content_body:
        merged.append(ln)
        line_map.append(orig)
    # Terminating newline: without it, Lean's end-of-input pseudo-command
    # starts at the END of the last line and Mathlib's
    # `linter.style.whitespace` fires the ghost "'' starts on column N"
    # warning on the candidate's `end` line — reported by every proving
    # agent, every day (~25 feedback entries).
    return "\n".join(merged) + "\n", line_map


# Declaration of `<slug>` in the candidate itself — so validating a
# standalone `new_<slug>.lean` stub inlines nothing (it declares its own
# slug), and we never inline a sibling the content already defines.
_DECL_SLUG_RE_TMPL = (
    r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:noncomputable[ \t]+|private[ \t]+|protected[ \t]+|scoped[ \t]+)*"
    r"(?:theorem|lemma|def|structure|class|abbrev)[ \t]+{slug}\b")


def _collect_referenced_sibling_stubs(
    attempts_dir: Path, content: str, own_name: "str | None" = None,
) -> "list[tuple[str, str]]":
    """Sibling `new_<slug>.lean` stubs in `attempts_dir` that `content`
    REFERENCES (uses `<slug>` as an identifier) but does NOT itself
    declare — computed to a FIXPOINT: a collected stub's own references
    pull further stubs in (D-lite: a stub B referenced only by stub A used
    to be absent from the unit, so A's citation of B silently vanished
    from the probe instead of resolving or erroring). Excludes the stub
    being validated and any already inlined, so validating a standalone
    stub (which references no sibling) inlines nothing and the common case
    stays the plain `_ensure_imports` path."""
    out: list[tuple[str, str]] = []
    try:
        stubs = sorted(attempts_dir.glob("new_*.lean"))
    except OSError:
        return out
    texts: "dict[str, str]" = {}
    for stub in stubs:
        # THE SESSION'S OWN TARGET IS NOT A SIBLING, and file identity is
        # the only test that says so for every seat. The decl-name guard
        # below ("does `content` declare `<slug>`") holds for Backward,
        # whose stub file and theorem share a name — and never for
        # Forward, whose target is `new_forward.lean` while its theorem
        # is whatever the agent invented. So the target's DISK copy was
        # inlined ahead of the live content, the unit carried the
        # declaration twice, and the tools reported "has already been
        # declared" against the very line the agent had just written.
        # Latent since 2026-06-18; 45 reports on 08-13/14 alone, all
        # Forward, none Backward. The reference test that let it in is a
        # bare word match over the whole text INCLUDING COMMENTS, and
        # the word came from the framework's own seed scaffold
        # (`pipeline/forward.py`: "-- Write ONE forward lemma here").
        if own_name is not None and stub.name == own_name:
            continue
        slug = stub.stem[len("new_"):]
        if not slug:
            continue
        try:
            texts[slug] = stub.read_text(encoding="utf-8")
        except OSError:
            continue
    collected: "dict[str, str]" = {}
    frontier = [content]
    while frontier:
        scan = frontier.pop()
        for slug, text in texts.items():
            if slug in collected:
                continue
            if re.search(_DECL_SLUG_RE_TMPL.format(slug=re.escape(slug)),
                         content):
                continue  # content declares it (the stub itself / inlined)
            if not re.search(rf"\b{re.escape(slug)}\b", scan):
                continue  # not referenced by this text
            collected[slug] = text
            frontier.append(text)
    # deterministic order (glob order) for stable units
    return [(s, texts[s]) for s in texts if s in collected]


def _toposort_siblings(
    siblings: "list[tuple[str, str]]",
) -> "list[tuple[str, str]]":
    """Order `(slug, text)` sibling stubs so each appears AFTER every other
    sibling whose slug its body references — Lean needs a declaration before
    its use, but `_collect_referenced_sibling_stubs` returns glob
    (alphabetical) order, breaking inter-sibling citations (agent_feedback:
    "inlining sub-goal stubs ... yields a spurious unknown-identifier
    forward-reference"). Stable among independents; a dependency cycle
    (shouldn't occur for sorry-stubs) degrades to input order rather than
    dropping any stub."""
    texts = dict(siblings)
    all_slugs = [s for s, _ in siblings]
    deps: "dict[str, set]" = {}
    for slug, text in siblings:
        deps[slug] = {o for o in all_slugs
                      if o != slug
                      and re.search(rf"\b{re.escape(o)}\b", text)}
    ordered: "list[str]" = []
    placed: set = set()
    remaining = list(all_slugs)
    while remaining:
        ready = [s for s in remaining if deps[s] <= placed]
        if not ready:  # cycle — emit the rest in input order, drop nobody
            ordered.extend(remaining)
            break
        for s in ready:
            ordered.append(s)
            placed.add(s)
        remaining = [s for s in remaining if s not in placed]
    return [(s, texts[s]) for s in ordered]


def _harvest_open_lines(text: str) -> "list[str]":
    """Single impl in `state.assemble.harvest_open_lines` (task #5 Step B).
    Carries the agent's working-patch opens into validate_file's compilation
    unit so a probed sub-goal stub elaborates against the SAME open
    namespaces the committed file will — and since Step B the commit side
    carries them too (`assemble_for_commit(carry_opens=…)`)."""
    return assemble.harvest_open_lines(text)


def _merge_opens(content: str, defs_opens: "list[str]",
                 extra_opens: "list[str]") -> "list[str]":
    """Prefix opens for the compilation unit: Defs.lean's file-scope opens
    (raw args, per `intent_mod.defs_opens`) plus `extra_opens` (the session
    patch's own `open ...` lines), each normalized to a full `open ...`
    line, de-duped, and dropping any already present verbatim in `content`
    (so probing the patch itself never doubles its opens)."""
    have = set(_harvest_open_lines(content))
    out: "list[str]" = []
    for o in list(defs_opens) + list(extra_opens):
        line = o if o.startswith("open ") else f"open {o}"
        if line in have or line in out:
            continue
        out.append(line)
    return out


def _proved_sibling_import_lines(
    texts: "list[str]", problem: str, workspace: "Path",
    declared: "set[str]",
) -> "list[str]":
    """The `import Problems.<p>.proofs.L_<slug>` lines the commit-side
    `assemble_for_commit` will auto-inject (proved-sibling auto-fix) for any
    of `texts` — hoisted into the unit's import block instead of mutated
    into the content, so the agent's line numbers (line_map) are untouched
    (task #5 Step C: the probe resolves the same modules commit will,
    killing the false-RED where validate said `unknown identifier` on a
    reference commit would have auto-imported). Best-effort mirror of the
    commit behavior: no DB on disk / any failure → [] (validate must never
    break on this)."""
    db_path = workspace / "asterism.db"
    if not db_path.exists():
        return []
    try:
        conn = db.connect(db_path)
    except Exception:
        return []
    try:
        out: "list[str]" = []
        for t in texts:
            _, added = assemble.inject_sibling_imports(
                conn, t, problem=problem, declared_slugs=declared)
            for s in added:
                line = f"import Problems.{problem}.proofs.L_{s}"
                if line not in out:
                    out.append(line)
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _parity_for(
    content: str, problem: str, workspace: "Path", inlined_slugs: "list[str]",
    header: "dict",
) -> "dict":
    """Does the sandbox's verdict cover what the real build will see?

    The two units are NOT the same object and never can be: the sandbox
    INLINES a referenced sibling's stub so it can elaborate without that
    sibling being built, while commit gives the sibling its own module and
    an `import` line. So comparing unit digests would alarm on every call.
    What must agree is narrower and checkable — every name the sandbox
    resolved through an inlined stub has to be a name the real build can
    resolve too:

      exact       every inlined sibling is PROVED, and commit imports it.
                  The sandbox saw the same declarations lake will.
      conditional at least one inlined sibling is not proved yet, so the
                  sandbox elaborated against `:= by sorry` and the real
                  build will use whatever that goal eventually becomes.
                  Legitimate and common (that is how a batch works) — but
                  it is NOT the same green, and it must not render as one.
      unresolved  an inlined sibling is neither proved nor a declared stub
                  of this batch, and no commit import covers it. That is a
                  framework defect, not the agent's: the probe answered a
                  question the build was never going to be asked.

    This is the handshake #179 needed. That bug hid for a week because
    the divergence surfaced to the AGENT as `Unknown identifier`, which
    reads as "my sibling does not exist" — 37 reports, several saying
    plainly they could not tell that from "wrong approach". A named
    parity verdict costs one field and moves the diagnosis to the side
    that can act on it."""
    if not inlined_slugs:
        return {"state": "exact", "note": "no siblings inlined"}
    imports = " ".join(header.get("imports") or ())
    proved: "list[str]" = []
    conditional: "list[str]" = []
    unresolved: "list[str]" = []
    db_path = workspace / "asterism.db"
    statuses: "dict[str, str]" = {}
    if db_path.exists():
        try:
            conn = db.connect(db_path)
            try:
                for slug in inlined_slugs:
                    row = conn.execute(
                        "SELECT status FROM goals WHERE problem = ? "
                        "AND slug = ?", (problem, slug)).fetchone()
                    if row is not None:
                        statuses[slug] = str(row[0])
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 — parity must never break validate
            statuses = {}
    for slug in inlined_slugs:
        st = statuses.get(slug)
        if st == "proved":
            proved.append(slug)
        elif st is not None:
            conditional.append(slug)
        elif f"L_{slug}" in imports:
            proved.append(slug)
        else:
            unresolved.append(slug)
    if unresolved:
        return {
            "state": "unresolved",
            "framework_parity_error": sorted(unresolved),
            "note": ("the probe resolved these through an inlined stub, but "
                     "the commit unit neither imports them nor knows them as "
                     "goals — your mathematics was not judged against what "
                     "will be built. Report this; it is not your error."),
        }
    if conditional:
        return {
            "state": "conditional",
            "depends_on": sorted(conditional),
            "note": ("elaborated against the DECLARED signature of these "
                     "not-yet-proved siblings; the real build uses whatever "
                     "they become. A clean result here is conditional on "
                     "them proving as declared."),
        }
    return {"state": "exact", "proved_siblings": sorted(proved)}


def _build_compilation_unit(
    content: str, problem: str, workspace: "Path", attempts_dir: "Path",
    extra_opens: "list[str]" = (), own_name: "str | None" = None,
) -> "tuple[str, list[int | None], list[str]]":
    """The SINGLE compilation state every in-spawn LSP tool elaborates:
    framework imports + commit's proved-sibling auto-imports + `Defs.lean`
    file-level opens + referenced `new_<slug>.lean` sibling stubs
    (topologically ordered) + `content`. Since task #5 Step C the unit is
    derived from the SAME `state.assemble` primitives the commit paths run,
    so what the probe elaborates is what commit will land (modulo the
    single-unit fold itself).

    Returns `(merged, line_map, inlined_slugs)`. `line_map[i]` maps merged
    line `i + 1` back to `content`'s 1-indexed line, or `None` for a
    framework-prefix / sibling-region line — so callers translate tool
    inputs (`content` frame → merged frame) and diagnostics (merged frame →
    `content` frame) through one map, killing the prior split where
    `apply_edit`/`goal_at`/`errors_at` saw a sibling-less buffer while
    `validate_file` synthesized a different one. Always returns a real
    `line_map` (even with no siblings: imports + opens are still prefix), so
    every tool remaps uniformly."""
    siblings = _toposort_siblings(
        _collect_referenced_sibling_stubs(attempts_dir, content,
                                          own_name))
    sib_texts = [t for _, t in siblings]
    declared = {s for s, _ in siblings}
    merged, line_map = _inline_sibling_stubs(
        content,
        sib_texts,
        _needed_imports(content, problem, workspace)
        + _proved_sibling_import_lines(
            [content] + sib_texts, problem, workspace, declared),
        # Defs' own namespace rides along with its opens: a bare snippet
        # (no `namespace Problems.…` wrapper) then resolves Defs symbols
        # the way the committed wrapped file does; redundant-but-harmless
        # for content that carries the wrapper (07-18 ×3 + 07-19 ×9).
        opens=_merge_opens(content,
                           intent_mod.defs_opens(workspace, problem)
                           + intent_mod.defs_namespaces(workspace, problem),
                           list(extra_opens)),
    )
    return merged, line_map, [s for s, _ in siblings]


def _commit_header_for(
    content: str, problem: str, workspace: "Path", attempts_dir: "Path",
    extra_opens: "list[str]" = (),
) -> "dict":
    """The exact header lines the framework itself will inject into THIS
    content at commit — `assemble_for_commit`'s framework imports +
    proved-sibling imports + Defs/carried opens, plus the mechanically
    injected intra-batch import edges (task #84, same
    `referenced_batch_slugs` scan the commit side runs). Surfaced in
    validate_file's response so the agent SEES the wrapping (and knows
    not to hand-write it); these lines are already part of the probe's
    compilation unit. Best-effort — a failed sub-derivation just leaves
    its lines out (validate must never break on this)."""
    all_stub_slugs: "list[str]" = []
    try:
        for stub in sorted(attempts_dir.glob("new_*.lean")):
            slug = stub.stem[len("new_"):]
            if slug:
                all_stub_slugs.append(slug)
    except OSError:
        pass
    # batch edges: only slugs content does not itself declare (validating
    # the stub itself must not predict a self-import)
    candidates = [
        s for s in all_stub_slugs
        if not re.search(_DECL_SLUG_RE_TMPL.format(slug=re.escape(s)),
                         content)]
    batch_imports = [
        f"import Problems.{problem}.proofs.L_{s}"
        for s in assemble.referenced_batch_slugs(content, candidates)]
    imports = (
        _needed_imports(content, problem, workspace)
        + batch_imports
        + _proved_sibling_import_lines(
            [content], problem, workspace, set(all_stub_slugs)))
    opens = _merge_opens(content, intent_mod.defs_opens(workspace, problem),
                         list(extra_opens))
    return {"imports": imports, "opens": opens}


def _merged_line_for(
    line_map: "list[int | None] | None", content_line: int,
) -> int:
    """Forward map: a 1-indexed `content_line` (the frame the agent's tool
    args use) → its 1-indexed line in the merged compilation unit. Inverse
    of `line_map` (which is merged → content). Falls back to `content_line`
    unchanged when there is no map or the line isn't a mapped body line
    (e.g. a hoisted import line — tools only query theorem/tactic body
    lines, so the fallback is never hit in practice)."""
    if line_map is None:
        return content_line
    for i, orig in enumerate(line_map):
        if orig == content_line:
            return i + 1
    return content_line


def _compilation_for(meta: SessionMetadata) -> "tuple[str, list[int | None]]":
    """`meta`'s single compilation unit (session content + Defs opens +
    referenced sibling stubs) and its line_map. The one elaboration target
    every claimed-session tool swaps in, so `goal_at` / `errors_at` /
    `apply_edit` see exactly what `validate_file` (and, post-commit, lake)
    do — no more sibling-less live buffer vs synthesized validate world."""
    if meta.kind == "interactive":
        # The serve editor's buffer IS the compilation unit — no
        # framework prefix, no sibling stubs; identity line_map.
        n = meta.file_content.count("\n") + 1
        return meta.file_content, list(range(1, n + 1))
    merged, line_map, _ = _build_compilation_unit(
        meta.file_content, meta.problem, meta.workspace,
        meta.target_path.parent, own_name=meta.target_path.name)
    return merged, line_map


def _remap_inlined_diags(
    formatted: "list[dict]", line_map: "list[int | None]",
) -> "list[dict]":
    """Map each diagnostic's line from the merged elaboration unit back to
    the agent's original content frame via `line_map`. Sibling-region
    lines (`line_map` is None there): drop non-errors — the inlined
    `:= by sorry` stubs each emit a 'declaration uses sorry' warning that
    is pure noise — and tag errors so the agent knows the fault is in a
    cited sibling stub, not its own patch."""
    n = len(line_map)
    out: list[dict] = []
    for f in formatted:
        ln = f.get("line")
        if not isinstance(ln, int) or ln < 1 or ln > n:
            out.append(f)  # outside the map — leave untouched
            continue
        orig = line_map[ln - 1]
        if orig is not None:
            out.append({**f, "line": orig})
        elif f.get("severity") == "error":
            out.append({**f, "message": "[inlined sibling stub] "
                        + str(f.get("message", ""))})
        # else: sibling-region warning/info → drop as noise
    return out


def _summarize_goal(result) -> str:
    if result is None:
        # plainGoal null = position outside any proof/tactic block —
        # NOT str(None): "None" read as a goal named None (owner hit it)
        return "no goals"
    if not isinstance(result, dict):
        return str(result)
    rendered = result.get("rendered")
    if rendered:
        return rendered
    goals = result.get("goals") or []
    if goals:
        return "\n---\n".join(goals)
    return "<no goals — proof complete at this position>"


def _goal_present(result) -> bool:
    """True iff plainGoal returned a live goal (vs an empty/closed state).

    `rendered == "no goals"` is Lean's CLOSED state, not a live goal —
    it is exactly what a query at/inside/after a `sorry` returns, so
    treating that truthy string as present had silently disabled the
    B#4 sorry-fallback (goal_at answered "no goals" on a sorry line
    instead of re-querying the token start for the real goal)."""
    if not isinstance(result, dict):
        return False
    if result.get("goals"):
        return True
    rendered = result.get("rendered")
    return bool(rendered) and str(rendered).strip() != "no goals"


def _sorry_start_col(meta, line: int) -> "int | None":
    """Column (0-indexed) of the first `sorry` token on the agent's 1-indexed
    `line` (its own content frame), or None. goal_at's B#4 fallback re-queries
    here: a `sorry` admits its goal, so plainGoal is empty AT/INSIDE/AFTER the
    token but returns the live goal at its START (verified 2026-06-22)."""
    try:
        lines = meta.target_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not (1 <= line <= len(lines)):
        return None
    m = re.search(r"\bsorry\b", lines[line - 1])
    return m.start() if m else None


# ─── MCP tools ───────────────────────────────────

mcp = FastMCP("lsp")


def _offload_to_thread(fn):
    """Wrap a sync function so it runs in `asyncio.to_thread`.

    Critical for FastMCP `@mcp.tool()` handlers because FastMCP's
    `call_fn_with_arg_validation` calls sync tool bodies INLINE on the
    asyncio event loop (verified 2026-05-12: just `return fn(**args)`
    with no thread pool). For tools that block (here: every one calls
    sync `_acquire_slot` with up to 120s polling), inline execution
    saturates the event loop under concurrent load — `/health` /
    `/register` / `/release` HTTP requests all queue behind in-flight
    tool calls and eventually time out at urllib's budget. The miniF2F
    20-problem wider pilot 2026-05-12 hit this with pool=15: 15
    concurrent claude.exe spawns × ~5 tool calls each saturated the
    loop, daemon-side `urlopen('/register')` timed out at 120s,
    propagated as TimeoutError → cascade classified as
    transient_timeout → spawn re-dispatched → loop.

    Wrapping with this decorator pushes each invocation onto
    `asyncio.to_thread` (default executor, contextvars propagate so
    `_session_ctx.get()` still resolves the X-Asterism-Session header).
    Event loop stays responsive; sync polling no longer blocks other
    handlers.
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    return wrapper


def _stub_fingerprint(attempts_dir: "Path",
                      own_name: "str | None" = None) -> tuple:
    """(name, mtime_ns, size) per SIBLING `new_*.lean`, sorted — the
    sibling half of the compilation unit's identity.

    The session's own target is excluded, and that is not a detail: for
    the Forward seat the target IS a `new_*.lean`, so every `apply_edit`
    write-through moved the fingerprint, cleared the slot's ownership,
    and sent the next read down the cold path to re-elaborate the unit
    it had just elaborated. The fingerprint's job is "did a sibling
    change under me"; the target's own edits are already tracked by the
    mirror two lines below.

    OSError → () (best-effort; an unreadable dir just reads as empty)."""
    try:
        return tuple(sorted(
            (f.name, f.stat().st_mtime_ns, f.stat().st_size)
            for f in attempts_dir.glob("new_*.lean")
            if own_name is None or f.name != own_name))
    except OSError:
        return ()


def _resync_buffer_from_disk(meta: "SessionMetadata") -> "str | None":
    """Adopt the on-disk `target_path` as the source of truth for the
    in-memory `file_content` mirror before any tool reads it.

    Returns an error string when the disk read FAILED (transient lock /
    missing file) — the mirror is then possibly stale. Read-only tools
    may proceed on the stale mirror; `apply_edit` must NOT (its
    write-through would overwrite newer on-disk content with
    stale-based text — the resurrection corruption class).

    Agents edit patch.lean through the `Write` / `Edit` tools too, which
    touch disk directly and bypass apply_edit's mirror update — leaving
    `meta.file_content` stale. Every swap_in tool then didChanges that
    STALE mirror into the slot, so `errors_at` / `goal_at` report phantom
    diagnostics at line numbers that no longer exist on disk, and
    `apply_edit` computes its line splice against stale text
    (agent_feedback T1, ~12 reports — the run's highest-frequency
    friction). Disk is never staler than the mirror (apply_edit, the only
    mirror writer, writes disk in the same breath at write-through), so
    unconditionally adopting disk on mismatch is safe and makes disk the
    single source of truth."""
    # Sibling-stub freshness rides the same resync (agent_feedback #4a):
    # a stub written AFTER the last elaboration changes the merged unit;
    # invalidate slot ownership so the next acquire re-elaborates.
    fp = _stub_fingerprint(meta.target_path.parent,
                           meta.target_path.name)
    if fp != meta.stub_fingerprint:
        meta.stub_fingerprint = fp
        for _slot in _state.workers:
            if _slot.claimed_by == meta.pipeline_id:
                _slot.content_pipeline_id = None
                break
        _log_for(meta, {"event": "sibling_stub_resync", "stubs": len(fp)})

    try:
        disk = meta.target_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"target file unreadable during resync: {e}"
    if disk != meta.file_content:
        meta.file_content = disk
        # Invalidate the claimed slot's content ownership: the hot path in
        # `_acquire_slot` keys "slot already has our content" on PIPELINE
        # identity, so after an external Write/Edit the refreshed mirror
        # was never didChange'd in and `errors_at`/`goal_at` reported the
        # PREVIOUS elaboration until some no-op apply_edit (~8 agent
        # reports, sphere_homology 2026-07-04/05). Clearing the marker
        # forces the next swap_in acquire through the cold_warmup
        # didChange + wait_for_diagnostics. Safe lock-free: a session's
        # tool calls are serial, so no concurrent op holds this slot.
        for _slot in _state.workers:
            if _slot.claimed_by == meta.pipeline_id:
                _slot.content_pipeline_id = None
                break
        _log_for(meta, {"event": "buffer_resync_from_disk",
                        "disk_lines": disk.count("\n") + 1})


_SCOPE_OPEN_RE = re.compile(
    # `mutual` is `end`-closed too. Without it a mutual block's `end`
    # counted as a closer with no opener and the balance went negative —
    # a false "one `end` too many" on a correct file (2026-08-10).
    r"^\s*(?:noncomputable\s+)?(?:namespace|section|mutual)\b")
_SCOPE_END_RE = re.compile(r"^\s*end\b")


def _scope_balance(text: str) -> int:
    """`namespace`/`section` openers minus `end` closers.

    Purely syntactic, which is the point: it is correct the instant the
    splice lands, whereas the elaborator's diagnostics in the same
    response may still describe the PREVIOUS version. Two agents in one
    run replaced a whole file, dropped its `end <namespace>`, and only
    learned about it a round-trip later (2026-08-02 feedback x2)."""
    opens = closes = 0
    for line in text.split("\n"):
        if _SCOPE_OPEN_RE.match(line):
            opens += 1
        elif _SCOPE_END_RE.match(line):
            closes += 1
    return opens - closes


@mcp.tool(structured_output=False)
@_offload_to_thread
def apply_edit(edits: list = None) -> str:
    """Apply one or more anchored edits to the target Lean file.

    Each edit names the TEXT it acts on, not a line number:

        [{"replace": "<exact old text>", "with": "<new text>"},
         {"replace_between": ["<from>", "<to>"], "with": "<new text>"},
         {"insert_after": "<anchor>", "text": "<new text>"}]

    Anchors must match exactly and appear exactly once. For
    `replace_between` the closing anchor need only be unique AFTER the
    opening one — use it to swap a whole tactic block without quoting
    it. BOTH anchors are part of the replaced span: `with` is the
    complete new text, and anything you want kept must be in it. So
    anchor on your OWN block's first and last lines, never on the
    neighbouring declaration — an anchor placed on the next `theorem`
    line deletes that line with the span. Ambiguity is refused rather
    than resolved to the first match: guessing is what silently
    swallowed the lines between the intended close and a later one
    (2026-08-11). `insert_after` splices immediately after the anchor;
    when the anchor ends its line and `text` brings no newline of its
    own, the text starts on a new line (so an inserted import or
    comment never glues onto the anchor's last token).

    If any anchor fails to resolve, NOTHING is applied: the response says
    which edit and how to repair it, the file is unchanged, and your
    other anchors are still valid on resubmission.

    Args:
      edits: list of edit objects (see above).
    """
    _recv_ts = _ts_now()
    meta = _current_session()
    # A refusal is an outcome, and it was the only one that left no
    # trace: `_log_for` sits past every early return below, so when an
    # agent and the framework disagreed about whether an edit had landed
    # there was nothing to consult (08-11, unresolvable to this day).
    # Each refusal now logs before it returns. The no-session branch
    # cannot: there is no session to log against.
    if meta is None:
        return json.dumps({"error":
            "no session — X-Asterism-Session header missing or unknown",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    t0 = time.perf_counter()

    # External Write/Edit may have advanced disk past the mirror; splice
    # against the current on-disk text, not a stale buffer (T1). A
    # FAILED resync aborts the edit: writing through a possibly-stale
    # mirror would overwrite newer on-disk content (resurrection
    # corruption, agent_feedback 2026-07-18).
    _resync_err = _resync_buffer_from_disk(meta)
    if _resync_err:
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps({"error": (
            f"{_resync_err}; edit aborted — the buffer may be stale and "
            "writing through it could clobber newer on-disk content. "
            "Retry, or Read the file and use Write."),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not edits:
        return _arg_help(
            "apply_edit",
            'the parameter is `edits`, a list \u2014 e.g. '
            'apply_edit(edits=[{"replace": "by norm_num", "with": "by simp"}])')
    try:
        spans = _edits.resolve(meta.file_content, edits)
    except _edits.EditError as exc:
        # Refusal, PRE-elaboration: the file is untouched and the batch
        # cost milliseconds instead of a corrupted proof discovered a
        # round-trip later. That is the whole point of anchoring \u2014 a line
        # number has nothing to check itself against, so a stale one
        # spliced silently (42 agent reports in the week to 2026-08-10).
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps(
            {"edit": "rejected \u2014 file unchanged", **exc.as_dict(),
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)

    replaced_text = " | ".join(
        _echo_removed(meta.file_content[s.start:s.end])
        for s in spans if not s.is_insert) or "(insert only)"
    new_content = _edits.apply_spans(meta.file_content, spans)
    _hb = _heartbeat_gate(meta, new_content)
    if _hb is not None:
        # Refused PRE-write, like an unresolvable anchor: the file is
        # untouched and the cost was milliseconds. Asking after the
        # write would be asking after the bill.
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps(
            {"edit": "held — file unchanged", "heartbeat_budget": _hb,
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)
    meta.hb_limit = _hb_declared(new_content) or meta.hb_limit
    new_lines = new_content.split(chr(10))
    # Where each edit LANDED, measured on the produced file. Line numbers
    # are output only: the tool measured them, so they cannot be stale
    # the way a caller-supplied one could.
    _shift = 0
    _regions = []
    for s in sorted(spans, key=lambda x: x.start):
        lo = _edits.line_of(new_content, s.start + _shift)
        hi = _edits.line_of(new_content, s.start + _shift + len(s.new_text))
        _regions.append((lo, hi))
        _shift += len(s.new_text) - (s.end - s.start)
    start_line = _regions[0][0]
    end_line = _regions[-1][1]

    # Structural balance, reported UNCONDITIONALLY as a number. The old
    # version warned only when THIS edit broke a previously balanced
    # file, so once a file was unbalanced every later edit went quiet \u2014
    # including the one that added a second stray `end`. Computing a
    # value and then gating it into silence is the "knows but flattens"
    # shape this codebase keeps finding.
    _scope_warn = None
    _bal_after = _scope_balance(new_content)

    # Metaprogramming gate — BEFORE the mirror/disk write-through, so a
    # blocked edit leaves neither the buffer nor the file carrying it.
    _mp = _metaprog_error(new_content, meta.target_path.name)
    if _mp is not None:
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps({"error": _mp, "edit": "rejected — file unchanged",
                           "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()},
                          ensure_ascii=False)

    # Echo the post-edit region with CURRENT 1-indexed line numbers (±2 lines
    # of context) so the agent re-anchors from ground truth after every edit
    # instead of tracking line positions itself. Stale positions — line
    # numbers that drifted when a prior edit changed the line count — are what
    # made a later apply_edit splice at the wrong range (duplicated signature,
    # dropped `:= by`, clobbered `have`): the recurring corruption in
    # agent_feedback (C1). Seeing the actual result makes a misfire obvious
    # immediately rather than via a confusing downstream diagnostic.
    _echo = []
    for lo, hi in _regions:
        a, b = max(1, lo - 2), min(len(new_lines), hi + 2)
        _echo += [f"{i}: {new_lines[i - 1]}" for i in range(a, b + 1)]
        _echo.append("")
    # The TAIL, always. Two of the loudest failure reports were a dropped
    # `end` and a duplicated proof body, both at end-of-file, where an
    # echo anchored on the edited region never looks.
    _tail_from = max(1, len(new_lines) - 2)
    _echo.append(f"--- end of file ({len(new_lines)} lines) ---")
    _echo += [f"{i}: {new_lines[i - 1]}"
              for i in range(_tail_from, len(new_lines) + 1)]
    post_edit_region = "\n".join(_echo)

    # Locked-signature tripwire (warning, not a block): the commit gate
    # byte-compares the seeded `s<sid>` signature, so an edit touching
    # it — usually via a drifted range — is doomed at commit. Same
    # helper as validate_file's submission mirror.
    _locked_warn = _locked_signature_submission(
        new_content, meta.target_path.parent)
    if _locked_warn is not None and _locked_warn.get("ok", True):
        _locked_warn = None

    # Disk + mirror hold the RAW patch (write-through for the framework
    # cascade); the slot elaborates the MERGED compilation unit (patch +
    # Defs opens + referenced sibling stubs) so cited siblings resolve and
    # the goal / diagnostics match validate_file and post-commit lake.
    # Mirror must be set before building the unit.
    meta.file_content = new_content
    backend = _state.backend
    # apply_edit overwrites slot content anyway → skip swap-in.
    with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
        with _elab_gate(slot.slot_uri):
            slot.file_version += 1
            backend.clear_diagnostics(slot.slot_uri)
            merged, line_map = _compilation_for(meta)
            backend.did_change_full(slot.slot_path, merged,
                                    slot.file_version)
            # `textDocument/waitForDiagnostics` blocks server-side until
            # the doc reaches our version, the reporter has flushed all
            # publishDiagnostics for it, and all command snapshots have
            # elaborated. Replaces the prior fileProgress + 3s-settle
            # polling, which over-waited by ~3s on every tool call.
            converged = _diags_converged(backend, slot)
        diags = backend.diagnostics_for(slot.slot_uri)
        q_line = _merged_line_for(line_map, start_line)
        try:
            result = backend.plain_goal(slot.slot_path,
                                         line=q_line - 1, character=2,
                                         timeout=15)
            goal_text = _summarize_goal(result)
        except Exception as e:
            goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
        # The goal at the END of what was just written (2026-08-06
        # feedback ×6, both arms): after a multi-line replacement the
        # agent wants the state at the new `sorry` / next open goal, and
        # `goal_at_edit_start` is the state at the top of the region —
        # so every tactic iteration paid a second `goal_at` round-trip
        # against a ~46s elaboration latency. Skipped when the edit is a
        # single line (both ends are the same query) or a deletion.
        goal_end_text: "str | None" = None
        end_line_after = _regions[-1][1]
        if end_line_after > start_line:
            try:
                q_end = _merged_line_for(line_map, end_line_after)
                goal_end_text = _summarize_goal(backend.plain_goal(
                    slot.slot_path, line=q_end - 1, character=2,
                    timeout=15))
            except Exception as e:
                goal_end_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
        # Slot now has this pipeline's NEW content didChanged in.
        slot.content_pipeline_id = meta.pipeline_id
        slot.line_map = line_map

    # Write through to disk (RAW patch) so the framework cascade reads the
    # agent's edits.
    meta.target_path.write_text(new_content, encoding="utf-8")

    # Diagnostics are in the merged frame → remap to the agent's content
    # frame (drop sibling-region sorry noise, tag sibling-region errors).
    formatted = [_format_diag(d) for d in diags]
    if line_map is not None:
        formatted = _remap_inlined_diags(formatted, line_map)

    # Citation mirror on the live-file path too (2026-07-19, user call):
    # the predictor lived only in validate_file, but agents editing
    # patch.lean via apply_edit ship without ever calling validate — the
    # a5 run burned six commits on cite_unproved_sibling rejects the
    # mirror would have predicted. Cheap (a few classify queries, only
    # when the content carries Problems-imports); surfaced only when
    # something is wrong, so clean edits stay noise-free.
    _own_stubs = {p.stem[len("new_"):]
                  for p in meta.target_path.parent.glob("new_*.lean")}
    _cite = _citation_submission(
        new_content, meta.problem, meta.workspace, _own_stubs,
        kind=meta.kind)
    _n_diags = len(formatted)
    formatted = _collapse_repeats(formatted)
    response = {
        "edit": (f"applied {len(spans)} edit(s) at lines "
                 + ", ".join(f"{a}-{b}" for a, b in _regions)
                 + f"; file is now {len(new_lines)} lines"),
        # Always a number, never a conditional warning: see the note at
        # the splice above.
        "scope_balance": _bal_after,
        "replaced_text": replaced_text,
        "post_edit_region": post_edit_region,
        "goal_at_edit_start": goal_text,
        "diagnostics": formatted,
        **({"goal_at_edit_end": goal_end_text,
            "goal_at_edit_end_note": _GOAL_AT_EDIT_END_NOTE}
           if goal_end_text is not None else {}),
        "diagnostic_count": _n_diags,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    _note_diagnostics(meta, formatted, time.perf_counter() - t0)
    if not converged:
        response["elaborating"] = True
        response["warning"] = _ELABORATING_WARNING
    if _cite is not None and _cite.get("issues"):
        response["citation"] = _cite
    if _locked_warn is not None:
        response["locked_signature"] = _locked_warn
    if _bal_after != 0:
        response["scope_warning"] = (
            f"{abs(_bal_after)} unclosed `namespace`/`section`/`mutual` — "
            f"add the matching `end`" if _bal_after > 0 else
            f"{abs(_bal_after)} more `end` than there are openers")
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "apply_edit",
                    "args": {"edits": len(spans),
                             "kinds": [s.kind for s in spans]},
                    "duration_s": dur,
                    "slot_kind": _slot_kind, "converged": converged,
                    "diagnostic_count": len(diags)})
    return json.dumps(response, ensure_ascii=False)


#: Same rule as `knowledge/mcp_tools`: NO TOOL ON THIS SERVER HAS A
#: REQUIRED PARAMETER. A model that guesses a parameter name wrong makes
#: FastMCP's pydantic model raise, and on the Antigravity CLI a raising
#: MCP tool stamps the whole envelope `status: ERROR` — killing the run
#: AND the `--resume` turn that would have collected its feedback.
#: Measured 2026-08-10: `inspect(inspect_requests=…)` cost six spawns
#: their feedback records in one fifteen-minute window. Optional
#: parameters plus a teaching string turn that into one recoverable
#: round-trip. Enumerating plausible aliases is NOT the fix — the next
#: model invents a new name.
def _arg_help(tool: str, hint: str) -> str:
    return json.dumps({"error": f"{tool}: {hint}"}, ensure_ascii=False)


@mcp.tool(structured_output=False)
@_offload_to_thread
def goal_at(line: int = 0, col: int = 0) -> str:
    """Get the Lean proof goal state at a specific position.

    Args:
      line: 1-indexed line number.
      col:  0-indexed character column.
    """
    if not line:
        return _arg_help(
            "goal_at",
            "the parameters are `line` (1-indexed) and `col` (0-indexed), "
            "e.g. goal_at(line=42, col=2)")
    _recv_ts = _ts_now()
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    t0 = time.perf_counter()
    backend = _state.backend
    # Pick up any external Write/Edit before swap_in didChanges the
    # mirror into the slot, so the goal query sees current disk (T1).
    _resync_buffer_from_disk(meta)
    # The Write/Edit tools bypass apply_edit's gate — this is where such
    # content would first reach an elaborator, so it is scanned here.
    _mp = _metaprog_error(meta.file_content, meta.target_path.name)
    if _mp is not None:
        return json.dumps({"error": _mp, "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()}, ensure_ascii=False)
    resolved_at_sorry: "int | None" = None
    with _acquire_slot(meta, swap_in=True) as (slot, _slot_kind):
        # The slot holds the merged compilation unit; the agent's `line`
        # is in its own content frame, so translate to the merged frame.
        q_line = _merged_line_for(slot.line_map, line)
        # Same honesty signal as errors_at/apply_edit (#106; 07-19: a
        # goal_at blocked ~2min and the agent could not tell timeout
        # from truth): an unconverged elaboration must say so.
        converged = _diags_converged(backend, slot)
        try:
            result = backend.plain_goal(
                slot.slot_path, line=q_line - 1, character=col, timeout=15
            )
            # B#4 fallback: a query at/inside/after a `sorry` token sees the
            # goal already admitted → "no goals". Retry once at the token's
            # START (where the goal is still live — verified 2026-06-22) so
            # peeking at an unedited stub (the documented Builder step 1, and
            # any mid-proof `sorry`) returns the real goal, not a misleading
            # "proof complete".
            if not _goal_present(result):
                s_col = _sorry_start_col(meta, line)
                if s_col is not None and s_col != col:
                    retry = backend.plain_goal(
                        slot.slot_path, line=q_line - 1, character=s_col,
                        timeout=15)
                    if _goal_present(retry):
                        result, resolved_at_sorry = retry, s_col
            goal_text = _summarize_goal(result)
        except Exception as e:
            goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "goal_at",
                    "args": {"line": line, "col": col},
                    "duration_s": dur,
                    "slot_kind": _slot_kind})
    resp = {"line": line, "col": col, "goal": goal_text,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()}
    if not converged:
        resp["elaborating"] = True
        resp["warning"] = _ELABORATING_WARNING
    if resolved_at_sorry is not None:
        resp["note"] = ("queried position had no goal (a `sorry` admits its "
                        "goal); showing the goal at the `sorry` token "
                        f"(col {resolved_at_sorry})")
    return json.dumps(resp, ensure_ascii=False)


def _diags_converged(backend, slot) -> bool:
    """True iff Lean finished elaborating the slot's current version and
    flushed its publishDiagnostics — i.e. `diagnostics_for` is the FINAL
    answer. False (wait expired / client error) means the stash is a
    snapshot of an unfinished elaborate: an empty list is NOT "clean",
    it is "no news yet". Every tool that returns diagnostics to the
    agent must surface this bit instead of letting a timeout masquerade
    as a clean file (the `errors_at`-fake-clean class, 2026-07-18)."""
    try:
        backend.wait_for_diagnostics(slot.slot_uri, slot.file_version,
                                     timeout=120)
        return True
    except (TimeoutError, RuntimeError):
        return False


#: `set_option maxHeartbeats N`. Lean syntax, not prose — the value is
#: a structured signal the way a decision kind is.
_HB_SET_RE = re.compile(r"set_option\s+maxHeartbeats\s+(\d+)")
_HB_TIMEOUT_MARK = "maximum number of heartbeats"
#: Above this, the gate asks once. NOT a limit on what may land: 11 of
#: this workspace's proved bricks sit at 4M — `_strategy_s24405` among
#: them, a sibling of the strategy this gate was written for — and their
#: comments name the same technique ("large literal-set peeling needs
#: the extra budget"). A big budget is normal practice here; being SLOW
#: about it while blind to the cost is what is not.
_HB_ASK_ABOVE = 1_000_000


def _hb_rank(limit: "int | None") -> float:
    """Order two budgets. `0` means UNLIMITED in Lean, so it sorts above
    every finite value rather than below all of them; `None` is "never
    set", i.e. Lean's own default."""
    if limit is None:
        return 200_000.0
    return float("inf") if limit == 0 else float(limit)


def _hb_declared(content: str) -> "int | None":
    """The largest budget this content asks for, or None."""
    found = [int(m.group(1)) for m in _HB_SET_RE.finditer(content or "")]
    return max(found, key=_hb_rank) if found else None


def _note_diagnostics(meta: SessionMetadata, diags: list,
                      elapsed_s: float) -> None:
    """Remember what a diagnostics call cost and whether Lean gave up on
    a heartbeat budget. Both are inputs the gate quotes back."""
    meta.hb_last_check_s = elapsed_s
    for d in diags or []:
        if _HB_TIMEOUT_MARK in str(d.get("message", "")):
            meta.hb_saw_timeout = True
            return


def _heartbeat_gate(meta: SessionMetadata, content: str) -> "str | None":
    """Ask once before a write buys a slower feedback loop — or None.

    Raising `maxHeartbeats` does not make an elaboration converge; it
    buys a LATER refusal, and every diagnostics call in the session pays
    the difference. Measured 2026-08-12 on g7554: 200k → 1M → 4M took
    the check latency 20s → 96s → 240s, the same three positions timed
    out at every budget, and the spawn died on its 30-minute wall with
    the file never once compiling. Its own last words were "still
    elaborating — let's wait and re-check".

    Two triggers, union, because each is blind where the other sees:
      (a) the budget is large — catches a file that opens at 4M and
          never learns why its checks take minutes;
      (b) the budget goes UP after this session has already been shown a
          heartbeat timeout — catches the 200k→1M step, which (a) would
          sleep through, and it is deliberately not keyed on the timing
          out LINE: an agent's own edits shift line numbers, so an
          exact-position match would mostly miss.

    Confirmation is the identical write resent. That is why the message
    has to SAY so: an agent whose write was refused will otherwise edit
    the content, changing the hash, and read the gate as random."""
    declared = _hb_declared(content)
    if declared is None:
        return None
    # BOTH triggers require this write to RAISE the budget. Without it,
    # (a) re-asks on every edit while the file sits at 4M — each edit is
    # a new content hash — which is a nag, not a gate.
    raised = _hb_rank(declared) > _hb_rank(meta.hb_limit)
    if not raised:
        return None
    escalating = meta.hb_saw_timeout
    if not (escalating or _hb_rank(declared) > _HB_ASK_ABOVE):
        return None
    key = hashlib.sha1((content or "").encode("utf-8")).hexdigest()
    if key in meta.hb_confirmed:
        return None
    meta.hb_confirmed.add(key)

    budget = "UNLIMITED" if declared == 0 else f"{declared:,}"
    cost = (f" Your last diagnostics call took "
            f"{meta.hb_last_check_s:.0f}s" if meta.hb_last_check_s else "")
    if escalating:
        was = ("Lean's default" if meta.hb_limit is None
               else "UNLIMITED" if meta.hb_limit == 0
               else f"{meta.hb_limit:,}")
        head = (
            f"This session has already been shown a heartbeat timeout, and "
            f"this write raises the budget from {was} to {budget}. A "
            f"timeout is Lean saying the elaboration does not converge — a "
            f"larger budget moves the same refusal further away and makes "
            f"every check until then slower.{cost}, against a spawn budget "
            f"measured in minutes. What works instead: bound the quantity "
            f"rather than evaluating it, or lift the heavy step into its "
            f"own `new_<slug>.lean` with a small context and cite it. If "
            f"neither fits, the claim itself is too coarse for one check "
            f"— decline with the cut you would make, and the review loop "
            f"will re-plan it as smaller bricks.")
    else:
        head = (
            f"This file asks for {budget} heartbeats. That is allowed and "
            f"normal here — several proved bricks in this workspace use "
            f"it — but every diagnostics call in this session now waits "
            f"proportionally longer before Lean will answer.{cost}. Budget "
            f"your remaining checks accordingly.")
    return head + (" — Resend this identical write to confirm and it will "
                   "be applied; changing the content asks again.")


_ELABORATING_WARNING = (
    "Lean has NOT finished elaborating this file (120s wait expired) — "
    "the diagnostics here are INCOMPLETE and a count of 0 does NOT mean "
    "the file is clean. Re-run this tool to check again."
)

# `goal_at_edit_end` is a CURSOR SNAPSHOT at the edited region's end
# position, not a verdict on the file — ~38 agent reports treated a
# non-empty goal there as "proof incomplete" and burned a turn
# cross-checking with validate_file, which already answers that
# question. Attached as a sibling key (never inline in the value
# itself) so the field stays machine-parseable while still teaching.
_GOAL_AT_EDIT_END_NOTE = (
    "this is the goal state AT THE CURSOR after the edited region, not "
    "a verdict on the whole file — an open goal here is expected mid-proof. "
    "Use `diagnostics` (or `validate_file`) to know whether the FILE is done."
)


@mcp.tool(structured_output=False)
@_offload_to_thread
def errors_at(line: int | None = None) -> str:
    """Get current diagnostics for the file.

    Args:
      line: Optional 1-indexed line. If set, return only diagnostics
            on that line. If None, return all.
    """
    _recv_ts = _ts_now()
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    t0 = time.perf_counter()
    backend = _state.backend
    # Pick up any external Write/Edit before swap_in didChanges the
    # mirror into the slot, so diagnostics track current disk (T1).
    _resync_buffer_from_disk(meta)
    # Same disk-side entry as goal_at (Write/Edit bypass apply_edit).
    _mp = _metaprog_error(meta.file_content, meta.target_path.name)
    if _mp is not None:
        return json.dumps({"error": _mp, "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()}, ensure_ascii=False)
    with _acquire_slot(meta, swap_in=True) as (slot, _slot_kind):
        converged = _diags_converged(backend, slot)
        diags = backend.diagnostics_for(slot.slot_uri)
        formatted = [_format_diag(d) for d in diags]
        slot_line_map = slot.line_map
    # Diagnostics come from the merged compilation unit; remap their lines
    # back to the agent's content frame (and drop sibling-region sorry
    # noise / tag sibling-region errors) before any line filter.
    if slot_line_map is not None:
        formatted = _remap_inlined_diags(formatted, slot_line_map)
    if line is not None:
        formatted = [f for f in formatted if f["line"] == line]
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "errors_at",
                    "args": {"line": line}, "duration_s": dur,
                    "slot_kind": _slot_kind, "converged": converged,
                    "returned_count": len(formatted)})
    # `elapsed_s` as a number, not two timestamps to subtract: a worker
    # blind to what a check costs cannot budget its checks, and this one
    # ran eight of them at 92s average against a 30-minute wall
    # (g7554, 2026-08-12).
    _elapsed = time.perf_counter() - t0
    _note_diagnostics(meta, formatted, _elapsed)
    response = {"diagnostics": formatted, "count": len(formatted),
                "elapsed_s": round(_elapsed, 1),
                "_server_recv_ts": _recv_ts,
                "_server_send_ts": _ts_now()}
    if not converged:
        response["elaborating"] = True
        response["warning"] = _ELABORATING_WARNING
    return json.dumps(response, ensure_ascii=False)


# ── validate_file submission mirror (#8 / P2) ────────────────────────
# The commit-time gates an agent's patch must also pass, surfaced pre-commit
# so a validate≠commit disagreement no longer costs a whole retry round.
# Returned in a `submission` block kept SEPARATE from Lean `diagnostics`
# (elaboration result vs framework policy — the user's separation instinct,
# in one tool call so the agent's existing validate_file loop catches it).

# Formerly hand-maintained `_GW_*` copies of the pipeline regexes ("kept
# local so the gateway does not import the heavy pipeline package") — now
# the SAME objects via the state-layer leaf `state.assemble` (task #5 Step
# A): the pipeline re-exports these under its historical names, so the two
# sides structurally cannot drift. The citability VERDICT stays with the
# shared SoT `db.classify_cited_slug`.
_GW_PROBLEM_IMPORT_RE = assemble.PROBLEM_IMPORT_RE
_GW_THEOREM_RE = assemble.THEOREM_LINE_RE
_GW_SORRY_STUB_RE = assemble.SORRY_STUB_RE
_GW_SLUG_RE = assemble.SLUG_RE
_GW_DECL_HEAD_RE = assemble.DECL_HEAD_RE


def _gw_leading_comments(text: str) -> str:
    """`--` comment lines before the first declaration head (ANY kind — a
    data goal's patch is a `def`) — presence-mirror of
    `pipeline._extract_leading_comments` (commit's annotation source)."""
    m = _GW_DECL_HEAD_RE.search(text)
    region = text[:m.start()] if m else text
    return "".join(ln for ln in region.splitlines(keepends=True)
                   if ln.strip().startswith("--"))


def _citation_submission(content: str, problem: str, workspace: "Path",
                         declared: "set[str]",
                         kind: "str | None" = None) -> "dict | None":
    """Classify each `import Problems.<problem>.proofs.L_<slug>` in `content`
    via the shared `db.classify_cited_slug` SoT so validate_file predicts the
    commit citation gate. `declared` = sibling stubs inlined this call (legit
    — skip). Best-effort: any DB failure → None (must never break validate).

    `kind` (the session's pipeline) sharpens the non-proved verdict: a
    Backward / Formalizer commit auto-links a cited open sibling as a
    strategy sub-goal; Builder/Forward commits have no
    auto-link — the citation dies at their axiom gate (transitive sorryAx),
    so for those pipelines the mirror reports it as the ERROR it is instead
    of the historical one-size warn (feedback family: agents trusted the
    warn, burned the round trip).

    Task #123 retired the stub-count sharpening: commit auto-links a cited
    unproved sibling whether or not the patch declares stubs (the wait edge,
    not the stub, is what defers verification), so a stub-less Backward /
    Formalizer patch now gets the same auto-link warn as a decomposition."""
    try:
        conn = db.connect(workspace / "asterism.db")
    except Exception:
        return None
    issues: "list[dict]" = []
    try:
        seen: "set[str]" = set()
        for m in _GW_PROBLEM_IMPORT_RE.finditer(content):
            if m.group(1) != problem:
                continue
            slug = m.group(2)
            if slug in seen or slug in declared:
                continue
            seen.add(slug)
            try:
                _gid, status, orphan = db.classify_cited_slug(
                    conn, problem=problem, slug=slug, workspace=workspace)
            except Exception:
                continue
            if status == "proved":
                continue
            if status is None:
                if orphan:
                    issues.append({
                        "slug": slug, "status": "orphan", "severity": "error",
                        "hint": "stub on disk with no tracked goal — citing it "
                                "imports a sorry; declare your own "
                                "new_<slug>.lean sub-goal instead"})
                # else: typo / cross-problem — lake's unknown-identifier covers it
                continue
            if status in transitions.GOAL_FAILED_TERMINALS:
                issues.append({
                    "slug": slug, "status": status, "severity": "error",
                    "hint": "hard-terminal; re-declare its statement as your "
                            "own new_<slug>.lean sub-goal stub"})
            else:  # open / attempting / pending_strategist_review / shelved
                if (kind or "").lower() in ("builder", "forward"):
                    issues.append({
                        "slug": slug, "status": status, "severity": "error",
                        "hint": f"non-proved: a {kind} commit has no "
                                "auto-link — the citation imports a sorry "
                                "and dies at the axiom gate; cite proved "
                                "siblings only, or (forward) declare the "
                                "fact as your own lemma"})
                else:
                    issues.append({
                        "slug": slug, "status": status, "severity": "warn",
                        "hint": "non-proved: commit auto-links it as a "
                                "dependency and your strategy waits until "
                                "it proves — legitimate, but rejected if it "
                                "is an ancestor of your goal or restates it"})
    finally:
        conn.close()
    return {"ok": not any(i["severity"] == "error" for i in issues),
            "issues": issues}


def _annotation_submission(content: str, is_mint: bool = False) -> "dict":
    """Mirror commit's `agent_no_annotation` gate: a final patch needs a
    leading `--` comment block. Applies only when `content` is a real
    submission (declares SOMETHING — any decl kind, a data goal's patch
    is a `def`/`structure` — with a non-sorry body); probing a
    `:= by sorry` stub is not a submission, so skip (`checked: False`).
    Historically theorem-only, so a def patch validated with
    `checked: false` and no explanation (feedback family: the agent
    couldn't tell whether the gate applied).

    The mint arm has no such gate since the Forward-rationale comment
    was retired (07-29) — nagging for it there is a false requirement."""
    if is_mint:
        return {"checked": False,
                "note": "mint commits need no annotation"}
    if (not _GW_DECL_HEAD_RE.search(content)
            or _GW_SORRY_STUB_RE.search(content)):
        # Explain the skip (07-19 ×2: agents read a bare
        # `checked: false` on a stub as "annotation maybe required").
        # The forward warning is deliberate (autopsy 2026-08-24): a
        # silent skip here let a WIP patch sail to commit and only
        # then learn the annotation was due.
        return {"checked": False,
                "note": "no annotation needed while the body is sorry "
                        "(a sub-goal stub never needs one) — the FINAL "
                        "patch will: replace the `-- STRATEGY:` "
                        "placeholder when the proof closes"}
    ok = bool(assemble.strip_annotation_placeholder(
        _gw_leading_comments(content)).strip())
    return {"checked": True, "ok": ok,
            "note": "" if ok else
            "FINAL patch only: replace the `-- STRATEGY:` placeholder "
            "with a leading -- comment before commit "
            "(agent_no_annotation; the unreplaced placeholder does not "
            "count). Ignore on exploratory probes."}


def _locked_signature_submission(content: str,
                                 attempts_dir: "Path") -> "dict | None":
    """D-lite mirror of the Backward commit signature gate: the strategy
    skeleton's `<kind> s<sid> <binders> : <type>` is LOCKED — commit
    byte-compares it (whitespace-normalized) and rejects any edit, even a
    mathematically equivalent rewrite that elaborates fine. Backward seeds
    the normalized signature into `_locked_signature.txt`; compare the
    content's current signature against it via the SAME shared helpers.
    None when there is no seed file (non-Backward session) or `content`
    doesn't mention the locked name (probing a sub-goal stub, not the
    patch)."""
    f = attempts_dir / "_locked_signature.txt"
    try:
        if not f.is_file():
            return None
        locked = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    parts = locked.split()
    name = parts[1] if len(parts) >= 2 else ""
    if not name or not re.search(rf"\b{re.escape(name)}\b", content):
        return None
    agent_sig = assemble.normalize_signature(
        assemble.signature_prefix(content, name))
    if agent_sig == locked:
        return {"checked": True, "ok": True}
    return {
        "checked": True, "ok": False,
        "hint": (f"the `{name}` signature is LOCKED — commit rejects ANY "
                 "edit to it (even an equivalent rewrite that elaborates "
                 "fine); restore it exactly and make changes after `:= by` "
                 "only"),
        "locked": locked,
        "current": agent_sig or "(declaration head not parseable)",
    }


def _stale_olean_submission(content: str, problem: str,
                            workspace: "Path") -> "dict | None":
    """D-lite staleness warning: this probe resolves committed siblings via
    their on-disk build products; if a cited `L_<slug>`'s source is newer
    than its .olean (or the .olean is missing), the probe's verdict for
    that citation is based on a stale world — commit's real build will
    recompile. Detection only (whether the recompile changes the verdict
    needs the real build); None when content cites nothing."""
    cites = [m.group(2) for m in _GW_PROBLEM_IMPORT_RE.finditer(content)
             if m.group(1) == problem]
    if not cites:
        return None
    prel = Path(*problem.split(".")) if "." in problem else Path(problem)
    issues: "list[dict]" = []
    for slug in cites:
        src = (workspace / "Problems" / prel / "proofs" / f"L_{slug}.lean")
        if not src.exists():
            continue                    # citation gate reports missing goals
        rel = Path("Problems") / prel / "proofs" / f"L_{slug}.olean"
        oleans = [workspace / ".lake" / "build" / "lib" / "lean" / rel,
                  workspace / ".lake" / "build" / "lib" / rel]
        try:
            fresh = any(o.exists() and o.stat().st_mtime >= src.stat().st_mtime
                        for o in oleans)
        except OSError:
            continue
        if not fresh:
            issues.append({
                "slug": slug,
                "note": (f"L_{slug}.lean is newer than its .olean (or the "
                         ".olean is missing) — this probe's verdict for the "
                         "citation is based on a stale build; commit will "
                         "recompile it"),
            })
    return {"ok": not issues, "issues": issues}


def _slug_collision_submission(stub_map: "dict[str, str]", problem: str,
                               workspace: "Path") -> "dict | None":
    """Predict the commit-only slug fate for BATCH STUBS (agent_feedback
    #4b: LSP all-green, bounced at commit): a `new_<slug>.lean` whose
    slug already exists as a goal in this problem either auto-suffixes
    to `_2` at commit (breaking the decl-name match every citation in
    the batch relies on) or — when the twin is a strict ancestor with an
    identical head — dies as `circular_decomposition`.

    FORK (agent_feedback 2026-07-11, 12 contradiction reports): when the
    colliding twin is SHELVED and the stub's statement is byte-identical
    (normalized signature match — display heuristic only; the commit
    authority is the kernel defeq/reuse path), the SANCTIONED move is to
    keep the name and let commit dedupe-link to the twin — so the entry
    downgrades to `info` instead of scaring the agent into a rename that
    mints yet another fresh-slug twin. Scoped to stubs only: a patch
    legitimately declares its own goal's slug. Best-effort: DB failure →
    None."""
    if not stub_map:
        return None
    try:
        conn = db.connect(workspace / "asterism.db")
    except Exception:
        return None
    try:
        issues: "list[dict]" = []
        all_ok = True
        for slug in sorted(stub_map):
            row = conn.execute(
                "SELECT id, status, lean_path FROM goals WHERE problem = ?"
                "  AND slug = ? AND alias_target_id IS NULL LIMIT 1",
                (problem, slug),
            ).fetchone()
            if row is None:
                continue
            same_stmt = False
            if str(row["status"]) == "shelved":
                try:
                    twin_text = (workspace / str(row["lean_path"])
                                 ).read_text(encoding="utf-8")
                    twin_sig = assemble.signature_prefix(twin_text, slug)
                    cand_sig = assemble.signature_prefix(
                        stub_map[slug], slug)
                    same_stmt = (bool(twin_sig) and bool(cand_sig)
                                 and assemble.normalize_signature(twin_sig)
                                 == assemble.normalize_signature(cand_sig))
                except OSError:
                    same_stmt = False
            if same_stmt:
                issues.append({
                    "slug": slug, "existing_goal": int(row["id"]),
                    "status": str(row["status"]),
                    "severity": "info",
                    "hint": (f"`{slug}` is statement-identical to the "
                             f"existing SHELVED goal {int(row['id'])} — "
                             f"this is the sanctioned dedupe path: KEEP "
                             f"this name; at commit the stub links to "
                             f"that twin (link-and-wait, no new goal). "
                             f"Do NOT rename — a fresh slug just mints "
                             f"another twin."),
                })
                continue
            all_ok = False
            issues.append({
                "slug": slug, "existing_goal": int(row["id"]),
                "status": str(row["status"]),
                "severity": "warn",
                "hint": (f"a goal named `{slug}` already exists "
                         f"(status={row['status']}). At commit this stub "
                         f"auto-suffixes to `{slug}_2`, breaking every "
                         f"decl-name reference to it in this batch; if the "
                         f"twin is an ancestor on your chain with the same "
                         f"statement, commit rejects the whole strategy as "
                         f"circular_decomposition. Rename the sub-goal, or "
                         f"cite the existing goal instead of re-declaring "
                         f"it."),
            })
        if not issues:
            return {"checked": True, "ok": True}
        return {"checked": True, "ok": all_ok, "issues": issues}
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _declhead_submission(content: str) -> "dict":
    """Mirror commit's slug gate: every top-level `<kind> <name>` declaration's
    name must be snake_case (`^[a-z][a-z0-9_]*$`). A camelCase def/theorem name
    elaborates clean but the Forward/Backward commit parser bounces it AFTER a
    full lake build — surface it pre-commit so the agent renames in-loop
    (agent_feedback green_theorem #69/#107). `checked: False` when the content
    declares nothing to slug (e.g. a pure import/open probe)."""
    bad: "list[str]" = []
    for m in _GW_DECL_HEAD_RE.finditer(content):
        name = m.group(2)
        if not _GW_SLUG_RE.match(name):
            bad.append(name)
    if not bad:
        return {"checked": _GW_DECL_HEAD_RE.search(content) is not None,
                "ok": True}
    return {"checked": True, "ok": False, "bad_slugs": sorted(set(bad)),
            "note": "declaration name(s) must be snake_case "
                    "(^[a-z][a-z0-9_]*$); commit rejects a camelCase slug after "
                    "a full lake build — rename now"}


#: Decline placeholder marker — kept in lockstep with
#: `pipeline.forward._DECLINE_RE` (the gateway subprocess stays free of
#: pipeline imports; a source pin in tests holds the two together).
_GW_DECLINE_RE = re.compile(r"^\s*--\s*decline\s*:\s*([a-z_]+)\b",
                            re.MULTILINE | re.IGNORECASE)


def _namespace_submission(content: str, problem: str) -> "dict | None":
    """Mirror the forward namespace-fidelity gate (forward.py): the file
    elaborates clean under ANY `namespace` wrapper, but commit resolves
    the declaration under the canonical `Problems.<problem>` — a
    respelled wrapper passed validate_file and only bounced at commit
    (Test.provider_probe, 2026-08-24 feedback: `Problems.provider_probe`
    vs `Problems.Test.provider_probe`). None when there is no namespace
    line, it already matches, or the file is a decline placeholder."""
    m = re.search(r"^namespace\s+(\S+)", content, re.M)
    if not m or _GW_DECLINE_RE.search(content):
        return None
    want = f"Problems.{problem}"
    if m.group(1) == want:
        return None
    return {"ok": False, "got": m.group(1), "want": want,
            "note": (f"commit resolves your declaration under the canonical "
                     f"`namespace {want}` (case included) — keep the seed's "
                     f"namespace/end lines exactly as seeded")}


@mcp.tool(structured_output=False)
@_offload_to_thread
def withdraw_stub(slug: str = "") -> str:
    """Withdraw a sub-goal you declared this session: deletes
    `new_<slug>.lean` from your attempts directory.

    Use it when a `new_<slug>.lean` turned out redundant — its content
    got folded into `patch.lean`, or the decomposition went another way.
    A stub left behind is submitted as a sub-goal, and one that declares
    nothing (or the wrong name) is rejected at commit.

    Nothing else is reachable: the path is built from `slug`, must be a
    `new_*.lean`, and must resolve inside this session's attempts
    directory. `patch.lean` is not withdrawable.

    Args:
      slug: the sub-goal's slug — `new_<slug>.lean`, without the prefix
            or the extension.
    """
    # 2026-08-12, g7557: the commit gate told an agent to "delete the
    # file", and the agent has no delete tool — Bash closed on 08-11 and
    # its file surface is write-only. It emptied the file (refused: the
    # gate wants a declaration), then wrote `theorem r4_scratch : True
    # := trivial` purely to satisfy the name check, and did the same to
    # a second dead stub. Two vacuous sub-goals, born proved, proving
    # nothing — and 48 minutes with two `parse_proposal_fail` deaths on
    # the way. A gate must name an action the agent can perform.
    #
    # Deleting adds no destructive power it lacked: it can already
    # overwrite any of these files with `Write`, and `WorkArea.__exit__`
    # rmtrees the whole attempts directory at pipeline exit. What it
    # adds is a way to SAY "withdrawn" instead of inventing one.
    _recv_ts = _ts_now()
    meta = _current_session()
    if meta is None:
        return json.dumps({"error":
            "no session — X-Asterism-Session header missing or unknown",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    name = (slug or "").strip()
    if not name:
        return _arg_help(
            "withdraw_stub",
            'the parameter is `slug`, the sub-goal name — e.g. '
            'withdraw_stub(slug="r4_scratch") to drop new_r4_scratch.lean')
    # Strip what an agent is likely to pass by mistake, then demand the
    # remainder be a bare slug: a path separator or `..` never survives.
    if name.startswith("new_"):
        name = name[4:]
    if name.endswith(".lean"):
        name = name[:-5]
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        return json.dumps({"error": (
            f"{slug!r} is not a slug. Pass the sub-goal name alone "
            f"(letters, digits, underscore) — the file path is built "
            f"here, not passed in."),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    attempts_dir = meta.target_path.parent.resolve()
    target = (attempts_dir / f"new_{name}.lean").resolve()
    if target.parent != attempts_dir or not target.name.startswith("new_"):
        return json.dumps({"error": (
            f"refusing: {target} is outside this session's attempts "
            f"directory or is not a new_<slug>.lean stub."),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not target.is_file():
        return json.dumps(
            {"withdrawn": False, "slug": name,
             "note": f"new_{name}.lean is not in the attempts directory — "
                     f"nothing to withdraw.",
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)
    try:
        target.unlink()
    except OSError as exc:
        return json.dumps({"error": f"could not remove {target.name}: {exc}",
                           "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()})
    _log_for(meta, {"event": "stub_withdrawn", "slug": name})
    return json.dumps(
        {"withdrawn": True, "slug": name,
         "note": (f"new_{name}.lean is gone; it will not be submitted as a "
                  f"sub-goal. Make sure nothing still cites {name} — a "
                  f"citation with no declaration fails the build."),
         "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
        ensure_ascii=False)


#: Cap on decls probed per validate — a patch carries one theorem, a
#: batch stub file one decl; anything past this is pathological input.
_AXIOM_PROBE_DECL_CAP = 8


def _axioms_submission(backend, slot, content: str,
                       meta: "SessionMetadata") -> "dict | None":
    """The commit axiom gate, mirrored pre-commit (2026-08-18). g7941:
    a `native_decide` proof validated green here, built for 51 minutes,
    and died at the commit gate — a verdict knowable at this probe for
    one warm RPC per decl. Returns a failing submission entry when a
    decl's axioms exceed the problem whitelist, None when clean /
    unknowable (the commit gate stays the authority; this only warns).

    `sorryAx` is deliberately NOT flagged here: `:= by sorry` stubs are
    the legal decomposition currency pre-commit, and the commit gate's
    own tripwire handles the illegal cases."""
    try:
        from ..state import intent as _intent
        conn = db.connect_readonly(Path(meta.workspace) / "asterism.db")
        try:
            pintent = _intent.read(conn, meta.problem)
        finally:
            conn.close()
        if pintent is None:
            return None
        wl = set(_intent.effective_axioms(pintent, problem=meta.problem))
    except Exception:  # noqa: BLE001 — no intent, no verdict
        return None
    wl.add("sorryAx")
    names: "list[str]" = []
    for m in _GW_DECL_HEAD_RE.finditer(content):
        if m.group(2) not in names:
            names.append(m.group(2))
    rogue: "set[str]" = set()
    for name in names[:_AXIOM_PROBE_DECL_CAP]:
        try:
            r = backend.rpc_call(
                slot.slot_uri, "Asterism.printAxioms",
                {"fqName": f"Problems.{meta.problem}.{name}"},
                timeout=30)
        except Exception:  # noqa: BLE001 — probe is best-effort
            continue
        if r.get("found"):
            rogue |= set(r.get("axioms") or []) - wl
    if not rogue:
        return None
    from ..state.failures import rogue_axioms_message
    return {"ok": False, "rogue": sorted(rogue),
            "note": rogue_axioms_message(rogue)}


@mcp.tool(structured_output=False)
@_offload_to_thread
def validate_file(content: str = "", file: str = "") -> str:
    """Validate this session's file FROM DISK — `validate_file()` reads
    `patch.lean`, `validate_file(file="new_<slug>.lean")` reads that
    stub. The disk file is the authority: write first (`apply_edit` /
    `write_file`), then validate; there is no string mode (what you
    validate IS what commit reads — the response's `content_sha256`
    names the exact bytes). Auto-prepends Mathlib + the problem's Defs
    imports, pushes the file's content onto a borrowed slot, reads
    diagnostics, leaves the slot dirty (next caller will swap content
    as needed).

    If `content` cites a freshly-declared sibling sub-goal (`new_<slug>.
    lean` in the attempts dir, referenced but not declared here), that
    stub's declaration is inlined ahead of `content` so the citation
    resolves and its arg-order / arity is checked pre-commit — the
    sibling stubs aren't importable until commit-time (T3). Diagnostics
    are remapped back to this content's own line numbers; the response's
    `inlined_siblings` lists which stubs were folded in.

    Beyond Lean elaboration, the response carries a `submission` block that
    mirrors the framework gates the patch must ALSO pass at commit, so a file
    that elaborates clean but would still be bounced at commit is flagged here
    (no wasted retry round). `submission` is separate from `diagnostics`
    (Lean) — `diagnostics` says "it elaborates", `submission` says "commit
    will accept it":
      - `submission.citation`: { ok, issues:[{slug,status,severity,hint}] } —
        each `import Problems.<p>.proofs.L_<slug>` whose cited goal is not
        `proved`. severity `error` = rejected at commit no matter what
        (orphan/dead/disproved); `warn` = citable only via a Backward
        decomposition. Absent if the DB can't be read.
      - `submission.annotation`: { checked, ok[, note] } — whether a final
        patch (a real, non-`sorry` theorem) carries the required leading `--`
        comment block; commit rejects a missing one as `agent_no_annotation`.
        `checked:false` when `content` is a `:= by sorry` stub (not a
        submission).
      - `submission.namespace`: { ok:false, got, want, note } — present only
        when the file's `namespace` line differs from the canonical
        `Problems.<problem>` (case included); commit resolves your
        declaration under the canonical name and bounces a respelled one.

    The candidate also elaborates against the session patch's own `open`
    lines (not just Defs.lean's), so a stub using `MeasureTheory` / scoped
    `Topology` / a `Library.*` namespace validates the way it will at commit.

    The response's `commit_header` block lists the exact import/open lines
    the framework itself will inject into this file at commit (framework
    imports, Defs/patch opens, proved-sibling imports, intra-batch sub-goal
    imports) — they are already part of this validation, so do NOT write
    them yourself.

    `submission.slug_collision` predicts the commit-only slug fate of
    batch stubs: a `new_<slug>.lean` whose slug already names a goal in
    this problem auto-suffixes (breaking decl-name references) or dies as
    circular_decomposition when the twin is an identical ancestor.

    Args:
      file: Which file to validate — empty for this session's own
            target (patch.lean), or a `new_<slug>.lean` beside it.

    Returns: { ok, file, content_sha256, diagnostics, diagnostic_count
               [, inlined_siblings], commit_header, submission }.
    """
    _recv_ts = _ts_now()
    if (content or "").strip():
        # Owner ruling 2026-08-24: patch.lean is itself the draft of the
        # proofs/ text — no drafts stacked on drafts. The string mode let
        # an agent validate an in-memory candidate, never write it back,
        # and honestly report "validated" while the canonical file sat
        # unchanged (union_closed autopsy).
        return _arg_help(
            "validate_file",
            "`content` is not accepted — the DISK file is the authority. "
            "Write your candidate first (`apply_edit` edits patch.lean "
            "in place; `write_file` creates a stub), then call "
            "validate_file() for patch.lean or "
            'validate_file(file="new_<slug>.lean") for a stub')
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not meta.problem:
        return json.dumps({"error": "no problem on session metadata",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    _attempts = meta.target_path.parent.resolve()
    _fname = (file or "").strip() or meta.target_path.name
    _fpath = (_attempts / _fname).resolve()
    if (_fpath.parent != _attempts
            or (_fpath.name != meta.target_path.name
                and not _fpath.name.startswith("new_"))):
        return json.dumps({
            "error": (f"`file` must name this session's "
                      f"{meta.target_path.name} or a new_<slug>.lean "
                      f"beside it; got {file!r}"),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    try:
        content = _fpath.read_text(encoding="utf-8")
    except OSError as e:
        return json.dumps({
            "error": (f"cannot read {_fname} ({e}) — write it first: "
                      f"`apply_edit` edits patch.lean in place, "
                      f"`write_file` creates a stub"),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not content.strip():
        return json.dumps({
            "error": f"{_fname} is empty on disk — write it first",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    _content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    _hb = _heartbeat_gate(meta, content)
    if _hb is not None:
        return json.dumps(
            {"ok": False, "held": True, "heartbeat_budget": _hb,
             "diagnostics": [], "diagnostic_count": 0,
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)
    meta.hb_limit = _hb_declared(content) or meta.hb_limit
    # Metaprogramming gate — the candidate is about to be elaborated, and
    # the sibling stubs folded in with it are agent text too.
    _mp = _metaprog_error(content, "candidate")
    if _mp is not None:
        return json.dumps({"ok": False, "error": _mp, "diagnostic_count": 0,
                           "diagnostics": [],
                           "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()}, ensure_ascii=False)
    # Build the SAME single compilation unit the claimed-session tools
    # elaborate: framework imports + Defs opens + referenced sibling stubs
    # (`new_<slug>.lean` in the attempts dir, not importable until commit)
    # + content. `line_map` is always returned (imports/opens are prefix
    # even with no siblings) so diagnostics remap uniformly.
    full_content, line_map, inlined_slugs = _build_compilation_unit(
        content, meta.problem, meta.workspace, meta.target_path.parent,
        extra_opens=_harvest_open_lines(meta.file_content),
        own_name=_fpath.name)

    t0 = time.perf_counter()
    diags: list = []
    elaborate_failed = False
    elaborate_error = ""
    timed_out = False
    axioms_sub: "dict | None" = None
    _slot_kind: str = "unknown"
    backend = _state.backend
    # validate_file uses a slot like apply_edit — swap_in=False (we'll
    # overwrite). After the call we mark slot as orphan (None) so the
    # next caller doesn't think this candidate content "belongs" to
    # anyone.
    try:
        with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
            with _elab_gate(slot.slot_uri):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                backend.did_change_full(slot.slot_path, full_content,
                                        slot.file_version)
                try:
                    backend.wait_for_diagnostics(slot.slot_uri,
                                                 slot.file_version,
                                                 timeout=120)
                except (TimeoutError, RuntimeError):
                    # Elaboration didn't confirm within the budget. Do
                    # NOT swallow into a clean verdict — record it so
                    # the response reports indeterminate, not a false
                    # ok:true (#102).
                    timed_out = True
            try:
                diags = backend.diagnostics_for(slot.slot_uri)
                # Pre-commit axiom mirror — needs the slot while it
                # still holds this candidate, and a clean elaboration
                # (collectAxioms wants a final cmd state).
                if not timed_out and not any(
                        _format_diag(d).get("severity") == "error"
                        for d in diags):
                    axioms_sub = _axioms_submission(
                        backend, slot, content, meta)
            finally:
                # validate_file's content isn't the session's "real"
                # mirror, just a probe. Clear content_pipeline_id so the
                # next tool call (still on this claimed slot) didChanges
                # back to the session's `file_content`.
                #
                # IN A `finally` BECAUSE THE SLOT IS ALREADY DIRTY. The
                # candidate text went in at `did_change_full` above; if
                # anything after that raises, the outer handler reports
                # the failure and the slot keeps the CANDIDATE text
                # under the SESSION's ownership marker — every later
                # `errors_at` then serves the probe's diagnostics as the
                # file's, hot, until something else invalidates. Nothing
                # here is allowed to skip the disown.
                slot.content_pipeline_id = None
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        # `ok: false` with zero diagnostics and no reason reads, to an
        # agent, as "your file is broken and I won't say where". Every
        # failure that lands here is the FRAMEWORK's (slot gone, backend
        # restarting, LSP transport dead), so name it: an agent that
        # cannot tell "your Lean is wrong" from "my Lean is down" will
        # rewrite a correct proof (2026-08-11, same flattening family as
        # the slot-claim message above).
        elaborate_failed = True
        elaborate_error = f"{type(exc).__name__}: {exc}"
        diags = []

    formatted = [_format_diag(d) for d in diags]
    if line_map is not None:
        formatted = _remap_inlined_diags(formatted, line_map)
    has_error = any(f.get("severity") == "error" for f in formatted)
    if elaborate_failed:
        has_error = True
    dur = time.perf_counter() - t0
    n_diags = len(formatted)
    formatted = _collapse_repeats(formatted)
    response = {
        # A timeout means we never confirmed the file is clean, so it must
        # not surface as ok:true — report indeterminate (#102).
        "ok": not has_error and not timed_out,
        "file": _fname,
        "content_sha256": _content_sha,
        "diagnostic_count": n_diags,
        "diagnostics": formatted,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    # `ok` is the zero-ERRORS verdict and sorry is warning-severity, so
    # a sorry-bearing unit reads ok:true — legal for stubs and
    # decomposition patches, but ~20 agents read it as "done" (owner
    # ruling 2026-08-24: keep the boolean, surface the fact beside it).
    _sorries = [d for d in formatted
                if str(d.get("severity")) == "warning"
                and "sorry" in str(d.get("message", ""))]
    if _sorries:
        response["sorries"] = [
            {"line": d.get("line"), "message": d.get("message"),
             **({"also_lines": d["also_lines"]}
                if d.get("also_lines") else {})}
            for d in _sorries]
        if response["ok"]:
            response["sorries_note"] = (
                "`ok` means zero ERRORS; these sorry warnings remain — "
                "legal in a stub or decomposition patch, not in a "
                "finished proof")
    _note_diagnostics(meta, formatted, time.perf_counter() - t0)
    if timed_out:
        response["timed_out"] = True
        response["error"] = ("validate_file elaboration did not complete "
                             "within 120s; result indeterminate")
    if elaborate_failed:
        response["error"] = (
            f"validate_file could not run: {elaborate_error}. This is a "
            "FRAMEWORK-side fault (Lean slot or backend), not a verdict "
            "on your file — the empty diagnostics list says nothing "
            "about it. Retry this call; do not rewrite the proof on "
            "the strength of this result.")
        response["framework_fault"] = True
    if inlined_slugs:
        # Tell the agent which sibling sub-goal stubs were inlined so a
        # citation could be resolved; diagnostics are already remapped to
        # this content's own line numbers.
        response["inlined_siblings"] = inlined_slugs
    # The header the framework will inject into this file at commit
    # (already part of this probe's compilation unit) — visibility for
    # the agent, which writes none of these lines itself (task #84).
    response["commit_header"] = _commit_header_for(
        content, meta.problem, meta.workspace, meta.target_path.parent,
        extra_opens=_harvest_open_lines(meta.file_content))
    # 07-29 feedback: an agent read these as "my file was edited".
    # 08-02 feedback: and read the list as the file's FINAL imports, so a
    # sibling import it had written itself looked stripped. These are the
    # lines that still need ADDING — one already in the file needs none.
    response["commit_header"]["note"] = (
        "what the framework ADDS at commit; do not write these yourself. "
        "Imports already in your file are kept, and are absent here only "
        "because nothing needs adding")
    # Does this green mean what a green usually means? The sandbox inlines
    # sibling stubs; commit imports sibling MODULES. Where those two views
    # can disagree, say so here rather than letting the disagreement reach
    # the agent later disguised as `Unknown identifier` (#179 hid behind
    # exactly that reading for a week, 37 reports).
    response["parity"] = _parity_for(
        content, meta.problem, meta.workspace, inlined_slugs,
        response["commit_header"])
    # Submission mirror (#8 / P2): the commit-time citation + annotation gates,
    # surfaced here so a clean Lean elaboration that would still be bounced at
    # commit is flagged pre-commit. Separate from `diagnostics` (Lean) so the
    # agent reads "elaborates" and "commit will accept" independently.
    submission: "dict" = {
        "annotation": _annotation_submission(
            content, is_mint=meta.target_path.name.startswith("new_forward")),
        "decl_head": _declhead_submission(content)}
    ns = _namespace_submission(content, meta.problem)
    if ns is not None:
        submission["namespace"] = ns
    if axioms_sub is not None:
        # Pre-commit mirror of the commit axiom gate (2026-08-18):
        # `ok: false` here rides `commit_will_reject` like every other
        # submission gate, so a native_decide proof learns its fate at
        # validate time instead of after the full build.
        submission["axioms"] = axioms_sub
    cite = _citation_submission(content, meta.problem, meta.workspace,
                                set(inlined_slugs), kind=meta.kind)
    if cite is not None:
        submission["citation"] = cite
    # D-lite (task #5): predict the SPLIT — the deterministic commit-policy
    # verdicts the single-unit elaboration structurally cannot surface.
    attempts_dir = meta.target_path.parent
    stub_map: "dict[str, str]" = {}
    for _slug, _text in _collect_referenced_sibling_stubs(
            attempts_dir, content, meta.target_path.name):
        stub_map[_slug] = _text
    # content itself may BE one of the batch stubs (agent validates
    # new_<slug>.lean directly) — include it under its own slug.
    _own = _GW_DECL_HEAD_RE.search(content)
    if _own and (attempts_dir / f"new_{_own.group(2)}.lean").is_file():
        stub_map.setdefault(_own.group(2), content)
    if stub_map:
        sv = assemble.split_visibility_issues(stub_map, problem=meta.problem)
        submission["split_visibility"] = {"ok": not sv, "issues": sv}
        sc = _slug_collision_submission(
            stub_map, meta.problem, meta.workspace)
        if sc is not None:
            submission["slug_collision"] = sc
    ls = _locked_signature_submission(content, attempts_dir)
    if ls is not None:
        submission["locked_signature"] = ls
    so = _stale_olean_submission(content, meta.problem, meta.workspace)
    if so is not None:
        submission["stale_oleans"] = so
    # Top-level `ok` is the LEAN verdict only (zero errors, no timeout);
    # the submission gates are the COMMIT verdict and were readable only
    # by walking into `submission`. Two workers keyed on `ok` and shipped
    # something commit then bounced (2026-08-06 feedback). Say it at the
    # top level too — the two axes stay separate, but a clean elaboration
    # can no longer read as "good to ship" while a gate is failing.
    _failing = sorted(k for k, v in submission.items()
                      if isinstance(v, dict) and v.get("ok") is False)
    if _failing:
        response["commit_will_reject"] = _failing
    response["submission"] = submission
    _log_for(meta, {"event": "tool_call", "name": "validate_file",
                    "args": {"content_lines": full_content.count("\n") + 1},
                    "duration_s": dur,
                    "slot_kind": _slot_kind,
                    "diagnostic_count": len(formatted),
                    "has_error": has_error,
                    "timed_out": timed_out})
    if _fpath == meta.target_path.resolve():
        # Identity record for the commit gate: the exact bytes the last
        # validate saw. Commit compares the file's hash against this —
        # an edit after the final validate is caught there instead of
        # sailing through on a stale green (autopsy 2026-08-24).
        try:
            (_attempts / "_validated.json").write_text(json.dumps({
                "sha256": _content_sha, "ok": response["ok"],
                "at": _ts_now()}), encoding="utf-8")
        except OSError:
            pass
    return json.dumps(response, ensure_ascii=False)


# ─── REST endpoints ─────────────────────────

@mcp.custom_route("/register", methods=["POST"])
async def register(request: Request):
    """Open a new session. Phase 2: stash metadata only, lazy-load
    target content into a slot at first tool call."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    required = ("pipeline_id", "target_path", "problem", "workspace")
    missing = [k for k in required if k not in data]
    if missing:
        return JSONResponse({"error": f"missing keys: {missing}"},
                            status_code=400)
    log_path = data.get("log_path")
    kind = data.get("kind")
    token, err = _register_session_internal(
        pipeline_id=str(data["pipeline_id"]),
        target_path=Path(data["target_path"]),
        problem=str(data["problem"]),
        workspace=Path(data["workspace"]),
        log_path=Path(log_path) if log_path else None,
        kind=str(kind) if kind else None,
    )
    if err:
        return JSONResponse({"error": err}, status_code=500)
    return JSONResponse({"session_token": token}, status_code=200)


@mcp.custom_route("/release/{token}", methods=["POST"])
async def release(request: Request):
    """Drop session metadata. Idempotent on unknown tokens."""
    token = request.path_params["token"]
    _release_session_internal(token)
    return JSONResponse({"ok": True}, status_code=200)


# ─── Interactive editor session (serve UI) ────────────────
#
# The browser's InfoView: one RESERVED slot, claimed via
# /interactive/register, full-buffer synced via /interactive/sync
# (one didChange + elaborate, goal at the cursor rides the same
# response), cursor-only moves via /interactive/goal (no re-elaborate
# on the hot slot). The buffer lives on a scratch file under
# `.asterism/eval/` (apply_edit's write-through lands there — never on
# real problem files). Stale sessions fall to the same 900s claim
# sweep as pipelines.

def _interactive_meta(token: str) -> "SessionMetadata | None":
    with _state.sessions_lock:
        meta = _state.sessions.get(token)
    return meta if meta is not None and meta.kind == "interactive" else None


@mcp.custom_route("/interactive/register", methods=["POST"])
async def interactive_register(request: Request):
    """Claim the reserved slot for a browser editor session."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    ws = _state.workspace
    if ws is None:
        return JSONResponse({"error": "backend not ready"},
                            status_code=503)
    content = str(data.get("content") or WARMUP_CONTENT)
    scratch_dir = ws / ".asterism" / "eval"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch = scratch_dir / f"interactive_{uuid.uuid4().hex[:8]}.lean"
    scratch.write_text(content, encoding="utf-8")
    def _claim() -> "tuple[str, str | None]":
        return _register_session_internal(
            pipeline_id=f"interactive-{scratch.stem.split('_')[1]}",
            target_path=scratch, problem="", workspace=ws,
            log_path=None, kind="interactive", interactive=True,
        )

    token, err = _claim()
    if err and err.startswith("interactive slot busy"):
        # Last editor wins. The holder is either an orphan (serve
        # hard-killed before its release — otherwise it waits out the
        # 900s sweep) or another live tab; either way the session the
        # user is opening NOW is the one that matters. Pipeline slots
        # are untouchable by construction — this evicts interactive
        # claims only.
        with _state.sessions_lock:
            stale = [t for t, m in _state.sessions.items()
                     if m.kind == "interactive"]
        for t in stale:
            _release_session_internal(t)
        token, err = _claim()
    if err:
        scratch.unlink(missing_ok=True)
        busy = err.startswith("interactive slot busy")
        return JSONResponse({"error": err},
                            status_code=409 if busy else 500)
    return JSONResponse({"session_token": token}, status_code=200)


@mcp.custom_route("/interactive/sync", methods=["POST"])
async def interactive_sync(request: Request):
    """Replace the session buffer with the browser's full text, wait
    for elaboration, return diagnostics — plus the goal at the cursor
    when (line, col) ride along."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    token = str(data.get("token") or "")
    meta = _interactive_meta(token)
    if meta is None:
        return JSONResponse({"error": "unknown interactive session"},
                            status_code=404)
    _session_ctx.set(token)
    # A FULL-BUFFER SET, not an edit. The editor sends what the buffer
    # now contains; there is no anchor and no old text to name. This
    # used to call `apply_edit(1, end, content)` — the line-range
    # signature retired on 2026-08-10 (`1d7ad006`) — so every sync since
    # has been a TypeError surfacing as HTTP 500. The guard test could
    # not see it: it greps this module for the string "apply_edit"
    # rather than calling the endpoint, so it passed on a call that
    # could never run.
    _content = str(data.get("content") or "")
    # ITS OWN SCAN NOW. This entry used to be exempt from the
    # metaprogramming gate on the grounds that it delegated to
    # `apply_edit`, which has one — and that delegation is what has just
    # been removed, so the exemption's premise went with it. Every
    # gateway path that hands text to a worker calls this first.
    _mp = _metaprog_error(_content, meta.target_path.name)
    if _mp is not None:
        return JSONResponse({"error": _mp}, status_code=400)
    meta.file_content = _content
    # Write through to the scratch file, exactly as `apply_edit` did for
    # this endpoint before. Not bookkeeping: `goal_at` — which the same
    # request calls when a cursor rides along, and which every cursor
    # move calls — starts by adopting DISK as the source of truth. A
    # mirror-only sync would be reverted to the registration-time text
    # by the next goal query, and the editor would show goals for a file
    # the owner no longer has.
    try:
        meta.target_path.write_text(_content, encoding="utf-8")
    except OSError as e:
        return JSONResponse({"error": f"scratch write failed: {e}"},
                            status_code=500)
    backend = _state.backend
    diags: list = []
    converged = False
    try:
        with _acquire_slot(meta, swap_in=False) as (slot, _kind):
            with _elab_gate(slot.slot_uri):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                merged, _line_map = _compilation_for(meta)
                backend.did_change_full(slot.slot_path, merged,
                                        slot.file_version)
                converged = _diags_converged(backend, slot)
            diags = backend.diagnostics_for(slot.slot_uri)
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        return JSONResponse({"error": f"sync failed: {exc}"},
                            status_code=500)
    resp = {
        "diagnostics": diags,
        "goal": None,
        "note": None,
        # Whether Lean FINISHED. Every agent-facing tool already carries
        # this bit; the editor discarded it, so a timed-out elaborate
        # showed the owner an empty error list — the same fake-clean the
        # bit exists to prevent, on the one surface a human trusts most.
        "converged": converged,
    }
    if not converged:
        resp["note"] = ("still elaborating — an empty diagnostic list "
                        "here means 'no news yet', not 'clean'")
    line, col = data.get("line"), data.get("col")
    if isinstance(line, int):
        goal_raw = await goal_at(line, int(col or 0))
        goal = json.loads(goal_raw)
        resp["goal"] = goal.get("goal")
        resp["note"] = goal.get("note") or resp["note"]
    return JSONResponse(resp, status_code=200)


@mcp.custom_route("/interactive/goal", methods=["POST"])
async def interactive_goal(request: Request):
    """Cursor moved, text unchanged: goal only (hot slot, no swap)."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    token = str(data.get("token") or "")
    if _interactive_meta(token) is None:
        return JSONResponse({"error": "unknown interactive session"},
                            status_code=404)
    _session_ctx.set(token)
    goal_raw = await goal_at(int(data.get("line") or 1),
                             int(data.get("col") or 0))
    goal = json.loads(goal_raw)
    if goal.get("error"):
        return JSONResponse({"error": goal["error"]}, status_code=500)
    return JSONResponse({"goal": goal.get("goal"),
                         "note": goal.get("note")}, status_code=200)


@mcp.custom_route("/interactive/release", methods=["POST"])
async def interactive_release(request: Request):
    """Release the editor session and its scratch file. Idempotent."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    token = str(data.get("token") or "")
    meta = _interactive_meta(token)
    _release_session_internal(token)
    if meta is not None:
        try:
            meta.target_path.unlink(missing_ok=True)
        except OSError:
            pass
    return JSONResponse({"ok": True}, status_code=200)


def _olean_dest_for(workspace: Path, target_path: Path) -> Path | None:
    """Derive `.lake/build/lib/lean/<module path>.olean` for a Lean
    source under `workspace`. Returns None if the path isn't under
    workspace or doesn't end in `.lean`."""
    try:
        rel = target_path.resolve().relative_to(workspace.resolve())
    except ValueError:
        return None
    if rel.suffix != ".lean":
        return None
    return (workspace / ".lake" / "build" / "lib" / "lean"
            / rel.with_suffix(".olean"))


def _verify_sync(target: Path, content: str, *, write_olean: bool,
                  axioms_for: str | None, constants_for: str | None = None,
                  decl_info: bool = False,
                  decl_info_constants: bool = False,
                  rpc_timeout: int) -> dict:
    """Sync core of /verify. MUST run off the asyncio event loop —
    `_acquire_slot` does blocking polling on a per-slot lock, which
    starves all other handlers (/register, /release, /health, MCP tool
    calls) when concurrent verify requests pile up.

    miniF2F 20-problem pilot 2026-05-12 hit this: 15 simultaneous
    Builder spawns each calling /verify → event loop frozen for
    cumulative slot-acquire durations → subsequent /register
    requests time out at urllib's 120s budget → entire daemon
    deadlocks despite gateway being technically alive.

    The fix is to offload this whole sync section into asyncio's
    default threadpool via `asyncio.to_thread(_verify_sync, ...)`
    from the async handler. Event loop stays responsive; the slot-
    acquire's blocking polling no longer blocks other endpoints."""
    _mp = _metaprog_error(content, Path(target).name)
    if _mp is not None:
        return {"ok": False, "error": _mp, "diagnostic_count": 0,
                "diagnostics": [], "_status": 400}
    backend = _state.backend
    workspace = _state.workspace or target.parent
    probe_id = f"verify:{uuid.uuid4().hex[:8]}"
    meta = SessionMetadata(
        pipeline_id=probe_id,
        target_path=target,
        problem="",
        workspace=workspace,
        log_path=None,
        file_content=content,
    )

    olean_path: Path | None = None
    olean_written = False
    axioms: list[str] | None = None
    axiom_error: str | None = None
    pending_anchors: list[dict] | None = None
    top_kind: str | None = None
    top_is_prop: bool | None = None
    top_module: str | None = None
    closure_error: str | None = None
    decl_info_result: dict | None = None
    decl_info_error: str | None = None
    diags: list = []

    try:
        # /verify is a one-shot probe with no registered session →
        # use borrow mode to grab any free slot. After release the
        # slot's content_pipeline_id is cleared so the slot's
        # registered owner (if any) re-loads its own content on its
        # next acquire (paying one cold_warmup).
        with _acquire_slot(meta, swap_in=True, borrow=True) as (slot, _slot_kind):
            # Confirm the slot's diagnostics correspond to the content we
            # just swapped in, BEFORE reading them. `_acquire_slot`'s swap
            # wait is silently swallowed on a transient (a fresh slot still
            # flushing warmup diagnostics at startup; a prior borrow's
            # elaborate still in flight), and `diagnostics_for` is
            # versionless — it returns the last-published set for the slot
            # URI. Without this re-wait, an unconfirmed swap leaves
            # `diagnostics_for` reflecting a prior/concurrent occupant's
            # stale diagnostics, surfacing a phantom error (e.g. an
            # "expected token" parse error) against our target even though
            # it elaborates clean. Re-wait at our version; on failure mark
            # the probe transient so the caller retries rather than trusts
            # a stale verdict. (Root-caused 2026-06-29: the Backward
            # decomposition gate logged spurious `lake_build_error:
            # <stub>:L:C expected token` on freshly-placed stubs that build
            # clean cold — 2/2 at gateway startup.) A genuine parse error
            # still surfaces: the wait succeeds (version applied, reporter
            # done) and `diagnostics_for` returns the real error.
            try:
                backend.wait_for_diagnostics(
                    slot.slot_uri, slot.file_version, timeout=60)
            except (TimeoutError, RuntimeError) as _diag_exc:
                return {
                    "error": f"diagnostics unconfirmed for swapped-in "
                             f"content (v{slot.file_version}): {_diag_exc}",
                    "transient": True,
                }
            diags = backend.diagnostics_for(slot.slot_uri)
            formatted = [_format_diag(d) for d in diags]
            has_error = any(f.get("severity") == "error" for f in formatted)

            # Optional RPC calls — only on successful elaborate, since
            # writeOlean / collectAxioms need a final cmd state. The
            # custom RPCs run inside the slot worker via lake serve's
            # `$/lean/rpc/call` dispatch.
            if not has_error:
                if write_olean:
                    olean_path = _olean_dest_for(workspace, target)
                    if olean_path is not None:
                        olean_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            r = backend.rpc_call(
                                slot.slot_uri,
                                "Asterism.writeOlean",
                                {"destPath": str(olean_path)},
                                timeout=rpc_timeout,
                            )
                            olean_written = bool(r.get("ok"))
                            if not olean_written:
                                axiom_error = (
                                    f"writeOlean error: {r.get('error')}"
                                )
                        except Exception as e:
                            olean_written = False
                            axiom_error = (
                                f"writeOlean RPC failed: "
                                f"{type(e).__name__}: {e}"
                            )

                if axioms_for:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri,
                            "Asterism.printAxioms",
                            {"fqName": axioms_for},
                            timeout=rpc_timeout,
                        )
                        if r.get("found"):
                            axioms = list(r.get("axioms") or [])
                        else:
                            axiom_error = (
                                f"printAxioms: {r.get('error') or 'not found'}"
                            )
                    except Exception as e:
                        axiom_error = (
                            f"printAxioms RPC failed: "
                            f"{type(e).__name__}: {e}"
                        )

                if constants_for:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri,
                            "Asterism.anchorClosure",
                            {"fqName": constants_for},
                            timeout=rpc_timeout,
                        )
                        if r.get("found"):
                            pending_anchors = list(r.get("pending") or [])
                            top_kind = r.get("topKind")
                            top_is_prop = bool(r.get("topIsProp"))
                            top_module = r.get("topModule")
                        else:
                            closure_error = (
                                f"anchorClosure: {r.get('error') or 'not found'}"
                            )
                    except Exception as e:
                        closure_error = (
                            f"anchorClosure RPC failed: "
                            f"{type(e).__name__}: {e}"
                        )

                if decl_info:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri,
                            "Asterism.declInfo",
                            {"includeSignatures": True,
                             "includeUsedConstants": decl_info_constants},
                            timeout=rpc_timeout,
                        )
                        if r.get("ok"):
                            decl_info_result = {
                                "commands": list(r.get("commands") or []),
                                "decls": list(r.get("decls") or []),
                            }
                        else:
                            decl_info_error = (
                                f"declInfo: {r.get('error') or 'not ok'}"
                            )
                    except Exception as e:
                        decl_info_error = (
                            f"declInfo RPC failed: "
                            f"{type(e).__name__}: {e}"
                        )

            # Probe (verify_file) wrote stand-alone content into the
            # slot; clear so next tool call didChanges the session's
            # actual content back in.
            slot.content_pipeline_id = None
    except Exception as e:
        return {
            "error": f"slot acquire failed: {type(e).__name__}: {e}",
            "_status": 500,
        }

    formatted = [_format_diag(d) for d in diags]
    has_error = any(f.get("severity") == "error" for f in formatted)
    return {
        "ok": not has_error,
        "diagnostic_count": len(formatted),
        "diagnostics": formatted,
        "olean_written": olean_written,
        "olean_path": str(olean_path) if olean_path else None,
        "axioms": axioms,
        "axiom_error": axiom_error,
        "pending_anchors": pending_anchors,
        "top_kind": top_kind,
        "top_is_prop": top_is_prop,
        "top_module": top_module,
        "closure_error": closure_error,
        "decl_info": decl_info_result,
        "decl_info_error": decl_info_error,
    }


@mcp.custom_route("/verify", methods=["POST"])
async def verify(request: Request):
    """Unified verify endpoint: didChange the file's content into a
    worker slot, optionally write the resulting `.olean` to disk,
    optionally run `Asterism.printAxioms` on a constant in it.

    Body: {
      "target_path":  "/abs/path.lean",        # required
      "write_olean":  true,                    # default: true
      "axioms_for":   "Problems.foo.main",     # optional fq name
      "decl_info":    false,                   # per-decl structured facts
                                               #   via Asterism.declInfo —
                                               #   the syntactic oracle that
                                               #   replaces regex extraction
                                               #   (task: declInfo RPC)
      "rpc_timeout":  60,                      # default: 30 — applied to
                                               #   writeOlean + printAxioms
                                               #   RPCs. Caller-driven so
                                               #   library promotion can
                                               #   raise it for big Roots
                                               #   without bloating
                                               #   short-path callers.
    }
    Returns: {
      "ok":               bool,
      "diagnostics":      [{line,col,severity,message}, ...],
      "diagnostic_count": int,
      "olean_written":    bool,
      "olean_path":       str | null,
      "axioms":           [str, ...] | null,
      "axiom_error":      str | null,
      "decl_info":        {commands: [...], decls: [...]} | null,
      "decl_info_error":  str | null,
    }

    Replaces the prior `lake build` + `lake env lean #print axioms`
    pair: the verify, the olean publish, and the axiom probe all run
    in the same worker process against the same just-elaborated
    environment.

    Slot ownership: the slot stays claimed by this session for its
    lifetime (1:1 binding); only `content_pipeline_id` is cleared
    after the verify call so the next tool call from the same session
    didChanges the session's `file_content` back into the slot.

    Concurrency: the sync slot-acquire + LSP RPC work runs in a
    thread offloaded from the asyncio event loop via
    `asyncio.to_thread`. Without this, sync polling in
    `_acquire_slot` would freeze the event loop and starve other
    handlers (/register, /release, /health, MCP tool calls) under
    concurrent verify load — observed under the miniF2F 20-problem
    benchmark, 2026-05-12.
    """
    import asyncio
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    target_path = data.get("target_path")
    if not target_path:
        return JSONResponse({"error": "missing target_path"},
                            status_code=400)
    target = Path(target_path).resolve()
    if not target.exists():
        return JSONResponse({"error": f"file not found: {target}"},
                            status_code=404)
    write_olean: bool = bool(data.get("write_olean", True))
    axioms_for: str | None = data.get("axioms_for")
    constants_for: str | None = data.get("constants_for")
    decl_info: bool = bool(data.get("decl_info", False))
    decl_info_constants: bool = bool(data.get("decl_info_constants", False))
    try:
        rpc_timeout = int(data.get("rpc_timeout", 30))
        if rpc_timeout <= 0:
            rpc_timeout = 30
    except (TypeError, ValueError):
        rpc_timeout = 30

    err = _ensure_backend_ready()
    if err:
        return JSONResponse({"error": err}, status_code=503)
    try:
        content = target.read_text(encoding="utf-8")
    except OSError as e:
        return JSONResponse({"error": f"read failed: {e}"},
                            status_code=500)

    # Off-load the blocking slot acquire + RPC work to a thread so the
    # asyncio event loop stays free to serve /register, /release,
    # /health, MCP tool calls, and other concurrent /verify requests.
    result = await asyncio.to_thread(
        _verify_sync, target, content,
        write_olean=write_olean, axioms_for=axioms_for,
        constants_for=constants_for, decl_info=decl_info,
        decl_info_constants=decl_info_constants,
        rpc_timeout=rpc_timeout,
    )
    status = result.pop("_status", 200)
    return JSONResponse(result, status_code=status)


def _verify_session_sync(token: str, content: str, *, write_olean: bool,
                         axioms_for: str | None, rpc_timeout: int,
                         wait_timeout: int,
                         decl_info: bool = False,
                         decl_info_constants: bool = False) -> dict:
    """Sync core of /verify_session: verify `content` on the slot CLAIMED by the
    registered session `token` (claimed mode — NOT a borrow), so the session's
    OWN warm slot serves the check.

    Why this exists alongside `/verify` (borrow): a borrow evicts the slot's
    content (forcing the owner a re-warmup) and grabs an arbitrary slot, so it
    can't reuse a held session's already-loaded import closure. A framework
    caller that holds a session (the Library cleanup mechanical gates: ONE
    file-level session per file) wants the OPPOSITE — verify whole-file
    candidates against the slot whose closure is already that file's. The first
    didChange pays the import load (~25s); every subsequent whole-file gate on
    the held slot is a ~4-5s body re-elaborate instead of a fresh ~25s `lake env
    lean`. Mirrors `_verify_sync` but uses the claimed slot + an explicit
    didChange of the candidate (no `_compilation_for` swap, no eviction).

    NOTE the warm win only applies to SAME-closure (whole-file) candidates; a
    minimal-import isolate (e.g. a single decl on `import Mathlib`) is a
    different closure → re-warmup → no faster (#108), and would evict the file's
    closure, so those stay on cold `lake env lean`."""
    backend = _state.backend
    if backend is None:
        return {"error": "backend not ready", "_status": 503}
    with _state.sessions_lock:
        meta = _state.sessions.get(token)
    if meta is None:
        return {"error": f"unknown session token {token[:8]}", "_status": 404}
    _mp = _metaprog_error(content, meta.target_path.name)
    if _mp is not None:
        return {"ok": False, "error": _mp, "diagnostic_count": 0,
                "diagnostics": [], "_status": 400}

    olean_path: Path | None = None
    olean_written = False
    axioms: list[str] | None = None
    axiom_error: str | None = None
    decl_info_result: dict | None = None
    decl_info_error: str | None = None
    diags: list = []
    timed_out = False
    try:
        # Claimed mode (borrow=False), swap_in=False: locate the session's own
        # slot, then didChange the candidate ourselves (like validate_file).
        with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
            with _elab_gate(slot.slot_uri):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                backend.did_change_full(slot.slot_path, content,
                                        slot.file_version)
                try:
                    backend.wait_for_diagnostics(slot.slot_uri,
                                                 slot.file_version,
                                                 timeout=wait_timeout)
                except (TimeoutError, RuntimeError):
                    timed_out = True
            diags = backend.diagnostics_for(slot.slot_uri)
            formatted0 = [_format_diag(d) for d in diags]
            has_error0 = any(f.get("severity") == "error" for f in formatted0)
            if not has_error0 and not timed_out and decl_info:
                # Mirrors /verify's declInfo block: per-decl structured
                # facts off the elaboration just paid for (statement mint
                # piggyback — backward's placed-file verify runs here when
                # the pipeline holds its own session slot).
                try:
                    r = backend.rpc_call(
                        slot.slot_uri, "Asterism.declInfo",
                        {"includeSignatures": True,
                         "includeUsedConstants": decl_info_constants},
                        timeout=rpc_timeout)
                    if r.get("ok"):
                        decl_info_result = {
                            "commands": list(r.get("commands") or []),
                            "decls": list(r.get("decls") or []),
                        }
                    else:
                        decl_info_error = (
                            f"declInfo: {r.get('error') or 'not ok'}")
                except Exception as e:
                    decl_info_error = (f"declInfo RPC failed: "
                                       f"{type(e).__name__}: {e}")
            if not has_error0 and not timed_out and (write_olean or axioms_for):
                if write_olean:
                    olean_path = _olean_dest_for(meta.workspace,
                                                 meta.target_path)
                    if olean_path is not None:
                        olean_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            r = backend.rpc_call(
                                slot.slot_uri, "Asterism.writeOlean",
                                {"destPath": str(olean_path)},
                                timeout=rpc_timeout)
                            olean_written = bool(r.get("ok"))
                            if not olean_written:
                                axiom_error = f"writeOlean error: {r.get('error')}"
                        except Exception as e:
                            axiom_error = (f"writeOlean RPC failed: "
                                           f"{type(e).__name__}: {e}")
                if axioms_for:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri, "Asterism.printAxioms",
                            {"fqName": axioms_for}, timeout=rpc_timeout)
                        if r.get("found"):
                            axioms = list(r.get("axioms") or [])
                        else:
                            axiom_error = (f"printAxioms: "
                                           f"{r.get('error') or 'not found'}")
                    except Exception as e:
                        axiom_error = (f"printAxioms RPC failed: "
                                       f"{type(e).__name__}: {e}")
            # The candidate is a probe, not the session's committed mirror —
            # clear so the session's next tool call didChanges its own content
            # back in (mirror validate_file).
            slot.content_pipeline_id = None
    except Exception as e:
        return {"error": f"claimed slot acquire failed: "
                f"{type(e).__name__}: {e}", "_status": 500}

    formatted = [_format_diag(d) for d in diags]
    has_error = any(f.get("severity") == "error" for f in formatted)
    return {
        "ok": not has_error and not timed_out,
        "diagnostic_count": len(formatted),
        "diagnostics": formatted,
        "olean_written": olean_written,
        "olean_path": str(olean_path) if olean_path else None,
        "axioms": axioms,
        "axiom_error": axiom_error,
        "decl_info": decl_info_result,
        "decl_info_error": decl_info_error,
        "timed_out": timed_out,
    }


@mcp.custom_route("/verify_session", methods=["POST"])
async def verify_session(request: Request):
    """Verify candidate `content` on the slot CLAIMED by a registered session
    (claimed mode, no borrow eviction) — the warm-slot path for framework-side
    gates that hold a session, notably the Library cleanup mechanical gates
    (ONE file-level session per file, verifying whole-file candidates against
    its already-loaded import closure).

    Body: { "token": <session token>, "content": <full Lean source>,
            "write_olean": false, "axioms_for": null, "decl_info": false,
            "rpc_timeout": 30, "wait_timeout": 240 }
    Returns: same shape as /verify, plus "timed_out"."""
    import asyncio
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    token = data.get("token")
    content = data.get("content")
    if not token:
        return JSONResponse({"error": "missing token"}, status_code=400)
    if content is None:
        return JSONResponse({"error": "missing content"}, status_code=400)
    write_olean = bool(data.get("write_olean", False))
    axioms_for = data.get("axioms_for")
    decl_info = bool(data.get("decl_info", False))
    decl_info_constants = bool(data.get("decl_info_constants", False))
    try:
        rpc_timeout = int(data.get("rpc_timeout", 30))
        if rpc_timeout <= 0:
            rpc_timeout = 30
    except (TypeError, ValueError):
        rpc_timeout = 30
    try:
        wait_timeout = int(data.get("wait_timeout", 240))
        if wait_timeout <= 0:
            wait_timeout = 240
    except (TypeError, ValueError):
        wait_timeout = 240

    err = _ensure_backend_ready()
    if err:
        return JSONResponse({"error": err}, status_code=503)
    result = await asyncio.to_thread(
        _verify_session_sync, str(token), str(content),
        write_olean=write_olean, axioms_for=axioms_for,
        rpc_timeout=rpc_timeout, wait_timeout=wait_timeout,
        decl_info=decl_info, decl_info_constants=decl_info_constants)
    status = result.pop("_status", 200)
    return JSONResponse(result, status_code=status)


@mcp.custom_route("/compute", methods=["POST"])
async def compute_endpoint(request: Request):
    """Run sandboxed Python here, because the tool server cannot.

    `compute` shipped on 2026-08-10 as a tool on the `asterism_tools`
    STDIO server, which claude spawns as its own child. Measured
    2026-08-11: **no subprocess started from that server ever runs** —
    the sandbox interpreter timed out at 60s on a bare `print('alive')`
    twelve consecutive times, and the control spawn (the very
    interpreter hosting the server, same flags, same cwd) hung
    identically. From a shell the same command takes 95ms. So it was
    never the venv, and the tool had not worked once in production.

    This process has no such problem: it spawns `lake serve` and a
    pool of lean workers continuously. And the stdio server already
    reaches it over plain HTTP (`knowledge/pin_check._gateway_probe`
    borrows `/verify` on every loogle call), so the client side is a
    proven path rather than a new one.

    Body:    {"code": "<python>"}
    Returns: {"rc": int, "output": str, "seconds": float, "killed": str}

    `killed` carries the limit that stopped the run ("timeout" /
    "memory" / ""), and it is part of the wire format rather than a
    detail because it is the half of the answer that says what to do
    next. It was omitted at first, and the caller rebuilt the result
    with `killed=""`: a timed-out sweep reached the Strategist as the
    standing header and NOTHING else — no output (the kill took the
    buffer), no "stopped at the 30s limit, shrink the search". The
    agent's next act was to spend a call on `print("hello", 1+1)` to
    find out whether the tool was alive at all (2026-08-12).

    The sandbox's own guarantees are unchanged — separate interpreter,
    no framework on `sys.path`, memory/wall-clock caps, PEP 578 audit
    hook — because this moves WHERE `sandbox.run` is called, not what
    it does.
    """
    try:
        data = await request.json()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    code = str(data.get("code") or "")
    from ..sandbox import run as _sandbox_run
    try:
        res = await asyncio.to_thread(_sandbox_run, code)
    except Exception as e:  # noqa: BLE001 — reported, never swallowed
        return JSONResponse(
            {"rc": 1, "output": f"[compute] gateway-side failure: "
                                f"{type(e).__name__}: {e}", "seconds": 0.0})
    return JSONResponse({"rc": res.rc, "output": res.output,
                         "seconds": res.seconds, "killed": res.killed})


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
            by_uri[uri] = int(priv)
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


@mcp.custom_route("/warm_target", methods=["POST"])
async def warm_target(request: Request):
    """RAM-ledger control plane (owner design 2026-08-25): the
    dispatcher's ledger tick POSTs {target, min_available_gb}; the
    gateway converges its open-slot count toward it (up via the
    background converger, down at release time). The reply reports the
    current open/free counts — the dispatcher's Lean admission gates on
    `open`, which keeps the /register "no free slot" contract intact
    while the pool moves."""
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001 — malformed body is a client bug
        return JSONResponse({"error": "JSON body required"},
                            status_code=400)
    try:
        from ..core.ram_ledger import MAX_SLOTS
        target = max(1, min(int(data.get("target")), MAX_SLOTS))
    except (TypeError, ValueError):
        return JSONResponse({"error": "target must be an int"},
                            status_code=400)
    _state.warm_target = target
    try:
        _state.warm_min_available_gb = float(
            data.get("min_available_gb") or 0.0)
    except (TypeError, ValueError):
        _state.warm_min_available_gb = 0.0
    with _state.sessions_lock:
        open_n = _open_pipeline_slots_locked()
        free_n = sum(1 for s in _state.workers
                     if not s.reserved and not s.closed
                     and s.claimed_by is None)
    if open_n != target and _state.first_warm_done:
        _kick_warm_converger()
    return JSONResponse({"target": target, "open": open_n,
                         "free": free_n,
                         "warming": _state.warm_converger_on,
                         # the ledger's slot-coefficient instrument —
                         # same TTL-cached reading /health serves
                         "slot_private_mb": _slot_private_mb_cached(),
                         # CPU-gate congestion (owner call 2026-08-25):
                         # sustained elab_waiting > 0 means the machine,
                         # not RAM, is the binding axis.
                         **elab_gate_stats()})


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request):
    """Liveness check. Reports worker pool status + active sessions
    + slot acquire counters (so operator can compute hot/cold ratio
    over the run, especially relevant at pool > W where churn
    dominates framework overhead).

    503 while the first warm runs. HTTP opens before that warm now, so
    this endpoint answers minutes earlier than it used to — and every
    reader of it means "is the gateway USABLE", not "is the port open".
    `lifecycle._ping_health` catches `URLError`, of which `HTTPError` is
    a subclass, so a 503 reads as absent exactly like the old connection
    refusal did: the warm window stays invisible to the reuse gate and
    `gateway-starting.txt` stays its only presence signal."""
    if not _state.first_warm_done:
        return JSONResponse(
            {"warming": True, "backend_ready": False, "pid": os.getpid(),
             "error": WARMING_MSG}, status_code=503)
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
    return JSONResponse({
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
        # RAM-ledger surface (owner design 2026-08-25): open = slots
        # with a live worker (closed ones freed their RAM); target =
        # what the dispatcher's ledger last asked for (None = static
        # mode). The cockpit reads WHICH AXIS binds from these.
        "workers_open": n_open,
        "warm_target": _state.warm_target,
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
    })


# ─── Session header → contextvar middleware ──────────────

class SessionHeaderMiddleware:
    """ASGI middleware: read X-Asterism-Session header, set
    `_session_ctx` so tool bodies (which run in the same asyncio task
    → same contextvar scope) can resolve their session via
    `_current_session()`."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            raw = headers.get(b"x-asterism-session")
            token = raw.decode("ascii") if raw else None
            ctx_token = _session_ctx.set(token)
            try:
                await self.app(scope, receive, send)
            finally:
                _session_ctx.reset(ctx_token)
        else:
            await self.app(scope, receive, send)


# ─── Entrypoint ─────────────────────────────

def main() -> None:
    # Install SelectorEventLoop policy at the VERY TOP of main, before
    # any thread or asyncio interaction. _start_workers (launched as a
    # daemon thread below) uses asyncio internally via lsp_client, and
    # uvicorn.run() creates its own event loop. Both must see the
    # Selector policy at construction time. Doing this AFTER thread
    # start (as the prior implementation did) was racy and uvicorn
    # ignored the global policy because its default `loop="auto"`
    # bypasses asyncio policy on Windows.
    _install_windows_event_loop_policy()

    workspace_env = os.environ.get("ASTERISM_WORKSPACE")
    if not workspace_env:
        print("[gateway] ASTERISM_WORKSPACE env required",
              file=sys.stderr, flush=True)
        sys.exit(2)
    workspace = Path(workspace_env).resolve()
    from ..core import config as _cfg
    port = _cfg.get(
        "gateway.port", default=8765,
        env_var="ASTERISM_GATEWAY_PORT", cast=int,
        workspace=workspace,
    )
    # Worker count is locked to dispatch.pool — every spawn claims one
    # dedicated worker for its lifetime (#118, 1:1 binding). No separate
    # gateway.workers knob.
    w_count = _cfg.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int,
        workspace=workspace,
    )
    # Adaptive RAM ledger (owner design 2026-08-25): the dispatcher's
    # ledger tick will own the slot count via /warm_target, so the
    # LAUNCH count only decides how fast first_warm opens the Lean
    # plane — start small, let the converger grow the pool in the
    # background while work already flows.
    try:
        from ..core import ram_ledger as _rl
        _budget_gb = _rl.parse_budget(_rl.env_budget_spec(workspace),
                                      _rl.total_gb())
    except Exception:  # noqa: BLE001 — the ledger must not stop launch
        _budget_gb = None
    if _budget_gb is not None:
        _target0 = _rl.compute_target_slots(budget_gb=_budget_gb,
                                            nl_demand=0)
        w_count = max(1, min(8, _target0))
        _state.warm_target = _target0
        print(f"[gateway] RAM ledger active — budget {_budget_gb:.1f} GB,"
              f" launch warms {w_count} slot(s), converger grows toward "
              f"{_target0}", file=sys.stderr, flush=True)
    # Reserved slots for the serve UI's interactive editor — outside
    # the pipeline pool entirely (pipeline=slot identity holds both
    # ways: spawns never see them, the editor never sees spawn slots).
    n_interactive = _cfg.get(
        "gateway.interactive_slots", default=1,
        env_var="ASTERISM_INTERACTIVE_SLOTS", cast=int,
        workspace=workspace,
    )
    # The claim ceiling is DERIVED, never a second hand-tuned constant:
    # the previous literal was chosen against a 780s worker life, and
    # when `spawn_timeout_sec` doubled nobody came back to it (2026-08-11
    # — the sweep then took slots from live workers). Twice the spawn
    # budget covers a main spawn plus its rescue/postmortem successor
    # under the same claim, and anything past that is an anomaly the
    # sweep should report rather than accommodate.
    _spawn_budget = _cfg.get(
        "dispatch.spawn_timeout_sec", default=1800,
        env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int,
        workspace=workspace,
    )
    _state.claim_ceiling_sec = max(2.0 * float(_spawn_budget),
                                   _LEASE_TTL_SEC + 900.0)

    # Downsize to what physical memory can hold — an overcommitted pool
    # pages its own warm-up to death (5 workers × multi-GB Mathlib on an
    # 8 GB machine: slot 0 not done after 300s). Yaml is intent; RAM is
    # law. The configured value still goes to /health so the daemon's
    # reuse gate compares yaml-to-yaml.
    from .lifecycle import ram_clamped_pool
    _state.workers_configured = w_count
    w_count, clamp_msg = ram_clamped_pool(w_count, n_interactive)
    if clamp_msg:
        print(f"[gateway] RAM clamp: {clamp_msg}",
              file=sys.stderr, flush=True)

    print(f"[gateway] starting; workspace={workspace} port={port} "
          f"workers={w_count}+{n_interactive} interactive",
          file=sys.stderr, flush=True)

    # Claim the port BEFORE warming, and hold the socket for uvicorn.
    # A collision must fail in seconds — the 2026-07-07 Test.Test3 run
    # warmed 7 minutes and then died on bind (Errno 10048) because an
    # earlier gateway held the port. bind-only (no listen): probes get
    # instant refusals during warm; asyncio listens when serving starts.
    import socket as _socket
    try:
        http_sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        if os.name != "nt":
            # TIME_WAIT remnants of a just-killed gateway's accepted
            # connections block a bare bind for up to ~60s on POSIX even
            # after the listener is provably gone — _kill_stale_gateway's
            # three-signal proof passed and this bind still EADDRINUSE'd,
            # twice on boarding day (2026-08-24; same family as the zen
            # shim's rebind). POSIX SO_REUSEADDR admits no second LIVE
            # listener, so the port-singleton guarantee is intact where
            # exclusivity is real; Windows keeps the bare bind (its
            # REUSEADDR would let a rival bind over a live gateway).
            http_sock.setsockopt(_socket.SOL_SOCKET,
                                 _socket.SO_REUSEADDR, 1)
        http_sock.bind(("127.0.0.1", port))
    except OSError as e:
        print(f"[gateway] FATAL: port {port} is already taken ({e}) — "
              f"another gateway is running or warming; refusing to race it",
              file=sys.stderr, flush=True)
        sys.exit(4)

    # Presence signal for the warm window (HTTP opens only after the
    # pool warms, so /health can't see us yet): daemon-side
    # `start_gateway` waits on this marker instead of spawning a rival.
    from .lifecycle import gateway_starting_marker
    _marker = gateway_starting_marker(workspace)
    try:
        _marker.parent.mkdir(parents=True, exist_ok=True)
        _marker.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass
    import atexit as _atexit
    _atexit.register(lambda: _marker.unlink(missing_ok=True))

    threading.Thread(target=_start_workers,
                     args=(workspace, w_count, n_interactive),
                     daemon=True).start()
    # Stale-claim sweep: reclaims gateway slots whose /release was
    # dropped (urlopen failure during teardown, worker crash before
    # AttemptsContext.__exit__, etc.). Cheap when nothing is stale.
    threading.Thread(target=_stale_claim_sweep_loop,
                     daemon=True, name="gateway-stale-claim-sweep").start()
    # Wedge recovery: replace the backend if a non-terminating elaborate
    # pins a worker (2026-06-12 hang fix — see `_wedge_watchdog_loop`).
    threading.Thread(target=_wedge_watchdog_loop,
                     daemon=True, name="gateway-wedge-watchdog").start()
    # The warm is watched from a thread and HTTP opens NOW, rather than
    # after it (2026-08-12). `core/warmup` dispatches Strategist and
    # Scholar during this window on purpose — a cold slot-0 warm was
    # measured at 300s+, once seven minutes — and `compute` lives in
    # this process, so waiting here left the NL layer without its
    # calculator for exactly the minutes it is the only thing running.
    #
    # Nothing about the warm moves ONTO the serving thread: the pool
    # already inits on `_start_workers`'s thread and only the WAIT was
    # here. Every Lean surface refuses fast until `first_warm_done`
    # (`_ensure_backend_ready`), so no request can put that wait back
    # on the event loop.
    #
    # Inner warm budget scales with the EFFECTIVE slot count: the warm
    # loop legally tolerates 300s per slot serially, so a flat 600s
    # contradicted our own tolerance at any pool ≥ 2. The daemon's
    # outer wait scales from the CONFIGURED (≥ effective) count and
    # stays the more generous of the two.
    _warm_budget = 300.0 * (w_count + n_interactive) + 300.0

    app = mcp.streamable_http_app()
    app = SessionHeaderMiddleware(app)

    import uvicorn
    # Important: uvicorn.run / uvicorn.Config(loop="asyncio") would
    # internally call `asyncio.set_event_loop_policy(
    # WindowsProactorEventLoopPolicy())` on Windows, OVERRIDING our
    # earlier WindowsSelectorEventLoopPolicy install at main() top.
    # Observed in SG run #18: gateway died at +82min with the same
    # IocpProactor.accept WinError 64 race that 475c318 / 1db4e8c
    # attempted to fix.
    #
    # Fix: build the asyncio loop manually with SelectorEventLoop,
    # then use uvicorn.Config(loop="none") so uvicorn doesn't touch
    # the policy. `Server.serve()` is an async coroutine — we run it
    # on our pre-built loop directly. This is the only way to keep
    # SelectorEventLoop active across uvicorn's startup.
    # Serve on the socket bound at startup (asyncio listens on it) —
    # the port was ours for the whole warm, so no bind can fail here.
    #
    # The Server object exists BEFORE the warm watcher starts: the
    # watcher's only way to end this process is `should_exit`, and a
    # warm that fails in the first second must not find that handle
    # still unset.
    if sys.platform == "win32":
        import asyncio as _asyncio
        loop = _asyncio.SelectorEventLoop()
        _asyncio.set_event_loop(loop)
        config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                log_level="warning", loop="none")
    else:
        loop = None
        # Non-Windows: manual Server so the pre-bound socket is used.
        config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                log_level="warning")
    server = uvicorn.Server(config)
    _state.http_server = server
    threading.Thread(target=_watch_initial_warm, daemon=True,
                     name="gateway-warm-watch",
                     args=(_warm_budget, _marker)).start()
    print(f"[gateway] HTTP open on {port} — pool warming in background",
          file=sys.stderr, flush=True)

    try:
        if loop is not None:
            try:
                loop.run_until_complete(server.serve(sockets=[http_sock]))
            finally:
                loop.close()
        else:
            server.run(sockets=[http_sock])
    finally:
        # Reap the Lean backend subtree on gateway exit (SIGTERM from the
        # daemon's atexit, or any shutdown). Without this, `lake serve`'s
        # `lean --server`/`--worker` children orphan on every gateway
        # exit/restart and accumulate (rule-8 / 2026-06-12 smoke-test
        # finding). uvicorn handles SIGTERM gracefully → serve() returns
        # → this finally runs.
        _b = _state.backend
        if _b is not None:
            try:
                _b.shutdown()
            except Exception:
                try:
                    _b._kill_tree()
                except Exception:
                    pass

    # A warm that never finished is still fatal, and still rc 3: the
    # daemon's `start_gateway` distinguishes "died" from "still coming"
    # by this exit, and a process that served 503s forever would hang
    # every retry behind a gateway that can never do Lean work.
    if _state.warm_failed:
        sys.exit(3)


def _install_windows_event_loop_policy() -> None:
    """Switch the asyncio event loop policy to Selector on Windows.

    Default Python 3.8+ on Windows is ProactorEventLoop (IOCP-based).
    Under sustained HTTP load with frequent connection churn we hit
    `OSError(WinError 64, '指定的網路名稱無法使用 / The specified
    network name is no longer available')` inside
    `IocpProactor.accept.accept_coro()` — the accept task raises but
    asyncio's default handler does NOT re-arm the accept loop, so the
    listening socket stays bound while no new connections are accepted.
    The HTTP endpoint becomes "half-working": in-flight worker sessions
    keep responding, but framework `/verify` POSTs from the daemon get
    WinError 10061 connection-refused (kernel rejects SYN because
    nothing's calling AcceptEx anymore).

    SelectorEventLoop on Windows uses select() instead of IOCP and
    doesn't run into this race. Throughput ceiling is lower (~few
    hundred concurrent connections) but Asterism gateway concurrency
    is bounded by `gateway.workers` (default 3) — well within the
    Selector ceiling.

    Observed in SG run #14 (2026-05-11): gateway crash at +~4h45min
    of sustained pool=15 / workers=3 load. See
    `runs/sg_run_14.md` CUT REASON for forensic detail.
    """
    if sys.platform != "win32":
        return
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


if __name__ == "__main__":
    main()
