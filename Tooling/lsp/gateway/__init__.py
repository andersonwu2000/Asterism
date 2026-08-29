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
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse


# ─── Package facade (2026-08-29: gateway.py → gateway/, splits A1-1..4b) ─
#
# Twelve axes moved into their own modules; what is left here is the
# HTTP surface itself — every `@mcp.custom_route`, the session-header
# middleware and `main()`. The names below are the ones code still in
# THIS file resolves by bare name, plus the ones callers
# and tests reach as `gateway.X`. Names whose only consumers live inside
# the moved module are deliberately absent, so a monkeypatch aimed at
# the facade fails loudly instead of becoming a silent no-op: patch
# `gateway.elab._ELAB_SEM` / `_ELAB_QUEUE_TIMEOUT_SEC`,
# `gateway.backend._await_backend` / `_start_workers` (for
# `_restart_backend`'s call), `gateway.weigh._slot_private_mb` (for
# `_slot_private_mb_cached`'s call), `gateway.sessions._owner_alive` /
# `_SWEEP_INTERVAL_SEC`, `gateway.leantext._DECL_SLUG_RE_TMPL` /
# `_needed_imports` / `_proved_sibling_import_lines` / `_SCOPE_*`,
# `gateway.rpc.ELAB_WALL_*` / `_ECHO_END_CHARS` / `_HB_*`,
# `gateway.gates._gw_leading_comments` / `_AXIOM_PROBE_DECL_CAP`,
# `gateway.verify._olean_dest_for`, and
# everything the governor alone consumes — `gateway.governor.
# _PRESSURE_DEBT` (rebound under `global`, so a facade patch reads back
# nothing), its kill/weigh helpers (`_await_worker_exit`,
# `_kill_worker_for_uri`, `_worker_pid_for_uri`, `_machine_gb`,
# `_slot_private_mb_fresh`), its histories and its thresholds — on the
# owning module.
#
# A module-level `from .x import name` COPIES the binding, so the patch
# target of a shared name is the CONSUMING module, not the defining one.
# `_ensure_backend_ready` is the split-brain example, four-sided as of
# cut 4b: the two /verify routes here read this facade, `validate_file`
# reads `gateway.verify`, `_register_session_internal` reads
# `gateway.sessions`, the four tools read `gateway.rpc`.
# `_current_session` and `_compilation_for` took the same shape with cut
# 4a, and `_build_compilation_unit` follows `validate_file` to
# `gateway.verify` with 4b. `_slot_private_mb_cached` and
# `_kick_warm_converger` stay double-bound because the /warm_target
# route here consumes both and the governor consumes both there. Patch
# the side whose consumer the test drives.
#
# All the reach-backs are gone. `_compilation_for` (governor + sessions)
# and `_log_for` (register/release) closed with 4a; the last one ran the
# other way — `rpc.apply_edit` imported the submission gates
# (`_citation_submission`, `_locked_signature_submission`) from HERE at
# CALL time because they had not moved yet. With 4b they are in
# `gates.py`, `rpc` imports them at module level, and every import in
# this package now resolves before anything runs.
#
# `_offload_to_thread` and `mcp` live in `server.py` for one reason: a
# decorator has to resolve before this module finishes executing, and
# `rpc`'s four tools plus `verify`'s `validate_file` wear both.
# `gateway.mcp` is the same FastMCP object it always was, and the tool
# roster is unchanged at five.
#
# The `/health` route handler is `health_route`, NOT `health`, and the
# `/verify` handler is `verify_route`, NOT `verify` — the bare names
# would have shadowed the `health` / `verify` submodules on the package
# namespace and turned `monkeypatch.setattr(gateway.health, ...)` /
# `(gateway.verify, ...)` into silent no-ops against a coroutine
# function. `verify_session` needs no such suffix: no submodule of that
# name exists.

from .state import (
    WARMUP_CONTENT,
    WorkerSlot,
    SessionMetadata,
    GatewayState,
    _state,
    _session_ctx,
    _log_for,
    _ts_now,
)
from .elab import (
    ELAB_CREDIT_FILENAME,
    _elab_gate,
    elab_gate_stats,
)
from .backend import (
    WARMING_MSG,
    _start_workers,
    _ensure_backend_ready,
    _watch_initial_warm,
    _restart_backend,
)
from .weigh import (
    _slot_private_mb_cached,
    _SLOT_MB_CACHE,
)
from .governor import (
    SLOT_RECYCLE_MB_DEFAULT,
    WORKER_EXIT_WAIT_SEC,
    _GOVERNOR_INTERVAL_SEC,
    _pressure_debt,
    _pressure_outlet_step,
    _effective_target,
    _weight_kill_over_cap,
    _weight_watchdog_run,
    _recycle_wedged_slot,
    _wedge_watchdog_loop,
    _recycle_slot_if_heavy,
    _open_pipeline_slots_locked,
    _shed_slot_if_over_target,
    _midlease_residue_mb,
    _maybe_kick_midlease_rewarm,
    _midlease_rewarm_run,
    _freeze_tick,
    _kick_warm_converger,
    _warm_converger_run,
)
from .sessions import (
    _LEASE_TTL_SEC,
    _borrow_order,
    _acquire_slot,
    _register_session_internal,
    _release_session_internal,
    _current_session,
    _sweep_stale_claims,
    _stale_claim_sweep_loop,
)
from .health import (
    _HEALTH_SNAPSHOT,
    _HEALTH_SNAPSHOT_LOCK,
    _health_payload,
)
from .leantext import (
    _format_diag,
    _collapse_repeats,
    _metaprog_error,
    _ensure_imports,
    _inline_sibling_stubs,
    _collect_referenced_sibling_stubs,
    _toposort_siblings,
    _harvest_open_lines,
    _merge_opens,
    _parity_for,
    _build_compilation_unit,
    _commit_header_for,
    _merged_line_for,
    _compilation_for,
    _remap_inlined_diags,
    _summarize_goal,
    _goal_present,
    _sorry_start_col,
    _stub_fingerprint,
    _resync_buffer_from_disk,
    _scope_balance,
)
from .server import (
    mcp,
    _offload_to_thread,
)
from .rpc import (
    apply_edit,
    goal_at,
    errors_at,
    withdraw_stub,
    _echo_removed,
    _arg_help,
    _await_elaboration,
    _hb_rank,
    _hb_declared,
    _note_diagnostics,
    _heartbeat_gate,
    _GOAL_AT_EDIT_END_NOTE,
)
from .gates import (
    _GW_PROBLEM_IMPORT_RE,
    _GW_THEOREM_RE,
    _GW_SORRY_STUB_RE,
    _GW_SLUG_RE,
    _GW_DECL_HEAD_RE,
    _citation_submission,
    _annotation_submission,
    _locked_signature_submission,
    _stale_olean_submission,
    _slug_collision_submission,
    _declhead_submission,
    _GW_DECLINE_RE,
    _namespace_submission,
    _axioms_submission,
)
from .verify import (
    validate_file,
    _interactive_meta,
    _verify_sync,
    _verify_session_sync,
)


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
    try:
        _goal_id = int(data["goal_id"]) if data.get("goal_id") else None
    except (TypeError, ValueError):
        _goal_id = None
    token, err = _register_session_internal(
        pipeline_id=str(data["pipeline_id"]),
        target_path=Path(data["target_path"]),
        problem=str(data["problem"]),
        workspace=Path(data["workspace"]),
        log_path=Path(log_path) if log_path else None,
        kind=str(kind) if kind else None,
        goal_id=_goal_id,
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
            with _elab_gate(slot.slot_uri, meta):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                merged, _line_map = _compilation_for(meta)
                backend.did_change_full(slot.slot_path, merged,
                                        slot.file_version)
                converged, _wall = _await_elaboration(backend, slot, meta)
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
        # The wall hit: the worker was reclaimed and the empty list is a
        # FAILURE, not "no news yet" (owner design 2026-08-29).
        resp["note"] = (_wall or {}).get("teaching") or "elaboration wall hit"
        resp["elab_wall"] = _wall
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


@mcp.custom_route("/verify", methods=["POST"])
async def verify_route(request: Request):
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
    from ...sandbox import run as _sandbox_run
    try:
        res = await asyncio.to_thread(_sandbox_run, code)
    except Exception as e:  # noqa: BLE001 — reported, never swallowed
        return JSONResponse(
            {"rc": 1, "output": f"[compute] gateway-side failure: "
                                f"{type(e).__name__}: {e}", "seconds": 0.0})
    return JSONResponse({"rc": res.rc, "output": res.output,
                         "seconds": res.seconds, "killed": res.killed})


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
        from ...core.ram_ledger import MAX_SLOTS
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
async def health_route(request: Request):
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
    # Snapshot fast-path (owner approval 2026-08-27): the governor
    # thread rebuilds the payload every pass, so a /health under a
    # saturated accept queue costs the event loop a dict lookup, not a
    # pool walk — status polling stops feeding the very backlog it is
    # trying to observe (flagship: accept queue 157 deep at 83% CPU).
    with _HEALTH_SNAPSHOT_LOCK:
        snap_at = _HEALTH_SNAPSHOT["at"]
        snap = _HEALTH_SNAPSHOT["val"]
    age = time.monotonic() - snap_at
    if snap is not None and age < 3 * _GOVERNOR_INTERVAL_SEC:
        return JSONResponse({**snap, "snapshot_age_s": round(age, 1)})
    # Governor hiccup: compute inline rather than serve a dead reading.
    return JSONResponse({**_health_payload(), "snapshot_age_s": 0.0})


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
    from ...core import config as _cfg
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
        from ...core import ram_ledger as _rl
        _budget_gb = _rl.parse_budget(_rl.env_budget_spec(workspace),
                                      _rl.total_gb())
    except Exception:  # noqa: BLE001 — the ledger must not stop launch
        _budget_gb = None
    _state.ram_budget_gb = _budget_gb   # the freezer reads this
    if _budget_gb is not None:
        _target0 = _rl.compute_target_slots(budget_gb=_budget_gb,
                                            nl_demand=0)
        # Launch warms the ledger's OPENING bid (min(lanes, RAM target));
        # the daemon's ramp pushes the climb one slot per calm minute.
        w_count = max(1, min(_rl.elab_lanes(), _target0))
        _state.warm_target = w_count
        print(f"[gateway] RAM ledger active — budget {_budget_gb:.1f} GB,"
              f" launch warms {w_count} slot(s) (lanes {_rl.elab_lanes()}),"
              f" RAM target {_target0}; the ramp climbs on measured calm",
              file=sys.stderr, flush=True)
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
    from ..lifecycle import ram_clamped_pool
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
    from ..lifecycle import gateway_starting_marker
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
    # Cross-platform memory-cap enforcement (the Windows Job Object
    # does not exist off-Windows; see _weight_kill_over_cap).
    threading.Thread(target=_weight_watchdog_run,
                     name="weight-watchdog", daemon=True).start()
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
