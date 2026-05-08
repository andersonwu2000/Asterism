"""LSP Gateway — long-living HTTP MCP server with shared backend.

Phase 1: K=1 backend, sticky-by-session metadata via X-Asterism-Session
header. Replaces the per-spawn `lsp_mcp_server.py` stdio model — one
gateway process serves all dispatcher pipelines.

Lifecycle:
  1. Daemon startup: launch this module as subprocess.
     `main()` pre-warms one `lake serve` (loads Mathlib ~30-145s cold)
     before opening the HTTP port.
  2. Per-spawn: framework POST /register with {pipeline_id, target_path,
     problem, workspace, log_path?} → returns {session_token}. Gateway
     didOpens the target file on the shared backend, stashes metadata.
  3. claude spawn writes mcp_config.json with X-Asterism-Session header.
     Tool calls (apply_edit / goal_at / errors_at / validate_file)
     resolve their session via the header → metadata lookup.
  4. Spawn end: framework POST /release/{token} to didClose the file
     and free the session slot.

Wire format (MCP):
  POST http://127.0.0.1:8765/mcp
  Header: X-Asterism-Session: <token>
  Body:   JSON-RPC over streamable-http (FastMCP)

Wire format (REST):
  POST /register      JSON body {pipeline_id, target_path, problem,
                                 workspace, log_path?}
  POST /release/{tok} no body
  GET  /health        backend + session counts

See `docs/dev/lsp_gateway.md` for design rationale + Phase 2-4 plan.
"""
from __future__ import annotations

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

from .lsp_client import LspClient


# ─── Session metadata ─────────────────────────────────────────────

@dataclass
class SessionMetadata:
    """Per-spawn state. Lives in `_state.sessions` keyed by session
    token. `file_content` mirrors the on-disk + LSP-known state of
    `target_path`; we apply edits to the in-memory copy first then
    push to LSP + disk."""
    pipeline_id: str
    target_path: Path
    problem: str
    workspace: Path
    log_path: Path | None = None
    file_content: str = ""
    file_version: int = 2  # didOpen was version 1


# ─── Gateway global state ─────────────────────────────────────────

@dataclass
class GatewayState:
    backend: LspClient | None = None
    workspace: Path | None = None
    sessions: dict[str, SessionMetadata] = field(default_factory=dict)
    sessions_lock: threading.Lock = field(default_factory=threading.Lock)
    ready_event: threading.Event = field(default_factory=threading.Event)
    init_error: str | None = None


_state = GatewayState()

# Per-request session token. SessionHeaderMiddleware (below) sets
# this from the X-Asterism-Session header before FastMCP routes the
# tool call; tool bodies read via `_current_session()`.
_session_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "asterism_session", default=None
)


# ─── Logging ────────────────────────────────────────────────────

def _log_for(meta: SessionMetadata | None, event: dict) -> None:
    """Best-effort per-session JSONL log into `meta.log_path` (typically
    `.attempts/<pid>/_mcp.jsonl`). Silent on missing log_path or any
    write failure — never crash a tool call over a log hiccup."""
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


# ─── Backend lifecycle ──────────────────────────────────────────

def _start_backend(workspace: Path) -> None:
    """Pre-warm the LSP backend at gateway startup. Loads Mathlib by
    didOpen-ing a smoke file, blocks until elaborate is done, then
    closes it. Sets `_state.ready_event` regardless of success — error
    case captured in `_state.init_error`.

    Cost: ~30-145s on cold mathlib. Paid once per daemon startup,
    amortized across all subsequent spawns."""
    try:
        t0 = time.perf_counter()
        client = LspClient(workspace)
        client.start()
        client.initialize(timeout=60)

        # Pre-warm Mathlib via a smoke file. The file is in the
        # workspace root (not under Problems/) so it doesn't pollute
        # any problem's tree. didOpen → wait → didClose so LSP fully
        # unloads it after the warm. uuid suffix avoids collision if
        # the workspace already had a `_gateway_smoke.lean` from a
        # prior daemon that didn't clean up (rare but bounded).
        smoke_path = workspace / f"_gateway_smoke_{uuid.uuid4().hex[:8]}.lean"
        smoke_path.write_text("import Mathlib\n", encoding="utf-8")
        try:
            client.did_open(smoke_path, "import Mathlib\n")
            uri = smoke_path.as_uri()
            try:
                client.wait_for_file_done(uri, timeout=300)
            except TimeoutError:
                pass
            client.wait_for_diagnostics_settled(
                uri, stable_for=3.0, max_wait=300.0
            )
            try:
                client.notify("textDocument/didClose",
                              {"textDocument": {"uri": uri}})
            except Exception:
                pass
        finally:
            try:
                smoke_path.unlink()
            except OSError:
                pass

        elapsed = time.perf_counter() - t0
        _state.backend = client
        _state.workspace = workspace
        print(f"[gateway] backend ready in {elapsed:.1f}s",
              file=sys.stderr, flush=True)
    except Exception as e:
        _state.init_error = f"{type(e).__name__}: {e}"
        print(f"[gateway] backend init failed: {_state.init_error}",
              file=sys.stderr, flush=True)
    finally:
        _state.ready_event.set()


def _ensure_backend_ready(timeout: float = 240.0) -> str | None:
    """Block until the bg-init thread reports ready. Returns None on
    success, error string on init failure or timeout."""
    if not _state.ready_event.wait(timeout=timeout):
        return f"backend not ready after {timeout}s"
    if _state.backend is None:
        return _state.init_error or "backend init failed"
    return None


# ─── Session ops (called by REST endpoints) ────────────────────

def _register_session_internal(
    pipeline_id: str, target_path: Path,
    problem: str, workspace: Path,
    log_path: Path | None,
) -> tuple[str, str | None]:
    """Open the target file on the backend, stash metadata, return
    (session_token, error). Synchronous: blocks until didOpen settles
    diagnostics so the first tool call gets accurate state."""
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
        file_version=2,
    )
    backend = _state.backend
    assert backend is not None  # _ensure_backend_ready guarantees
    uri = meta.target_path.as_uri()
    try:
        backend.did_open(meta.target_path, content)
        try:
            backend.wait_for_file_done(uri, timeout=60)
        except TimeoutError:
            pass
        backend.wait_for_diagnostics_settled(
            uri, stable_for=3.0, max_wait=60.0
        )
    except Exception as e:
        # Best-effort didClose so the partial open doesn't leak a
        # file handle on the backend. Failure here is logged-only —
        # we already have the original error to return.
        try:
            backend.notify("textDocument/didClose",
                           {"textDocument": {"uri": uri}})
        except Exception:
            pass
        return "", f"didOpen failed: {type(e).__name__}: {e}"
    with _state.sessions_lock:
        _state.sessions[token] = meta
    _log_for(meta, {"event": "session_registered",
                    "pipeline_id": pipeline_id,
                    "target": str(target_path)})
    return token, None


def _release_session_internal(token: str) -> None:
    """didClose the session's file on the backend, drop the metadata.
    Idempotent — releasing an unknown token is a no-op."""
    with _state.sessions_lock:
        meta = _state.sessions.pop(token, None)
    if meta is None or _state.backend is None:
        return
    try:
        uri = meta.target_path.as_uri()
        _state.backend.notify(
            "textDocument/didClose",
            {"textDocument": {"uri": uri}}
        )
    except Exception:
        pass
    _log_for(meta, {"event": "session_released",
                    "pipeline_id": meta.pipeline_id})


def _current_session() -> SessionMetadata | None:
    """Resolve the calling tool's session via the per-request contextvar
    set by SessionHeaderMiddleware. Returns None if header missing /
    token unknown."""
    token = _session_ctx.get()
    if token is None:
        return None
    with _state.sessions_lock:
        return _state.sessions.get(token)


# ─── Diagnostic + import helpers ───────────────────────────────

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
    `import Mathlib` and `import Problems.<problem>.Defs` (if Defs.lean
    exists) when missing. Idempotent."""
    needed: list[str] = []
    if not re.search(r"(?m)^import\s+Mathlib\b", content):
        needed.append("import Mathlib")
    defs_path = workspace / "Problems" / problem / "Defs.lean"
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


# ─── MCP server + tools ───────────────────────────────────────

mcp = FastMCP("lsp")


@mcp.tool()
def apply_edit(start_line: int, end_line: int, new_text: str) -> str:
    """Replace lines [start_line..end_line] (1-indexed, inclusive) in
    the target Lean file with new_text. Set start_line == end_line to
    replace a single line. new_text may contain multiple lines (use
    literal newlines). To insert without removing, copy the original
    line(s) into new_text alongside your additions.

    Lean re-elaborates after the edit; the response includes:
      - goal_at_edit_start: the proof goal at line=start_line, col=2
      - diagnostics: list of errors / warnings / info in the file
      - diagnostic_count: total

    Args:
      start_line: 1-indexed inclusive start of region to replace.
      end_line:   1-indexed inclusive end of region to replace.
      new_text:   Replacement text (may be multi-line).
    """
    meta = _current_session()
    if meta is None:
        return json.dumps({"error":
            "no session — X-Asterism-Session header missing or unknown"})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err})
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
    meta.file_content = new_content
    meta.target_path.write_text(new_content, encoding="utf-8")

    backend = _state.backend
    assert backend is not None
    uri = meta.target_path.as_uri()
    backend.clear_diagnostics(uri)
    backend.did_change_full(meta.target_path, new_content, meta.file_version)
    meta.file_version += 1

    try:
        backend.wait_for_file_done(uri, timeout=10)
    except TimeoutError:
        pass
    diags = backend.wait_for_diagnostics_settled(
        uri, stable_for=3.0, max_wait=90.0
    )

    try:
        result = backend.plain_goal(meta.target_path,
                                    line=start_line - 1, character=2,
                                    timeout=15)
        goal_text = _summarize_goal(result)
    except Exception as e:
        goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"

    response = {
        "edit": (f"replaced lines {start_line}-{end_line}; "
                 f"file is now {len(new_lines)} lines"),
        "goal_at_edit_start": goal_text,
        "diagnostics": [_format_diag(d) for d in diags],
        "diagnostic_count": len(diags),
    }
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "apply_edit",
                    "args": {"start_line": start_line,
                             "end_line": end_line,
                             "new_text_lines": new_text.count("\n") + 1},
                    "duration_s": dur,
                    "diagnostic_count": len(diags)})
    return json.dumps(response, ensure_ascii=False)


@mcp.tool()
def goal_at(line: int, col: int) -> str:
    """Get the Lean proof goal state at a specific position. Lines are
    1-indexed; col is 0-indexed character offset.

    Args:
      line: 1-indexed line number.
      col:  0-indexed character column.
    """
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session"})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err})
    t0 = time.perf_counter()
    try:
        result = _state.backend.plain_goal(
            meta.target_path, line=line - 1, character=col, timeout=15
        )
        goal_text = _summarize_goal(result)
    except Exception as e:
        goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "goal_at",
                    "args": {"line": line, "col": col},
                    "duration_s": dur})
    return json.dumps({"line": line, "col": col, "goal": goal_text},
                      ensure_ascii=False)


@mcp.tool()
def errors_at(line: int | None = None) -> str:
    """Get current diagnostics for the file.

    Args:
      line: Optional 1-indexed line. If set, return only diagnostics
            on that line. If None, return all.
    """
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session"})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err})
    t0 = time.perf_counter()
    uri = meta.target_path.as_uri()
    diags = _state.backend.diagnostics_for(uri)
    formatted = [_format_diag(d) for d in diags]
    if line is not None:
        formatted = [f for f in formatted if f["line"] == line]
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "errors_at",
                    "args": {"line": line}, "duration_s": dur,
                    "returned_count": len(formatted)})
    return json.dumps({"diagnostics": formatted, "count": len(formatted)},
                      ensure_ascii=False)


@mcp.tool()
def validate_file(content: str) -> str:
    """Validate a candidate Lean file (typically a `new_<slug>.lean`
    sub-goal stub before Backward commits it). Auto-prepends Mathlib +
    the problem's Defs imports, didOpens at a temp path, waits for
    diagnostics, then closes + deletes.

    Args:
      content: Full contents of the candidate file.

    Returns: { ok, diagnostics, diagnostic_count }.
    """
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session"})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err})
    if not meta.problem:
        return json.dumps({"error": "no problem on session metadata"})

    base_dir = meta.log_path.parent if meta.log_path else meta.workspace
    tmp_path = base_dir / f"_validate_{uuid.uuid4().hex[:8]}.lean"
    full_content = _ensure_imports(content, meta.problem, meta.workspace)

    t0 = time.perf_counter()
    diags: list = []
    elaborate_failed = False
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(full_content, encoding="utf-8")
        uri = tmp_path.as_uri()
        backend = _state.backend
        backend.clear_diagnostics(uri)
        backend.did_open(tmp_path, full_content)
        try:
            backend.wait_for_file_done(uri, timeout=15)
        except TimeoutError:
            pass
        diags = backend.wait_for_diagnostics_settled(
            uri, stable_for=3.0, max_wait=60.0
        )
        try:
            backend.notify("textDocument/didClose",
                            {"textDocument": {"uri": uri}})
        except Exception:
            pass
    except Exception:
        elaborate_failed = True
        diags = []
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    formatted = [_format_diag(d) for d in diags]
    has_error = any(f.get("severity") == "error" for f in formatted)
    if elaborate_failed:
        has_error = True
    dur = time.perf_counter() - t0
    response = {
        "ok": not has_error,
        "diagnostic_count": len(formatted),
        "diagnostics": formatted,
    }
    _log_for(meta, {"event": "tool_call", "name": "validate_file",
                    "args": {"content_lines": full_content.count("\n") + 1},
                    "duration_s": dur,
                    "diagnostic_count": len(formatted),
                    "has_error": has_error})
    return json.dumps(response, ensure_ascii=False)


# ─── REST endpoints ─────────────────────────────────────────

@mcp.custom_route("/register", methods=["POST"])
async def register(request: Request):
    """Open a new session. Request body:
      {
        "pipeline_id": str,
        "target_path": str (absolute),
        "problem": str,
        "workspace": str (absolute),
        "log_path": str | null  (optional)
      }
    Response: {"session_token": str}.
    Spawn-time: framework calls this before writing mcp_config.json,
    embeds the returned token in X-Asterism-Session header."""
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
    """Close session's file on backend, free the slot. Idempotent."""
    token = request.path_params["token"]
    _release_session_internal(token)
    return JSONResponse({"ok": True}, status_code=200)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request):
    """Liveness check. Returns backend readiness + active session count."""
    backend_ok = _state.backend is not None
    with _state.sessions_lock:
        n_sessions = len(_state.sessions)
    return JSONResponse({
        "backend_ready": backend_ok,
        "sessions_active": n_sessions,
        "init_error": _state.init_error,
    })


# ─── Session header → contextvar middleware ────────────────────

class SessionHeaderMiddleware:
    """ASGI middleware: read X-Asterism-Session header on incoming HTTP
    requests, set _session_ctx so tool bodies (which run in the same
    asyncio task → same contextvar scope) can resolve their session.

    Why: FastMCP's tool dispatcher doesn't know about HTTP headers;
    contextvar bridges the layer. Each request pushes its own token,
    `finally:` restores the parent scope's token (None for unrelated
    requests like /health)."""
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


# ─── Entrypoint ─────────────────────────────────────────────

def main() -> None:
    workspace_env = os.environ.get("ASTERISM_WORKSPACE")
    if not workspace_env:
        print("[gateway] ASTERISM_WORKSPACE env required",
              file=sys.stderr, flush=True)
        sys.exit(2)
    workspace = Path(workspace_env).resolve()
    port = int(os.environ.get("ASTERISM_GATEWAY_PORT", "8765"))

    print(f"[gateway] starting; workspace={workspace} port={port}",
          file=sys.stderr, flush=True)

    # Pre-warm backend in a background thread; main thread blocks on
    # ready event before opening HTTP. Daemon doesn't see /health
    # until backend is fully warm — keeps startup explicit.
    threading.Thread(target=_start_backend, args=(workspace,),
                     daemon=True).start()
    err = _ensure_backend_ready(timeout=300.0)
    if err:
        print(f"[gateway] FATAL: {err}", file=sys.stderr, flush=True)
        sys.exit(3)

    print(f"[gateway] backend warm, opening HTTP",
          file=sys.stderr, flush=True)

    app = mcp.streamable_http_app()
    app = SessionHeaderMiddleware(app)

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
