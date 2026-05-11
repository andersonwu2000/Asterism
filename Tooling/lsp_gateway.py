"""LSP Gateway — long-living HTTP MCP server with shared worker pool.

Phase 2: 1 server + W persistent workers + content swap on tool call.
N pipelines compete for W workers via tool-call-level LRU (not pipeline
hold). See `docs/dev/lsp_gateway.md` for design rationale.

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

import contextlib
import contextvars
import json
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import db
from .lsp_client import LspClient


# ─── Worker slot ────────────────────────────────────────────────

WARMUP_CONTENT = "import Mathlib\n"


@dataclass
class WorkerSlot:
    """One persistent lean --worker holding a slot URI. Pre-warmed at
    startup with `import Mathlib`; subsequent loads are didChange swaps
    on this URI (~3-4s vs ~27s fresh worker)."""
    slot_id: int
    slot_path: Path
    slot_uri: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Which pipeline's content is currently loaded. None = warmup state
    # (no pipeline content). Set after successful didChange.
    loaded_pipeline_id: str | None = None
    # Monotonic version for LSP didChange. Starts at 2 (didOpen was 1).
    file_version: int = 2
    # Wall-clock time of last release, for LRU eviction.
    last_used_ts: float = 0.0


# ─── Session metadata ────────────────────────────────────────

@dataclass
class SessionMetadata:
    """Per-pipeline state held in gateway. file_content is the mirror
    of the agent's accumulated edits; slot URIs are transient stages
    we push this content onto for elaboration. target_path is the
    real on-disk goal_lean — write-through ensures the framework's
    post-spawn cascade reads the agent's final state."""
    pipeline_id: str
    target_path: Path
    problem: str
    workspace: Path
    log_path: Path | None = None
    file_content: str = ""


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
    # Hot/cold path counters for slot acquire (visible via /health).
    # The cost asymmetry — hot ~0.2s vs cold-swap ~5-30s for complex
    # content — is the dominant framework overhead at pool > W. These
    # let operators measure churn rate directly.
    counters_lock: threading.Lock = field(default_factory=threading.Lock)
    n_hot: int = 0           # slot already loaded with this pipeline's content
    n_cold_warmup: int = 0   # slot had warmup (`import Mathlib\n`) only
    n_cold_evicted: int = 0  # slot held another pipeline's content (real churn)
    n_cold_noswap: int = 0   # swap_in=False (apply_edit / validate_file)
    n_busy_polls: int = 0    # times we slept 0.1s waiting for any free slot


_state = GatewayState()
_session_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "asterism_session", default=None
)


# ─── Logging ─────────────────────────────────────────────

def _log_for(meta: SessionMetadata | None, event: dict) -> None:
    """Best-effort per-session JSONL log. Silent on missing log_path
    or any write failure — never crash a tool call over a log hiccup."""
    if meta is None or meta.log_path is None:
        return
    event = {"ts": datetime.utcnow().isoformat() + "Z", **event}
    try:
        meta.log_path.parent.mkdir(parents=True, exist_ok=True)
        with meta.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str))
            f.write("\n")
    except Exception:
        pass


# ─── Backend + worker pool lifecycle ──────────────────────

def _start_workers(workspace: Path, w_count: int) -> None:
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
        for i in range(w_count):
            slot_path = slots_dir / f"_gateway_slot_{i}.lean"
            slot_path.write_text(WARMUP_CONTENT, encoding="utf-8")
            slot = WorkerSlot(
                slot_id=i,
                slot_path=slot_path,
                slot_uri=slot_path.as_uri(),
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
            except TimeoutError:
                pass
            print(f"[gateway] slot {slot.slot_id} warmed in "
                  f"{time.perf_counter() - t_slot:.1f}s",
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


# ─── Slot acquisition (the heart of Phase 2) ─────────────

@contextlib.contextmanager
def _acquire_slot(meta: SessionMetadata, *, swap_in: bool = True):
    """Borrow a worker slot for this pipeline's content.

    Step 1 (hot path): if any slot is already loaded with this
    pipeline's content AND not busy, grab it. Tool op runs against
    pre-loaded state, no didChange needed.

    Step 2 (cold path): no hot slot available. Pick LRU non-busy slot,
    didChange to meta.file_content (~3-4s), then yield. After release,
    slot is marked as loaded for this pipeline so the next call from
    the same pipeline hits hot path.

    `swap_in=False` skips the didChange — used by apply_edit which
    will overwrite content anyway. After apply_edit, caller marks
    slot as loaded to claim it for this pipeline.

    Locks: per-slot threading.Lock acquired on grab, released on
    yield exit. Holders should be brief (one tool op).
    """
    backend = _state.backend
    if backend is None:
        raise RuntimeError("backend not ready")
    if not _state.workers:
        raise RuntimeError("no workers in pool")

    # Step 1: hot path — slot already loaded with this pipeline's content.
    for slot in _state.workers:
        if slot.loaded_pipeline_id == meta.pipeline_id:
            if slot.lock.acquire(blocking=False):
                # Re-check after lock (avoids TOCTOU vs another thread
                # snatching the slot for a different pipeline).
                if slot.loaded_pipeline_id == meta.pipeline_id:
                    try:
                        with _state.counters_lock:
                            _state.n_hot += 1
                        yield (slot, "hot")
                        slot.last_used_ts = time.time()
                        return
                    finally:
                        slot.lock.release()
                else:
                    slot.lock.release()

    # Step 2: cold path — borrow a slot, swap content if needed.
    # Sort by last_used (LRU); skip locked slots, take the first free one.
    sorted_slots = sorted(_state.workers, key=lambda s: s.last_used_ts)
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        for slot in sorted_slots:
            if slot.lock.acquire(blocking=False):
                try:
                    if swap_in and slot.loaded_pipeline_id != meta.pipeline_id:
                        # Distinguish "first time slot used for any
                        # pipeline" vs "evicting another pipeline's
                        # content". The latter is the real churn cost
                        # of pool > W.
                        if slot.loaded_pipeline_id is None:
                            kind = "cold_warmup"
                            with _state.counters_lock:
                                _state.n_cold_warmup += 1
                        else:
                            kind = "cold_evicted"
                            with _state.counters_lock:
                                _state.n_cold_evicted += 1
                        slot.file_version += 1
                        backend.clear_diagnostics(slot.slot_uri)
                        backend.did_change_full(
                            slot.slot_path, meta.file_content,
                            slot.file_version
                        )
                        try:
                            backend.wait_for_diagnostics(
                                slot.slot_uri, slot.file_version,
                                timeout=120
                            )
                        except (TimeoutError, RuntimeError):
                            pass
                        slot.loaded_pipeline_id = meta.pipeline_id
                    else:
                        # swap_in=False (apply_edit / validate_file
                        # will overwrite content themselves) — caller
                        # got a slot but no swap-in elaborate happened.
                        kind = "cold_noswap"
                        with _state.counters_lock:
                            _state.n_cold_noswap += 1
                    yield (slot, kind)
                    slot.last_used_ts = time.time()
                    return
                finally:
                    slot.lock.release()
        # All slots busy. Wait briefly + retry.
        with _state.counters_lock:
            _state.n_busy_polls += 1
        time.sleep(0.1)
    raise RuntimeError("no slot available within 120s")


# ─── Session ops ────────────────────────────────────

def _register_session_internal(
    pipeline_id: str, target_path: Path,
    problem: str, workspace: Path,
    log_path: Path | None,
) -> tuple[str, str | None]:
    """Stash session metadata. NO didOpen — that's lazy-deferred to
    first tool call (which goes through `_acquire_slot`). Returns
    (session_token, error)."""
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
    )
    with _state.sessions_lock:
        _state.sessions[token] = meta
    _log_for(meta, {"event": "session_registered",
                    "pipeline_id": pipeline_id,
                    "target": str(target_path)})
    return token, None


def _release_session_internal(token: str) -> None:
    """Drop session metadata. NO didClose — slots stay loaded (next
    tool call from another pipeline will swap content as needed).
    Idempotent on unknown tokens."""
    with _state.sessions_lock:
        meta = _state.sessions.pop(token, None)
    if meta is None:
        return
    _log_for(meta, {"event": "session_released",
                    "pipeline_id": meta.pipeline_id})
    # If a slot still claims this pipeline_id, mark as orphan (next
    # acquire will swap it). Don't didChange to warmup eagerly —
    # other pipelines might want this slot's CPU more than warmup.
    for slot in _state.workers:
        if slot.loaded_pipeline_id == meta.pipeline_id:
            # Acquire briefly to safely clear the marker.
            if slot.lock.acquire(blocking=False):
                try:
                    if slot.loaded_pipeline_id == meta.pipeline_id:
                        slot.loaded_pipeline_id = None
                finally:
                    slot.lock.release()


def _current_session() -> SessionMetadata | None:
    token = _session_ctx.get()
    if token is None:
        return None
    with _state.sessions_lock:
        return _state.sessions.get(token)


# ─── Diag + import helpers ─────────────────────────

def _ts_now() -> str:
    """High-precision UTC ISO timestamp for server-side stamping into
    tool responses. Pairs with claude.exe's session jsonl message
    timestamps to localize MCP transport / claude-internal latency
    versus actual gateway processing time. Cheap (<1µs)."""
    return datetime.utcnow().isoformat() + "Z"


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


def _ensure_imports(content: str, problem: str, workspace: Path) -> str:
    """Mirrors `pipeline.backward._ensure_imports_subgoal`: prepends
    `import Mathlib` and `import Problems.<problem>.Defs` (if
    Defs.lean exists) when missing. Idempotent."""
    needed: list[str] = []
    if not re.search(r"(?m)^import\s+Mathlib\b", content):
        needed.append("import Mathlib")
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if defs_path.exists():
        defs_module = f"Problems.{problem}.Defs"
        if not re.search(rf"(?m)^import\s+{re.escape(defs_module)}\b",
                         content):
            needed.append(f"import {defs_module}")
    if not needed:
        return content
    return "\n".join(needed) + "\n\n" + content


def _summarize_goal(result) -> str:
    if not isinstance(result, dict):
        return str(result)
    rendered = result.get("rendered")
    if rendered:
        return rendered
    goals = result.get("goals") or []
    if goals:
        return "\n---\n".join(goals)
    return "<no goals — proof complete at this position>"


# ─── MCP tools ───────────────────────────────────

mcp = FastMCP("lsp")


@mcp.tool()
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

    lines = meta.file_content.split("\n")
    if start_line < 1 or start_line > len(lines):
        return json.dumps({"error":
            f"start_line {start_line} out of range 1..{len(lines)}"})
    if end_line < start_line or end_line > len(lines):
        return json.dumps({"error":
            f"end_line {end_line} out of range {start_line}..{len(lines)}"})

    new_lines = (lines[: start_line - 1]
                 + new_text.split("\n")
                 + lines[end_line:])
    new_content = "\n".join(new_lines)

    backend = _state.backend
    # apply_edit overwrites slot content anyway → skip swap-in.
    with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
        slot.file_version += 1
        backend.clear_diagnostics(slot.slot_uri)
        backend.did_change_full(slot.slot_path, new_content,
                                slot.file_version)
        # `textDocument/waitForDiagnostics` blocks server-side until
        # the doc reaches our version, the reporter has flushed all
        # publishDiagnostics for it, and all command snapshots have
        # elaborated. Replaces the prior fileProgress + 3s-settle
        # polling, which over-waited by ~3s on every tool call.
        try:
            backend.wait_for_diagnostics(slot.slot_uri, slot.file_version,
                                          timeout=120)
        except (TimeoutError, RuntimeError):
            pass
        diags = backend.diagnostics_for(slot.slot_uri)
        try:
            result = backend.plain_goal(slot.slot_path,
                                         line=start_line - 1, character=2,
                                         timeout=15)
            goal_text = _summarize_goal(result)
        except Exception as e:
            goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
        # Mark slot as loaded with this pipeline's NEW content.
        slot.loaded_pipeline_id = meta.pipeline_id

    # Update mirror + write through to disk so framework cascade sees
    # the agent's edits.
    meta.file_content = new_content
    meta.target_path.write_text(new_content, encoding="utf-8")

    response = {
        "edit": (f"replaced lines {start_line}-{end_line}; "
                 f"file is now {len(new_lines)} lines"),
        "goal_at_edit_start": goal_text,
        "diagnostics": [_format_diag(d) for d in diags],
        "diagnostic_count": len(diags),
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "apply_edit",
                    "args": {"start_line": start_line,
                             "end_line": end_line,
                             "new_text_lines": new_text.count("\n") + 1},
                    "duration_s": dur,
                    "slot_kind": _slot_kind,
                    "diagnostic_count": len(diags)})
    return json.dumps(response, ensure_ascii=False)


@mcp.tool()
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
    with _acquire_slot(meta, swap_in=True) as (slot, _slot_kind):
        try:
            result = backend.plain_goal(
                slot.slot_path, line=line - 1, character=col, timeout=15
            )
            goal_text = _summarize_goal(result)
        except Exception as e:
            goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "goal_at",
                    "args": {"line": line, "col": col},
                    "duration_s": dur,
                    "slot_kind": _slot_kind})
    return json.dumps({"line": line, "col": col, "goal": goal_text,
                       "_server_recv_ts": _recv_ts,
                       "_server_send_ts": _ts_now()},
                      ensure_ascii=False)


@mcp.tool()
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
    with _acquire_slot(meta, swap_in=True) as (slot, _slot_kind):
        diags = backend.diagnostics_for(slot.slot_uri)
        formatted = [_format_diag(d) for d in diags]
    if line is not None:
        formatted = [f for f in formatted if f["line"] == line]
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "errors_at",
                    "args": {"line": line}, "duration_s": dur,
                    "slot_kind": _slot_kind,
                    "returned_count": len(formatted)})
    return json.dumps({"diagnostics": formatted, "count": len(formatted),
                       "_server_recv_ts": _recv_ts,
                       "_server_send_ts": _ts_now()},
                      ensure_ascii=False)


@mcp.tool()
def validate_file(content: str) -> str:
    """Validate a candidate Lean file (typically a `new_<slug>.lean`
    sub-goal stub). Auto-prepends Mathlib + the problem's Defs imports,
    pushes the candidate content onto a borrowed slot, reads diagnostics,
    leaves the slot dirty (next caller will swap content as needed).

    Args:
      content: Full contents of the candidate file.

    Returns: { ok, diagnostics, diagnostic_count }.
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
    full_content = _ensure_imports(content, meta.problem, meta.workspace)

    t0 = time.perf_counter()
    diags: list = []
    elaborate_failed = False
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
                pass
            diags = backend.diagnostics_for(slot.slot_uri)
            # Mark slot as orphan: validate_file's content isn't the
            # session's "real" mirror, just a probe; future tool calls
            # from this session will didChange back to file_content.
            slot.loaded_pipeline_id = None
    except Exception:
        elaborate_failed = True
        diags = []

    formatted = [_format_diag(d) for d in diags]
    has_error = any(f.get("severity") == "error" for f in formatted)
    if elaborate_failed:
        has_error = True
    dur = time.perf_counter() - t0
    response = {
        "ok": not has_error,
        "diagnostic_count": len(formatted),
        "diagnostics": formatted,
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    _log_for(meta, {"event": "tool_call", "name": "validate_file",
                    "args": {"content_lines": full_content.count("\n") + 1},
                    "duration_s": dur,
                    "slot_kind": _slot_kind,
                    "diagnostic_count": len(formatted),
                    "has_error": has_error})
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
    token, err = _register_session_internal(
        pipeline_id=str(data["pipeline_id"]),
        target_path=Path(data["target_path"]),
        problem=str(data["problem"]),
        workspace=Path(data["workspace"]),
        log_path=Path(log_path) if log_path else None,
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


@mcp.custom_route("/verify", methods=["POST"])
async def verify(request: Request):
    """Unified verify endpoint: didChange the file's content into a
    worker slot, optionally write the resulting `.olean` to disk,
    optionally run `Asterism.printAxioms` on a constant in it.

    Body: {
      "target_path":  "/abs/path.lean",        # required
      "write_olean":  true,                    # default: true
      "axioms_for":   "Problems.foo.main",     # optional fq name
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
    }

    Replaces the prior `lake build` + `lake env lean #print axioms`
    pair: the verify, the olean publish, and the axiom probe all run
    in the same worker process against the same just-elaborated
    environment.

    Slot ownership: marks loaded_pipeline_id=None after the call so
    the next caller doesn't think this content "belongs" to anyone.
    """
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
    # Caller-driven RPC timeout. Default 30 preserves prior behavior;
    # library promotion / big-Root callers bump this via verify_file's
    # `timeout` argument (minus HTTP overhead). Clamp to a positive
    # integer; fall through on bad input.
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
    diags: list = []

    try:
        with _acquire_slot(meta, swap_in=True) as (slot, _slot_kind):
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

            slot.loaded_pipeline_id = None
    except Exception as e:
        return JSONResponse(
            {"error": f"slot acquire failed: {type(e).__name__}: {e}"},
            status_code=500,
        )

    formatted = [_format_diag(d) for d in diags]
    has_error = any(f.get("severity") == "error" for f in formatted)
    return JSONResponse({
        "ok": not has_error,
        "diagnostic_count": len(formatted),
        "diagnostics": formatted,
        "olean_written": olean_written,
        "olean_path": str(olean_path) if olean_path else None,
        "axioms": axioms,
        "axiom_error": axiom_error,
    })


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request):
    """Liveness check. Reports worker pool status + active sessions
    + slot acquire counters (so operator can compute hot/cold ratio
    over the run, especially relevant at pool > W where churn
    dominates framework overhead)."""
    backend_ok = _state.backend is not None and bool(_state.workers)
    with _state.sessions_lock:
        n_sessions = len(_state.sessions)
    n_workers = len(_state.workers)
    n_busy = sum(1 for s in _state.workers if s.lock.locked())
    with _state.counters_lock:
        counters = {
            "n_hot": _state.n_hot,
            "n_cold_warmup": _state.n_cold_warmup,
            "n_cold_evicted": _state.n_cold_evicted,
            "n_cold_noswap": _state.n_cold_noswap,
            "n_busy_polls": _state.n_busy_polls,
        }
    total_acq = (counters["n_hot"] + counters["n_cold_warmup"]
                 + counters["n_cold_evicted"] + counters["n_cold_noswap"])
    counters["hot_rate"] = (
        counters["n_hot"] / total_acq if total_acq else None
    )
    return JSONResponse({
        "backend_ready": backend_ok,
        "workers_total": n_workers,
        "workers_busy": n_busy,
        "sessions_active": n_sessions,
        "init_error": _state.init_error,
        "acquires": counters,
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
    from . import config as _cfg
    port = _cfg.get(
        "gateway.port", default=8765,
        env_var="ASTERISM_GATEWAY_PORT", cast=int,
        workspace=workspace,
    )
    w_count = _cfg.get(
        "gateway.workers", default=4,
        env_var="ASTERISM_GATEWAY_WORKERS", cast=int,
        workspace=workspace,
    )

    print(f"[gateway] starting; workspace={workspace} port={port} "
          f"workers={w_count}",
          file=sys.stderr, flush=True)

    threading.Thread(target=_start_workers, args=(workspace, w_count),
                     daemon=True).start()
    err = _ensure_backend_ready(timeout=600.0)
    if err:
        print(f"[gateway] FATAL: {err}", file=sys.stderr, flush=True)
        sys.exit(3)

    print(f"[gateway] worker pool warm, opening HTTP",
          file=sys.stderr, flush=True)

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
    if sys.platform == "win32":
        import asyncio as _asyncio
        loop = _asyncio.SelectorEventLoop()
        _asyncio.set_event_loop(loop)
        config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                 log_level="warning", loop="none")
        server = uvicorn.Server(config)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()
    else:
        # Non-Windows: stock uvicorn.run is fine; no IOCP race.
        uvicorn.run(app, host="127.0.0.1", port=port,
                    log_level="warning")


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
