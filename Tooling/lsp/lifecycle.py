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
(by user decision, see docs/archive/lsp_gateway.md §3). Operator should
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
    from ..core import config as _cfg
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

    # Capture gateway subprocess output to a dedicated log file so
    # we get the traceback if it crashes mid-run. Without this, the
    # subprocess inherits parent's stdout/stderr — fine while
    # everything works, but a hard crash + the log being also where
    # the dispatcher writes makes correlation hard. Dedicated log
    # also survives parent's stdout being captured/buffered.
    log_dir = workspace / ".asterism" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    gateway_log = log_dir / "gateway.log"
    gateway_log_fp = open(gateway_log, "ab", buffering=0)
    print(f"[gateway] launching subprocess (port {_gateway_port()}); "
          f"log={gateway_log}", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "Tooling.lsp.gateway"],
        env=env,
        cwd=str(workspace),
        stdout=gateway_log_fp,
        stderr=subprocess.STDOUT,
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


_VERIFY_RETRY_DELAYS: tuple[float, ...] = (5.0, 15.0, 30.0)


def verify_file(target_path: Path,
                *,
                write_olean: bool = True,
                axioms_for: str | None = None,
                timeout: float = 120.0,
                workspace: Path | None = None,
                _retry_delays: tuple[float, ...] | None = None,
                ) -> dict:
    """POST /verify. Single round trip: elaborate `target_path` in a
    gateway worker slot, optionally write the `.olean`, optionally
    run `#print axioms` on a fully-qualified name.

    Returns the gateway's response dict directly:
      {
        ok, diagnostics, diagnostic_count,
        olean_written, olean_path,
        axioms, axiom_error,
        # OR on failure:
        error: str,
        transient: bool,   # True iff retry might succeed
                           # (gateway timeout / unreachable / 5xx);
                           # False for logical errors (4xx / missing
                           # target / malformed response)
      }

    Transient infrastructure failures (URLError / OSError /
    HTTPError 5xx) trigger an in-process retry with exponential
    backoff (5s, 15s, 30s by default). Total retry budget ~50s.
    After the final attempt the dict still carries `transient=True`
    so the caller (see `verify.verify_strategy`) can defer to a
    later dispatcher tick rather than mark the strategy dead.

    Logical errors (target file missing, HTTPError 4xx) are returned
    immediately with `transient=False`.

    `timeout` is the HTTP read budget. The gateway's inner writeOlean /
    printAxioms RPC budget is derived as `max(30, timeout - 30)` — the
    30s slack covers HTTP + slot acquire + elaborate before the RPC
    runs. Library promotion / big-Root callers bump `timeout` to give
    writeOlean enough room to serialize a heavy environment; short-path
    callers stay on the 120s default and get a 90s RPC budget.

    Replaces the older `check_build` + downstream `lake build` +
    `lake env lean #print axioms` chain. ~3-5s on a warm worker
    (Mathlib loaded), vs ~25-50s for the cold-lake path.
    """
    import json
    if not target_path.exists():
        return {"error": f"target file not found: {target_path}",
                "transient": False}
    body: dict = {
        "target_path": str(target_path),
        "write_olean": write_olean,
    }
    if axioms_for:
        body["axioms_for"] = axioms_for
    # Propagate caller's timeout budget into the inner writeOlean /
    # printAxioms RPCs. Reserve a slice for HTTP + slot-acquire +
    # elaborate before the RPC even runs; what remains is the RPC's
    # share. Floor at 30s to preserve prior small-call behavior.
    rpc_share = max(30, int(timeout) - 30)
    body["rpc_timeout"] = rpc_share
    req = urllib.request.Request(
        f"http://127.0.0.1:{_gateway_port(workspace)}/verify",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    delays = _VERIFY_RETRY_DELAYS if _retry_delays is None else _retry_delays
    last_err: dict | None = None
    # One initial attempt + len(delays) retries = len(delays)+1 total
    for attempt in range(len(delays) + 1):
        if attempt > 0:
            time.sleep(delays[attempt - 1])
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body_text = exc.read().decode('utf-8', errors='replace')
            except Exception:
                body_text = ""
            msg = (f"gateway HTTP {exc.code}: {body_text}"
                   if body_text else f"gateway HTTP {exc.code}")
            # 5xx is server-side transient; retry. 4xx is request
            # error; don't retry.
            if 500 <= exc.code < 600:
                last_err = {"error": msg, "transient": True}
                continue
            return {"error": msg, "transient": False}
        except (urllib.error.URLError, OSError) as exc:
            last_err = {"error": f"gateway unreachable: {exc}",
                        "transient": True}
            continue
    # Retries exhausted; return the last transient error verbatim.
    return last_err or {"error": "gateway unreachable (unknown)",
                        "transient": True}


def release_session(token: str) -> None:
    """POST /release/{token}. Idempotent. Best-effort — failure is
    logged but not raised (the daemon teardown path uses this and
    should never crash on a missed release).

    Timeout is generous (30s) because the gateway shares its uvicorn
    event loop between `/release` and `/mcp` traffic; under high
    concurrent MCP load (multiple agents firing apply_edit etc.)
    `/release` can queue behind in-flight tool calls. The handler
    itself is microsecond-scale (one dict pop + a non-blocking lock
    sweep), so a long timeout costs nothing in the typical case but
    avoids spurious warnings + leaked sessions when cascade events
    coincide with peak MCP traffic."""
    if not token:
        return
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{_gateway_port()}/release/{token}",
            method="POST",
        )
        urllib.request.urlopen(req, timeout=30.0).read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"[gateway] release {token[:8]} failed: {exc}", flush=True)
