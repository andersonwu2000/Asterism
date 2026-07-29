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
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..state import assemble, db, manifest, metaprog
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


def _ensure_backend_ready(timeout: float = 240.0) -> str | None:
    """Block until the bg-init thread reports ready. Returns None on
    success, error string on init failure or timeout."""
    if not _state.ready_event.wait(timeout=timeout):
        return f"backend not ready after {timeout}s"
    if _state.backend is None or not _state.workers:
        return _state.init_error or "backend init failed"
    return None


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
        n = (len(_state.workers) - n_res) or 1
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
            _restart_backend(
                f"elaborate on {wedged} wedged >{int(_BACKEND_WEDGE_SEC)}s")


# ─── Slot acquisition (the heart of Phase 2) ─────────────

def _borrow_order(workers):
    """Slot preference for a borrow probe: UNCLAIMED slots first (evicting a
    registered session's warm content costs its owner a cold_warmup and can
    block it behind our lock — the 2026-06-29 slot-thrash shape), LRU within
    each group. A claimed slot is reachable only when every unclaimed slot is
    lock-busy — liveness for housekeeping probes when the whole pool is
    registered. Extracted for direct unit-testing of the ordering invariant."""
    return sorted((s for s in workers if not getattr(s, "reserved", False)),
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
        raise RuntimeError(
            f"no slot claimed for pipeline {meta.pipeline_id} "
            "— register_session was not called (or release races with use)"
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
             if s.claimed_by is None and s.reserved == interactive), None,
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


def _release_session_internal(token: str) -> None:
    """Drop session metadata and release this pipeline's claimed worker
    slot (1:1 lifecycle, #118). `content_pipeline_id` is left untouched
    — the next claim will didChange its own content in regardless, so
    clearing it eagerly buys nothing. Idempotent on unknown tokens."""
    with _state.sessions_lock:
        meta = _state.sessions.pop(token, None)
        if meta is None:
            return
        # Clear claim under sessions_lock so a concurrent register
        # cannot grab the slot before we release it.
        for slot in _state.workers:
            if slot.claimed_by == meta.pipeline_id:
                slot.claimed_by = None
                break
    _log_for(meta, {"event": "session_released",
                    "pipeline_id": meta.pipeline_id})


def _current_session() -> SessionMetadata | None:
    token = _session_ctx.get()
    if token is None:
        return None
    with _state.sessions_lock:
        return _state.sessions.get(token)


# ─── Stale-claim sweep (#118 follow-up) ────────────────

# Worker timeouts are 600s (main) + 180s (postmortem); a healthy
# pipeline issues tool calls every few seconds during agent work, so
# silence > 900s reliably means the claim has leaked (release_session
# urlopen failed silently, or the worker / dispatcher crashed before
# AttemptsContext.__exit__ ran). Set well above WORKER_TIMEOUT to
# leave a comfortable buffer so long agent reasoning between tool
# calls is never mistakenly reclaimed.
_LEASE_TTL_SEC = 900.0
_SWEEP_INTERVAL_SEC = 60.0


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
    couldn't find any free slot. Activity-TTL self-heals before that
    safety net trips."""
    now = time.monotonic()
    reclaimed = 0
    with _state.sessions_lock:
        # Snapshot then mutate — we hold the lock for the whole sweep
        # because reclaim writes `claimed_by` and `sessions.pop` need
        # the same lock that /register / /release use to serialize
        # claim transitions. The work per session is O(workers) for
        # the slot lookup which is bounded (~4 in production), so
        # holding the lock for the full pass is cheap.
        stale = [
            (tok, meta) for tok, meta in _state.sessions.items()
            if now - meta.last_active > _LEASE_TTL_SEC
        ]
        for tok, meta in stale:
            _state.sessions.pop(tok, None)
            for slot in _state.workers:
                if slot.claimed_by == meta.pipeline_id:
                    slot.claimed_by = None
                    break
            reclaimed += 1
            inactive_for = now - meta.last_active
            print(
                f"[gateway] reclaimed leaked slot for "
                f"pipeline {meta.pipeline_id[:8]} "
                f"({inactive_for:.0f}s inactive > "
                f"{_LEASE_TTL_SEC:.0f}s TTL)",
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
    attempts_dir: Path, content: str,
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
    (raw args, per `manifest.defs_opens`) plus `extra_opens` (the session
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


def _build_compilation_unit(
    content: str, problem: str, workspace: "Path", attempts_dir: "Path",
    extra_opens: "list[str]" = (),
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
        _collect_referenced_sibling_stubs(attempts_dir, content))
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
                           manifest.defs_opens(workspace, problem)
                           + manifest.defs_namespaces(workspace, problem),
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
    opens = _merge_opens(content, manifest.defs_opens(workspace, problem),
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
        meta.target_path.parent)
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


def _stub_fingerprint(attempts_dir: "Path") -> tuple:
    """(name, mtime_ns, size) per `new_*.lean` in the attempts dir,
    sorted — the sibling-stub half of the compilation unit's identity.
    OSError → () (best-effort; an unreadable dir just reads as empty)."""
    try:
        return tuple(sorted(
            (f.name, f.stat().st_mtime_ns, f.stat().st_size)
            for f in attempts_dir.glob("new_*.lean")))
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
    fp = _stub_fingerprint(meta.target_path.parent)
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


def _editor_line_count(text: str) -> int:
    """Line count as an editor shows it: the empty element after a
    trailing newline is NOT a line (bbe7169 — counting it let a range
    overshoot land on the phantom slot and eat the file's last real
    line). ONE law, shared by apply_edit's range check and
    interactive_sync's full-buffer replace — they drifted apart once
    and every chapter probe broke (QA, 2026-07-20)."""
    lines = text.split("\n")
    return len(lines) - 1 if lines and lines[-1] == "" else len(lines)


@mcp.tool()
@_offload_to_thread
def apply_edit(start_line: int, end_line: int, new_text: str) -> str:
    """Replace lines [start_line..end_line] (1-indexed, inclusive) in
    the target Lean file with new_text. Set start_line == end_line to
    replace a single line. new_text may contain multiple lines (use
    literal newlines).

    Lean re-elaborates after the edit; the response includes the proof
    goal at line=start_line col=2, plus diagnostics.

    Args:
      start_line: 1-indexed inclusive start of region to replace.
      end_line:   1-indexed inclusive end of region to replace.
      new_text:   Replacement text (may be multi-line).
    """
    _recv_ts = _ts_now()
    meta = _current_session()
    if meta is None:
        return json.dumps({"error":
            "no session — X-Asterism-Session header missing or unknown",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
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
        return json.dumps({"error": (
            f"{_resync_err}; edit aborted — the buffer may be stale and "
            "writing through it could clobber newer on-disk content. "
            "Retry, or Read the file and use Write."),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    lines = meta.file_content.split("\n")
    n_lines = _editor_line_count(meta.file_content)
    if start_line < 1 or start_line > n_lines:
        return json.dumps({"error":
            f"start_line {start_line} out of range 1..{n_lines}"})
    if end_line < start_line or end_line > n_lines:
        return json.dumps({"error":
            f"end_line {end_line} out of range {start_line}..{n_lines}"
            f" (the file has {n_lines} lines)"})

    # Editor-sanity normalization (agent_feedback ~30 reports):
    # CRLF → LF, and ONE trailing newline stripped — a block ending in
    # a newline means "content ends here", not "plus a blank line".
    # Empty new_text DELETES the range (the old splice left a blank
    # line behind, which no editor means by "replace with nothing").
    new_text = new_text.replace("\r\n", "\n")
    if new_text.endswith("\n"):
        new_text = new_text[:-1]
    replacement = [] if new_text == "" else new_text.split("\n")
    # Echo of the OLD region (the splice's precondition): a range that
    # drifted after an earlier edit becomes visible in THIS response
    # instead of via a confusing downstream diagnostic.
    replaced_text = "\n".join(lines[start_line - 1:end_line])
    if len(replaced_text) > 600:
        replaced_text = replaced_text[:600] + " …[truncated]"

    new_lines = (lines[: start_line - 1]
                 + replacement
                 + lines[end_line:])
    new_content = "\n".join(new_lines)

    # Metaprogramming gate — BEFORE the mirror/disk write-through, so a
    # blocked edit leaves neither the buffer nor the file carrying it.
    _mp = _metaprog_error(new_content, meta.target_path.name)
    if _mp is not None:
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
    _lo = max(1, start_line - 2)
    _hi = min(len(new_lines), start_line + len(replacement) - 1 + 2)
    post_edit_region = "\n".join(
        f"{i}: {new_lines[i - 1]}" for i in range(_lo, _hi + 1))

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
    _verb = "deleted" if not replacement else "replaced"
    _n_diags = len(formatted)
    formatted = _collapse_repeats(formatted)
    response = {
        "edit": (f"{_verb} lines {start_line}-{end_line}; "
                 f"file is now {len(new_lines)} lines"),
        "replaced_text": replaced_text,
        "post_edit_region": post_edit_region,
        "goal_at_edit_start": goal_text,
        "diagnostics": formatted,
        "diagnostic_count": _n_diags,
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    if not converged:
        response["elaborating"] = True
        response["warning"] = _ELABORATING_WARNING
    if _cite is not None and _cite.get("issues"):
        response["citation"] = _cite
    if _locked_warn is not None:
        response["locked_signature"] = _locked_warn
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "apply_edit",
                    "args": {"start_line": start_line,
                             "end_line": end_line,
                             "new_text_lines": new_text.count("\n") + 1},
                    "duration_s": dur,
                    "slot_kind": _slot_kind, "converged": converged,
                    "diagnostic_count": len(diags)})
    return json.dumps(response, ensure_ascii=False)


@mcp.tool()
@_offload_to_thread
def goal_at(line: int, col: int) -> str:
    """Get the Lean proof goal state at a specific position.

    Args:
      line: 1-indexed line number.
      col:  0-indexed character column.
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


_ELABORATING_WARNING = (
    "Lean has NOT finished elaborating this file (120s wait expired) — "
    "the diagnostics here are INCOMPLETE and a count of 0 does NOT mean "
    "the file is clean. Re-run this tool to check again."
)


@mcp.tool()
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
    response = {"diagnostics": formatted, "count": len(formatted),
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
            if status in ("dead", "disproved"):
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
        return {"checked": False,
                "note": "stubs need no annotation — whoever proves the "
                        "sub-goal writes it"}
    ok = bool(_gw_leading_comments(content).strip())
    return {"checked": True, "ok": ok,
            "note": "" if ok else
            "FINAL patch only: add a leading -- comment before commit "
            "(agent_no_annotation). Ignore on exploratory probes."}


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


@mcp.tool()
@_offload_to_thread
def validate_file(content: str) -> str:
    """Validate a candidate Lean file (typically a `new_<slug>.lean`
    sub-goal stub, or the assembled strategy patch). Auto-prepends
    Mathlib + the problem's Defs imports, pushes the candidate content
    onto a borrowed slot, reads diagnostics, leaves the slot dirty (next
    caller will swap content as needed).

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
      content: Full contents of the candidate file.

    Returns: { ok, diagnostics, diagnostic_count[, inlined_siblings],
               commit_header, submission }.
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
    if not meta.problem:
        return json.dumps({"error": "no problem on session metadata",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
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
        extra_opens=_harvest_open_lines(meta.file_content))

    t0 = time.perf_counter()
    diags: list = []
    elaborate_failed = False
    timed_out = False
    _slot_kind: str = "unknown"
    backend = _state.backend
    # validate_file uses a slot like apply_edit — swap_in=False (we'll
    # overwrite). After the call we mark slot as orphan (None) so the
    # next caller doesn't think this candidate content "belongs" to
    # anyone.
    try:
        with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
            slot.file_version += 1
            backend.clear_diagnostics(slot.slot_uri)
            backend.did_change_full(slot.slot_path, full_content,
                                    slot.file_version)
            try:
                backend.wait_for_diagnostics(slot.slot_uri,
                                              slot.file_version,
                                              timeout=120)
            except (TimeoutError, RuntimeError):
                # Elaboration didn't confirm within the budget. Do NOT
                # swallow into a clean verdict — record it so the response
                # reports indeterminate, not a false ok:true (#102).
                timed_out = True
            diags = backend.diagnostics_for(slot.slot_uri)
            # validate_file's content isn't the session's "real" mirror,
            # just a probe. Clear content_pipeline_id so the next tool
            # call (still on this claimed slot) didChanges back to the
            # session's `file_content`.
            slot.content_pipeline_id = None
    except Exception:
        elaborate_failed = True
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
        "diagnostic_count": n_diags,
        "diagnostics": formatted,
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    if timed_out:
        response["timed_out"] = True
        response["error"] = ("validate_file elaboration did not complete "
                             "within 120s; result indeterminate")
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
    response["commit_header"]["note"] = (
        "framework injects these at commit; do not write them")
    # Submission mirror (#8 / P2): the commit-time citation + annotation gates,
    # surfaced here so a clean Lean elaboration that would still be bounced at
    # commit is flagged pre-commit. Separate from `diagnostics` (Lean) so the
    # agent reads "elaborates" and "commit will accept" independently.
    submission: "dict" = {
        "annotation": _annotation_submission(
            content, is_mint=meta.target_path.name.startswith("new_forward")),
        "decl_head": _declhead_submission(content)}
    cite = _citation_submission(content, meta.problem, meta.workspace,
                                set(inlined_slugs), kind=meta.kind)
    if cite is not None:
        submission["citation"] = cite
    # D-lite (task #5): predict the SPLIT — the deterministic commit-policy
    # verdicts the single-unit elaboration structurally cannot surface.
    attempts_dir = meta.target_path.parent
    stub_map: "dict[str, str]" = {}
    for _slug, _text in _collect_referenced_sibling_stubs(
            attempts_dir, content):
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
    response["submission"] = submission
    _log_for(meta, {"event": "tool_call", "name": "validate_file",
                    "args": {"content_lines": full_content.count("\n") + 1},
                    "duration_s": dur,
                    "slot_kind": _slot_kind,
                    "diagnostic_count": len(formatted),
                    "has_error": has_error,
                    "timed_out": timed_out})
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
    # ONE line-count law with apply_edit (`_editor_line_count`) — the
    # old `count("\n") + 1` here was one high for any buffer ending in
    # a newline (the probe assembler always emits one), so every
    # chapter-probe sync bounced off apply_edit's range check with
    # "end_line N+1 out of range 1..N" (QA, 2026-07-20).
    end = max(1, _editor_line_count(meta.file_content))
    edit_raw = await apply_edit(1, end, str(data.get("content") or ""))
    edit = json.loads(edit_raw)
    if edit.get("error"):
        return JSONResponse({"error": edit["error"]}, status_code=500)
    resp = {
        "diagnostics": edit.get("diagnostics") or [],
        "goal": None,
        "note": None,
    }
    line, col = data.get("line"), data.get("col")
    if isinstance(line, int):
        goal_raw = await goal_at(line, int(col or 0))
        goal = json.loads(goal_raw)
        resp["goal"] = goal.get("goal")
        resp["note"] = goal.get("note")
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
            slot.file_version += 1
            backend.clear_diagnostics(slot.slot_uri)
            backend.did_change_full(slot.slot_path, content, slot.file_version)
            try:
                backend.wait_for_diagnostics(slot.slot_uri, slot.file_version,
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


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request):
    """Liveness check. Reports worker pool status + active sessions
    + slot acquire counters (so operator can compute hot/cold ratio
    over the run, especially relevant at pool > W where churn
    dominates framework overhead)."""
    backend_ok = _state.backend is not None and bool(_state.workers)
    with _state.sessions_lock:
        n_sessions = len(_state.sessions)
    # workers_total counts the PIPELINE pool only — the daemon's reuse
    # gate compares it against dispatch.pool; reserved interactive
    # slots report separately.
    n_workers = sum(1 for s in _state.workers if not s.reserved)
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
        "sessions_active": n_sessions,
        "init_error": _state.init_error,
        "acquires": counters,
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
    # Reserved slots for the serve UI's interactive editor — outside
    # the pipeline pool entirely (pipeline=slot identity holds both
    # ways: spawns never see them, the editor never sees spawn slots).
    n_interactive = _cfg.get(
        "gateway.interactive_slots", default=1,
        env_var="ASTERISM_INTERACTIVE_SLOTS", cast=int,
        workspace=workspace,
    )

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
    # Inner warm budget scales with the EFFECTIVE slot count: the warm
    # loop legally tolerates 300s per slot serially, so a flat 600s
    # contradicted our own tolerance at any pool ≥ 2. The daemon's
    # outer wait scales from the CONFIGURED (≥ effective) count and
    # stays the more generous of the two.
    err = _ensure_backend_ready(
        timeout=300.0 * (w_count + n_interactive) + 300.0)
    if err:
        print(f"[gateway] FATAL: {err}", file=sys.stderr, flush=True)
        sys.exit(3)

    print(f"[gateway] worker pool warm, opening HTTP",
          file=sys.stderr, flush=True)
    # HTTP is about to open: /health takes over as the presence signal.
    _marker.unlink(missing_ok=True)

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
    try:
        if sys.platform == "win32":
            import asyncio as _asyncio
            loop = _asyncio.SelectorEventLoop()
            _asyncio.set_event_loop(loop)
            config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                     log_level="warning", loop="none")
            server = uvicorn.Server(config)
            try:
                loop.run_until_complete(server.serve(sockets=[http_sock]))
            finally:
                loop.close()
        else:
            # Non-Windows: manual Server so the pre-bound socket is used.
            config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                    log_level="warning")
            uvicorn.Server(config).run(sockets=[http_sock])
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
