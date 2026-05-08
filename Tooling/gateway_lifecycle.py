"""Daemon-side hooks to manage the long-living LSP gateway process.

Phase 1: launch as subprocess at daemon startup, poll /health until
backend ready, register atexit shutdown. Subsequent spawns (Builder /
Backward) will register sessions over HTTP and use the gateway URL in
their MCP config.

Behavior:
  - `start_gateway(workspace)`: spawn subprocess, block until /health
    reports `backend_ready=true` (timeout 300s).
  - atexit: SIGTERM the subprocess so daemon shutdown cleans up the
    gateway. Lake serve children will follow.

If the gateway can't start (port in use / lake missing / mathlib
init failure), this raises RuntimeError. Daemon refuses to start
without gateway — Phase 1 has no fallback to per-spawn stdio MCP
(by user decision, see docs/dev/lsp_gateway.md §3). Operator should
fix the underlying issue and retry.
"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _gateway_port(workspace: Path | None = None) -> int:
    """Resolve gateway HTTP port via env / yaml / default chain. Both
    daemon-side (this module) and gateway-side (lsp_gateway.main) read
    the same config so they always agree."""
    from . import config as _cfg
    return _cfg.get(
        "gateway.port", default=8765,
        env_var="ASTERISM_GATEWAY_PORT", cast=int,
        workspace=workspace,
    )


def _health_url() -> str:
    return f"http://127.0.0.1:{_gateway_port()}/health"


def _ping_health(timeout: float = 2.0) -> dict | None:
    """Single /health probe. Returns parsed JSON dict on success,
    None on any error (port not yet listening, JSON garbage, etc.)."""
    import json
    try:
        with urllib.request.urlopen(_health_url(), timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def start_gateway(workspace: Path,
                  ready_timeout: float = 300.0) -> subprocess.Popen:
    """Launch `python -m Tooling.lsp_gateway` as subprocess. Blocks
    until /health reports backend_ready=true. Returns the Popen so
    callers can monitor / kill it. Registers atexit cleanup so daemon
    shutdown propagates."""
    # Refuse if something is already on our port — likely a stale
    # gateway from a prior daemon run that didn't clean up. Operator
    # should kill it and retry.
    pre = _ping_health(timeout=1.0)
    if pre is not None:
        if pre.get("backend_ready"):
            print(f"[gateway] reusing existing gateway on port "
                  f"{_gateway_port()} (already healthy)", flush=True)
            # Don't atexit-kill someone else's process.
            class _Stub:
                def poll(self): return None
                def terminate(self): pass
                def wait(self, timeout=None): return 0
            return _Stub()  # type: ignore[return-value]
        raise RuntimeError(
            f"port {_gateway_port()} occupied by an unhealthy server: "
            f"{pre}; kill it and retry")

    env = dict(os.environ)
    env["ASTERISM_WORKSPACE"] = str(workspace.resolve())
    env["ASTERISM_GATEWAY_PORT"] = str(_gateway_port())
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"[gateway] launching subprocess (port {_gateway_port()}) ...",
          flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "Tooling.lsp_gateway"],
        env=env,
        cwd=str(workspace),
    )

    def _shutdown():
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    atexit.register(_shutdown)

    # Poll /health. Gateway only opens HTTP after backend pre-warm,
    # so any successful response means backend_ready=true (we still
    # check explicitly to be defensive).
    deadline = time.monotonic() + ready_timeout
    last_status = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"gateway subprocess exited rc={proc.returncode} "
                f"during startup (see stderr above)")
        status = _ping_health(timeout=2.0)
        if status is not None and status.get("backend_ready"):
            elapsed = ready_timeout - (deadline - time.monotonic())
            print(f"[gateway] ready after {elapsed:.0f}s", flush=True)
            return proc
        last_status = status
        time.sleep(2.0)
    proc.terminate()
    raise RuntimeError(
        f"gateway not ready within {ready_timeout}s; last_status={last_status}")


def release_session(token: str) -> None:
    """POST /release/{token}. Idempotent. Best-effort — failure is
    logged but not raised (the daemon teardown path uses this and
    should never crash on a missed release)."""
    if not token:
        return
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{_gateway_port()}/release/{token}",
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5.0).read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"[gateway] release {token[:8]} failed: {exc}", flush=True)
