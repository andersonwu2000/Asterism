"""LSP-backed MCP server for Builder pipeline.

Spawned by claude CLI via `--mcp-config`. Holds an `LspClient` (stdio
JSON-RPC connection to `lake serve`) in-process. Exposes 3 MCP tools:

  apply_edit(start_line, end_line, new_text)
    Replace inclusive line range in the target file. Writes through to
    disk + sends `textDocument/didChange`. Returns the post-edit goal
    at line=start_line, col=2 plus full-file diagnostics.

  goal_at(line, col)
    Returns the proof goal state at any position (no edit).

  errors_at(line=None)
    Returns current diagnostics for the file (optionally filtered to
    one line).

Lifecycle: one MCP server per Builder pipeline spawn. claude spawns
us (stdio), we spawn lake serve, we own the LSP session. claude exits
→ atexit → graceful LSP shutdown.

Required env (set by builder.py via mcp_config.json):
  ASTERISM_WORKSPACE   workspace root (where lakefile.lean lives)
  ASTERISM_TARGET      path to the .lean file the agent edits
                       (typically goal_lean = Problems/<p>/proofs/L_*.lean)

Why poll-and-stabilize instead of fileProgress empty: see
`wait_for_diagnostics_settled` docstring. Lean LSP's
`$/lean/fileProgress processing=[]` signal fires before
`textDocument/publishDiagnostics` has finished arriving for
non-trivial proofs (empirically 25s+ for 100-LOC files). Reading
diagnostics on empty signal alone gets stale (often empty) results
— a false-positive bug that masked compile errors in the spike.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

# stdout utf-8 (cp950 on Windows chokes on `⊢` `‖` `ℝ` etc).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ─── LSP JSON-RPC client ───────────────────────────────────────────
# Extracted to Tooling/lsp_client.py (2026-05-08) so the long-living
# gateway server (lsp_gateway.py) can reuse it without importing this
# module's env-var-at-load-time globals.
from .lsp_client import LspClient   # noqa: E402, F401




# ─── MCP server config from env ────────────────────────────────────

WORKSPACE = Path(os.environ["ASTERISM_WORKSPACE"]).resolve()
TARGET_PATH = Path(os.environ["ASTERISM_TARGET"]).resolve()


def _derive_problem_name(workspace: Path, target: Path) -> str:
    """Walk up from `target` until we find a directory whose parent
    equals `workspace / "Problems"`. That directory's name is the
    problem (e.g. `cantor_xi_measure`). Used by `validate_file` to
    auto-prepend `import Problems.<problem>.Defs`."""
    p = target.resolve()
    problems_root = (workspace / "Problems").resolve()
    while p != p.parent:
        if p.parent == problems_root:
            return p.name
        p = p.parent
    return ""


PROBLEM_NAME = _derive_problem_name(WORKSPACE, TARGET_PATH)

# Optional: log file for tool-call forensic. Set by builder.py to
# .attempts/<pid>/_mcp.jsonl. Best-effort; silent if missing or
# unwritable.
_LOG_PATH_ENV = os.environ.get("ASTERISM_MCP_LOG")
LOG_PATH = Path(_LOG_PATH_ENV).resolve() if _LOG_PATH_ENV else None


def _log(event: dict) -> None:
    if LOG_PATH is None:
        return
    event = {"ts": datetime.utcnow().isoformat() + "Z", **event}
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str))
            f.write("\n")
    except Exception:
        pass


# ─── LSP lifecycle: background init ────────────────────────────────
#
# The LSP cold start (load mathlib) takes 25-145s. claude CLI's MCP
# `initialize` handshake has a much shorter timeout, so we can't do
# the slow LSP startup synchronously before calling mcp.run() — claude
# would SIGTERM us mid-startup. Instead: start mcp.run() immediately
# (handshake fast), kick off LSP init in a background thread, and
# block tool calls on `_lsp_ready_event` until init finishes.

_lsp_client: LspClient | None = None
_next_version = 2  # didOpen was version 1
_file_content: str = ""
_lsp_ready_event = threading.Event()
_lsp_init_error: str | None = None


def _bg_init_lsp() -> None:
    global _lsp_client, _file_content, _lsp_init_error
    try:
        t0 = time.perf_counter()
        client = LspClient(WORKSPACE)
        client.start()
        client.initialize(timeout=60)

        if not TARGET_PATH.exists():
            raise FileNotFoundError(f"target file not found: {TARGET_PATH}")
        content = TARGET_PATH.read_text(encoding="utf-8")
        client.did_open(TARGET_PATH, content)

        uri = TARGET_PATH.as_uri()
        try:
            client.wait_for_file_done(uri, timeout=300)
        except TimeoutError:
            pass
        diags = client.wait_for_diagnostics_settled(
            uri, stable_for=3.0, max_wait=300.0
        )
        elapsed = time.perf_counter() - t0
        _lsp_client = client
        _file_content = content
        _log({"event": "lsp_ready", "elapsed_s": elapsed,
              "initial_diagnostic_count": len(diags),
              "initial_lines": len(content.split("\n"))})
        print(f"[lsp_mcp_server] LSP ready in {elapsed:.1f}s",
              file=sys.stderr, flush=True)
    except Exception as e:
        _lsp_init_error = f"{type(e).__name__}: {e}"
        _log({"event": "lsp_init_error", "error": _lsp_init_error})
        print(f"[lsp_mcp_server] LSP init failed: {_lsp_init_error}",
              file=sys.stderr, flush=True)
    finally:
        _lsp_ready_event.set()


def _ensure_lsp_ready(timeout: float = 240.0) -> str | None:
    """Return None on success, error string on failure."""
    if not _lsp_ready_event.wait(timeout=timeout):
        return f"LSP not ready after {timeout}s"
    if _lsp_client is None:
        return _lsp_init_error or "LSP init failed"
    return None


def _shutdown_lsp() -> None:
    if _lsp_client is None:
        return
    _log({"event": "lsp_shutdown"})
    try:
        _lsp_client.shutdown()
    except Exception:
        pass


atexit.register(_shutdown_lsp)


# ─── Helpers ───────────────────────────────────────────────────────

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
    """Mirror of `Tooling.pipeline.backward._ensure_imports_subgoal`.
    Prepends `import Mathlib` and (if the problem ships a Defs.lean)
    `import Problems.<problem>.Defs` when missing. Idempotent.

    Inlined here rather than imported so the MCP server stays
    self-contained (no circular dep on the pipeline package, which
    pulls in the dispatcher / DB layer)."""
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


# ─── MCP tools ─────────────────────────────────────────────────────

from mcp.server.fastmcp import FastMCP   # noqa: E402

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

    This is the primary editing tool. It also writes to disk, so the
    file's on-disk state matches what Lean sees.

    Args:
      start_line: 1-indexed inclusive start of region to replace.
      end_line:   1-indexed inclusive end of region to replace.
      new_text:   Replacement text (may be multi-line).
    """
    global _next_version, _file_content
    err = _ensure_lsp_ready()
    if err:
        return json.dumps({"error": err})
    t0 = time.perf_counter()

    lines = _file_content.split("\n")
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
    _file_content = new_content
    TARGET_PATH.write_text(new_content, encoding="utf-8")

    uri = TARGET_PATH.as_uri()
    _lsp_client.clear_diagnostics(uri)
    _lsp_client.did_change_full(TARGET_PATH, new_content, _next_version)
    _next_version += 1

    try:
        _lsp_client.wait_for_file_done(uri, timeout=10)
    except TimeoutError:
        pass
    diags = _lsp_client.wait_for_diagnostics_settled(
        uri, stable_for=3.0, max_wait=90.0
    )

    try:
        result = _lsp_client.plain_goal(TARGET_PATH,
                                        line=start_line - 1,
                                        character=2,
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
    _log({"event": "tool_call", "name": "apply_edit",
          "args": {"start_line": start_line, "end_line": end_line,
                   "new_text_lines": new_text.count("\n") + 1},
          "duration_s": dur,
          "diagnostic_count": len(diags)})
    return json.dumps(response, ensure_ascii=False)


@mcp.tool()
def goal_at(line: int, col: int) -> str:
    """Get the Lean proof goal state at a specific position. Lines are
    1-indexed; col is 0-indexed character offset (a "  by" line has
    "by" at col 2).

    Args:
      line: 1-indexed line number.
      col:  0-indexed character column.
    """
    err = _ensure_lsp_ready()
    if err:
        return json.dumps({"error": err})
    t0 = time.perf_counter()
    try:
        result = _lsp_client.plain_goal(TARGET_PATH,
                                        line=line - 1, character=col,
                                        timeout=15)
        goal_text = _summarize_goal(result)
    except Exception as e:
        goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
    dur = time.perf_counter() - t0
    _log({"event": "tool_call", "name": "goal_at",
          "args": {"line": line, "col": col},
          "duration_s": dur})
    return json.dumps({"line": line, "col": col, "goal": goal_text},
                      ensure_ascii=False)


@mcp.tool()
def errors_at(line: int | None = None) -> str:
    """Get current diagnostics (errors / warnings) for the file.

    Args:
      line: Optional 1-indexed line. If set, return only diagnostics
            on that line. If None, return all.
    """
    err = _ensure_lsp_ready()
    if err:
        return json.dumps({"error": err})
    t0 = time.perf_counter()
    uri = TARGET_PATH.as_uri()
    diags = _lsp_client.diagnostics_for(uri)
    formatted = [_format_diag(d) for d in diags]
    if line is not None:
        formatted = [f for f in formatted if f["line"] == line]
    dur = time.perf_counter() - t0
    _log({"event": "tool_call", "name": "errors_at",
          "args": {"line": line}, "duration_s": dur,
          "returned_count": len(formatted)})
    return json.dumps({"diagnostics": formatted,
                       "count": len(formatted)},
                      ensure_ascii=False)


@mcp.tool()
def validate_file(content: str) -> str:
    """Validate a candidate Lean file (typically a `new_<slug>.lean`
    sub-goal stub before Backward commits it) against the live LSP.
    Auto-prepends required imports (Mathlib + the problem's Defs if
    any), didOpens at a temp path, waits for diagnostics, then
    closes + deletes.

    Use after writing each `new_<slug>.lean` to catch parse / type
    errors. The in-file `have h_<slug> := by sorry` skeleton check
    on the parent file does NOT cover the standalone-file case
    (separate import context, fresh parser state); a sub-goal stub
    that elaborates inside the parent's body can still fail to
    compile as its own file.

    Args:
      content: Full contents of the candidate file (theorem
               declaration, body = `:= by sorry`). No need to
               include `import Mathlib` etc — the framework adds
               them as it does for committed sub-goal stubs.

    Returns: { ok, diagnostics, diagnostic_count }. `ok` is true iff
    no error-severity diagnostics (sorry warnings tolerated).
    """
    err = _ensure_lsp_ready()
    if err:
        return json.dumps({"error": err})
    if not PROBLEM_NAME:
        return json.dumps({
            "error": "could not derive problem name from target",
        })

    # Place under attempts_dir if known, else workspace root. Lake
    # serve resolves `import Mathlib` / `import Problems.<p>.Defs`
    # via olean lookup, so the file's directory doesn't affect
    # elaboration. Avoids polluting Problems/ with temp files that
    # could be globbed by an out-of-band lake build.
    base_dir = LOG_PATH.parent if LOG_PATH else WORKSPACE
    tmp_path = base_dir / f"_validate_{uuid.uuid4().hex[:8]}.lean"
    full_content = _ensure_imports(content, PROBLEM_NAME, WORKSPACE)

    t0 = time.perf_counter()
    diags: list = []
    elaborate_failed = False
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(full_content, encoding="utf-8")
        uri = tmp_path.as_uri()
        _lsp_client.clear_diagnostics(uri)
        _lsp_client.did_open(tmp_path, full_content)
        try:
            _lsp_client.wait_for_file_done(uri, timeout=15)
        except TimeoutError:
            pass
        diags = _lsp_client.wait_for_diagnostics_settled(
            uri, stable_for=3.0, max_wait=60.0)
        try:
            _lsp_client.notify("textDocument/didClose", {
                "textDocument": {"uri": uri},
            })
        except Exception:
            pass
    except Exception as e:
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
    _log({"event": "tool_call", "name": "validate_file",
          "args": {"content_lines": full_content.count("\n") + 1},
          "duration_s": dur,
          "diagnostic_count": len(formatted),
          "has_error": has_error})
    return json.dumps(response, ensure_ascii=False)


# ─── Entrypoint ────────────────────────────────────────────────────

def main() -> None:
    _log({"event": "mcp_startup",
          "workspace": str(WORKSPACE), "target": str(TARGET_PATH)})
    threading.Thread(target=_bg_init_lsp, daemon=True).start()
    print(f"[lsp_mcp_server] starting MCP stdio server "
          f"(LSP init in bg, target={TARGET_PATH.name})",
          file=sys.stderr, flush=True)
    mcp.run()


if __name__ == "__main__":
    main()
