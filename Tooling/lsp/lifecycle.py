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
import signal
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


def code_fingerprint() -> str:
    """Fingerprint of the Tooling source tree: SHA1 over every .py file's
    (relpath, mtime_ns, size), sorted. The gateway snapshots this at ITS
    start and reports it via /health; a reusing daemon compares against
    the CURRENT tree — any drift means the long-lived gateway process is
    serving stale code (version skew: /health 200 but tool calls 500,
    sphere daemon #5 2026-07-05) and must be relaunched. mtime-based, so
    a plain edit (no commit needed) already flips it; a needless restart
    costs a re-warm, a missed stale gateway costs a broken run."""
    import hashlib
    tooling = Path(__file__).resolve().parents[1]
    h = hashlib.sha1()
    for p in sorted(tooling.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"{p.relative_to(tooling)}|{st.st_mtime_ns}|{st.st_size}\n"
                 .encode("utf-8"))
    return h.hexdigest()


def _ping_health(timeout: float = 2.0) -> dict | None:
    """Single /health probe. Returns parsed JSON dict on success,
    None on any error (port not yet listening, JSON garbage, etc.)."""
    import json
    try:
        with urllib.request.urlopen(_health_url(), timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def _desired_pool(workspace: Path) -> int | None:
    """The worker count a fresh gateway would launch with — i.e. the
    current `dispatch.pool` (gateway.py sizes its pool from this). Returns
    None if config can't be read (then reuse is left as-is, never worse
    than the old unconditional-reuse behaviour)."""
    try:
        from ..core import config
        return config.get("dispatch.pool", default=4, env_var="ASTERISM_POOL",
                          cast=int, workspace=workspace)
    except Exception:  # noqa: BLE001 — config read is best-effort
        return None


def _kill_stale_gateway(pid) -> None:
    """Kill a reused gateway whose worker count no longer matches
    `dispatch.pool`, then wait for the port to free so a fresh gateway can
    bind. `os.kill(pid, SIGTERM)` terminates the process on both POSIX and
    Windows (Windows maps any non-CTRL signal to TerminateProcess)."""
    if not pid:
        raise RuntimeError(
            "existing gateway worker count != dispatch.pool, but its /health "
            "reports no pid (old gateway build) — kill it manually and retry")
    try:
        os.kill(int(pid), signal.SIGTERM)
    except (ProcessLookupError, OSError) as e:
        print(f"[gateway] kill stale gateway pid={pid}: {e} "
              "(already gone?)", flush=True)
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if _ping_health(timeout=1.0) is None:
            return
        time.sleep(0.5)
    raise RuntimeError(
        f"stale gateway pid={pid} did not release port "
        f"{_gateway_port()} within 30s")


def start_gateway(workspace: Path,
                  ready_timeout: float | None = None) -> subprocess.Popen:
    """Launch `python -m Tooling.lsp_gateway` as subprocess. Blocks
    until /health reports backend_ready=true. Returns the Popen so
    callers can monitor / kill it. Registers atexit cleanup so daemon
    shutdown propagates.

    `ready_timeout` (seconds): outer wait budget. Default resolution:
      1. `ASTERISM_GATEWAY_READY_TIMEOUT` env var (operator escape hatch
         for under-spec workstations / cold mathlib caches)
      2. 600.0 — must be ≥ the gateway subprocess's inner
         `_ensure_backend_ready(timeout=600.0)` (gateway.py:1158),
         otherwise the outer wait fires before the inner one even
         had a chance to succeed. Pre-Phase 2 default was 300.0;
         empirically tight on cold mathlib + low-RAM machines (PN
         regression 2026-05-18 hit it with Civ VI / Chrome eating
         ~25 GB).
    """
    if ready_timeout is None:
        env_val = os.environ.get("ASTERISM_GATEWAY_READY_TIMEOUT")
        if env_val:
            try:
                ready_timeout = float(env_val)
            except ValueError:
                pass
        if ready_timeout is None:
            ready_timeout = 600.0
    # A healthy gateway already on our port is reused (warming Mathlib
    # costs minutes, so reuse across runs is a feature) — BUT only if its
    # worker count matches the current `dispatch.pool`. The gateway sizes
    # its worker pool from `dispatch.pool` AT LAUNCH (gateway.py); a
    # gateway started under a different pool (or orphaned across a pool
    # change) keeps a stale count, and reusing it either starves spawns
    # (pool > workers → slot-exhaustion 500s) or wastes workers. Worker
    # count must track the yaml, so on a mismatch we kill the stale
    # gateway and relaunch with the right size.
    pre = _ping_health(timeout=1.0)
    if pre is not None:
        if pre.get("backend_ready"):
            want = _desired_pool(workspace)
            have = pre.get("workers_total")
            gw_fp = pre.get("code_fingerprint")
            cur_fp = code_fingerprint()
            if gw_fp != cur_fp:
                # Version skew: the gateway outlives daemons by design, but
                # a code change since ITS start means it serves stale
                # modules (health 200 / tool calls 500). Missing field =
                # pre-fingerprint build, equally stale.
                print(f"[gateway] existing gateway is version-stale "
                      f"(fingerprint {str(gw_fp)[:12]!r} != current "
                      f"{cur_fp[:12]!r}) — killing it and relaunching on "
                      f"current code", flush=True)
                _kill_stale_gateway(pre.get("pid"))
                # fall through to launch a fresh gateway below
            elif want is not None and have is not None \
                    and int(have) != int(want):
                print(f"[gateway] existing gateway has workers={have} but "
                      f"dispatch.pool={want} — killing it and relaunching to "
                      f"match the yaml", flush=True)
                _kill_stale_gateway(pre.get("pid"))
                # fall through to launch a fresh gateway below
            else:
                print(f"[gateway] reusing existing gateway on port "
                      f"{_gateway_port()} (already healthy, "
                      f"workers={have})", flush=True)
                # Don't atexit-kill someone else's process.
                class _Stub:
                    def poll(self): return None
                    def terminate(self): pass
                    def wait(self, timeout=None): return 0
                return _Stub()  # type: ignore[return-value]
        else:
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
    # The gateway is reused across daemon restarts (warming Mathlib costs
    # minutes), so it must OUTLIVE the daemon. When the daemon has bound itself
    # to a kill-on-close Job Object (`core.process_group`), spawn the gateway
    # with CREATE_BREAKAWAY_FROM_JOB so it escapes that job; otherwise a daemon
    # death would drag the gateway down with it. Gated on `should_breakaway()`:
    # passing the flag when NOT in a breakaway-ok job makes CreateProcess fail.
    from ..core import process_group
    proc = subprocess.Popen(
        [sys.executable, "-m", "Tooling.lsp.gateway"],
        env=env,
        cwd=str(workspace),
        stdout=gateway_log_fp,
        stderr=subprocess.STDOUT,
        creationflags=process_group.breakaway_creationflags(),
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
                constants_for: str | None = None,
                decl_info: bool = False,
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
    if constants_for:
        body["constants_for"] = constants_for
    if decl_info:
        # Per-decl structured facts (`decl_info` + `decl_info_error` in the
        # response) from the `Asterism.declInfo` RPC — the syntactic oracle
        # consumers use instead of regex extraction over source text.
        body["decl_info"] = True
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
                result = json.loads(resp.read().decode("utf-8"))
            # Gateway-flagged transient (e.g. diagnostics unconfirmed on a
            # slot still settling — gateway `_verify_sync`) — retry
            # in-process with backoff like an HTTP 5xx, instead of handing
            # the caller an unreliable verdict it would treat as a build
            # failure. After the retry budget the transient dict is
            # returned verbatim (caller still sees `transient=True`).
            if (isinstance(result, dict) and result.get("transient")
                    and result.get("error")):
                last_err = result
                continue
            return result
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


def verify_in_session(token: str, content: str, *,
                      write_olean: bool = False,
                      axioms_for: str | None = None,
                      decl_info: bool = False,
                      timeout: float = 240.0,
                      workspace: Path | None = None,
                      _retry_delays: tuple[float, ...] | None = None) -> dict:
    """POST /verify_session: verify `content` on the slot CLAIMED by the
    registered session `token` (claimed mode — the session's OWN warm slot,
    no borrow eviction). For framework-side gates that hold a session and
    verify WHOLE-FILE candidates against an already-loaded import closure
    (Library cleanup mechanical gates).

    Same response shape as `verify_file` (`{ok, diagnostics, olean_written,
    axioms, …}`, plus `timed_out`) and the same transient semantics — but
    NO retries by default: the caller (cleanup gate) has a reliable cold
    `lake env lean` fallback, so a transient gateway fault should fail fast to
    cold rather than burn the verify_file retry budget. On gateway-unreachable
    returns `{error, transient=True}`."""
    import json
    if not token:
        return {"error": "no session token", "transient": False}
    # Reserve a slice of the budget for HTTP + slot-acquire before the inner
    # writeOlean / printAxioms RPC (mirrors verify_file); floor 30s.
    rpc_share = max(30, int(timeout) - 30)
    body: dict = {
        "token": token,
        "content": content,
        "write_olean": write_olean,
        "rpc_timeout": rpc_share,
        "wait_timeout": max(60, int(timeout)),
    }
    if axioms_for:
        body["axioms_for"] = axioms_for
    if decl_info:
        body["decl_info"] = True
    req = urllib.request.Request(
        f"http://127.0.0.1:{_gateway_port(workspace)}/verify_session",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Default: no retry → fail fast to the caller's cold fallback.
    delays = () if _retry_delays is None else _retry_delays
    last_err: dict | None = None
    for attempt in range(len(delays) + 1):
        if attempt > 0:
            time.sleep(delays[attempt - 1])
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""
            msg = (f"gateway HTTP {exc.code}: {body_text}"
                   if body_text else f"gateway HTTP {exc.code}")
            if 500 <= exc.code < 600:
                last_err = {"error": msg, "transient": True}
                continue
            return {"error": msg, "transient": False}
        except (urllib.error.URLError, OSError) as exc:
            last_err = {"error": f"gateway unreachable: {exc}",
                        "transient": True}
            continue
    return last_err or {"error": "gateway unreachable (unknown)",
                        "transient": True}


def register_session(*, pipeline_id: str, target_path: Path, problem: str,
                     workspace: Path, log_path: Path | None = None,
                     timeout: float = 30.0) -> "str | None":
    """POST /register to claim a worker slot for a FRAMEWORK-held session and
    return its token (None on ANY failure → caller falls back to cold). Unlike
    `_write_mcp_config` (which also writes the agent's MCP config), this is for
    framework-only sessions with no agent attached: the Library cleanup
    mechanical span holds ONE to verify its whole-file gates on a single warm
    claimed slot (the file's import closure loaded once) instead of a fresh cold
    `lake env lean` per gate. Pair with `release_session`. A pool-exhausted
    register (HTTP 500) or an unreachable gateway both return None — the gate
    then runs cold, never blocks."""
    import json
    if not target_path.exists():
        return None
    body: dict = {"pipeline_id": pipeline_id, "target_path": str(target_path),
                  "problem": problem, "workspace": str(workspace)}
    if log_path is not None:
        body["log_path"] = str(log_path)
    req = urllib.request.Request(
        f"http://127.0.0.1:{_gateway_port(workspace)}/register",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tok = data.get("session_token")
        return tok or None
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


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
