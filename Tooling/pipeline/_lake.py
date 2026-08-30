"""Lake-build helpers — shell out to `lake build` and parse rc.

Extracted from `pipeline/__init__.py`. Pure module: no DB,
no agent, no provider — depends only on subprocess + Path. The build
GATE (below) is injected by the dispatcher; the default gate needs
nothing but a lock.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import Future
from pathlib import Path

from ..core.process_group import no_window_creationflags


def lean_path_to_module(workspace: Path, lean_path: Path) -> str:
    """Convert workspace-relative .lean path to lean module name.
    Problems/wilson/Root.lean → Problems.wilson.Root
    Problems/wilson/proofs/L_x.lean → Problems.wilson.proofs.L_x
    """
    rel = lean_path.relative_to(workspace).with_suffix("")
    return ".".join(rel.parts)


#: Upper bound on the joined `lake build <modules...>` command line per
#: subprocess call. Windows CreateProcess rejects command lines over
#: 32,767 chars with WinError 206 ("filename or extension too long");
#: 2026-08-29 the dedupe pre-flight passed a few hundred union_closed
#: proof modules (4,206 on disk, ~69 chars each, max 118) in ONE call,
#: tripped the limit, and — because the pre-flight is best-effort — the
#: whole defeq probe silently fail-opened (all 9,696 pairs refused,
#: alias=0) for days. The budget is deliberately far below the OS limit
#: so `lake`'s own argv handling never becomes the next ceiling; POSIX
#: ARG_MAX is much larger, but one shape everywhere keeps the test honest.
LAKE_CMDLINE_BUDGET = 8000

#: Per-invocation build wall (the subprocess only — queueing for the
#: gate is NOT counted; a saturated queue fails with its own message).
LAKE_BUILD_TIMEOUT_SEC = 600


def chunk_modules_for_cmdline(modules: list[str],
                              budget: int = LAKE_CMDLINE_BUDGET
                              ) -> list[list[str]]:
    """Split `modules` into consecutive chunks whose joined argv
    (`lake build m1 m2 ...`, space-separated) stays within `budget`
    chars. Order is preserved; every module lands in exactly one chunk;
    a single module longer than the budget still gets its own chunk
    (lake, not us, decides whether that name is buildable)."""
    base = len("lake build")
    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_len = base
    for m in modules:
        add = len(m) + 1
        if cur and cur_len + add > budget:
            chunks.append(cur)
            cur, cur_len = [], base
        cur.append(m)
        cur_len += add
    if cur:
        chunks.append(cur)
    return chunks


# ─── The build gate (owner ruling 2026-08-30) ───────────────────────
#
# Flagship 16 OCPU / 125 GB, 00:00Z: the daemon ran 13 `lake build`s at
# once — two with byte-identical module lists — and Lake 5, which has
# no `--jobs`, let each fan `lean` compiles (6.8 GB apiece) over every
# core beside the 14 elaboration lanes the gateway DID bound: load 217,
# 108 batch compiles, 4 GB left. Every daemon-side build funnels
# through `lake_build_modules`; that one door now
#   1. coalesces identical module lists (the second caller waits for
#      the first build's result),
#   2. runs under a LEASE that says how many threads Lake may use —
#      `LEAN_NUM_THREADS`, the Lean runtime's knob and the only one —
#      and that, with the gateway gate, is borrowed from the SAME lane
#      pool the elaborations queue on (one CPU budget, two consumers),
#   3. names queueing and building as different failures.
# RAM admission for a build lives beside the CPU lease: the dispatcher
# hands the gateway gate a `ram_fit(threads)` reading (the ledger's
# headroom against the calm watermark, in compiles) that SHRINKS the
# lane request — never below one, never blocking: lanes are what a
# build waits for, RAM only sizes it.


def default_build_threads() -> int:
    """Half the elaboration lanes (`ram_ledger.elab_lanes` formula,
    kept import-free here), never below one."""
    env = os.environ.get("ASTERISM_BUILD_LANES")
    try:
        if env and int(env) > 0:
            return int(env)
    except ValueError:
        pass
    lanes = max(2, (os.cpu_count() or 4) - 2)
    return max(1, lanes // 2)


class BuildLease:
    def __init__(self, threads: int, release, renew=None):
        self.threads = max(1, int(threads))
        self._release = release
        self._renew = renew

    def renew(self) -> None:
        if self._renew is not None:
            self._renew()

    def release(self) -> None:
        self._release()


class BuildQueueSaturated(RuntimeError):
    pass


class LocalBuildGate:
    """In-process gate: one build at a time, a fixed thread count. The
    default when no dispatcher installed anything (CLI tools, tests),
    and the fallback while the gateway is unreachable."""

    def __init__(self, threads: "int | None" = None):
        self.threads = int(threads) if threads else default_build_threads()
        self._lock = threading.Lock()

    def acquire(self, threads: int, hint: str = "") -> BuildLease:
        self._lock.acquire()
        return BuildLease(min(self.threads, max(1, int(threads))),
                          release=self._lock.release)


def _http_post_json(url: str, payload: dict, timeout: float
                    ) -> "tuple[int, dict]":
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            data = {}
        return e.code, data


def lease_heartbeat_period(ttl_s: float) -> float:
    """Renew every quarter of the TTL (never under 5s): two renews may
    be lost to a stalled gateway loop before a live build's lease
    expires under it. The server side of the same contract is
    `elab._default_build_lease_ttl_sec`."""
    return max(5.0, float(ttl_s) / 4.0)


class GatewayBuildGate:
    """Borrow build lanes from the gateway's elaboration gate
    (`POST /build/lease`, 409 = nothing free, poll). Renews the lease
    on a timer while the build runs; releases on exit; a gateway that
    cannot be reached bounds the build locally instead of stalling the
    daemon (the lease's TTL on the gateway side covers the reverse
    failure — a dead daemon)."""

    def __init__(self, base_url: str, *, owner: str, ram_fit=None,
                 poll_sec: float = 3.0, queue_timeout_sec: float = 900.0,
                 post=_http_post_json, local_threads: "int | None" = None,
                 http_timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.owner = str(owner)
        #: `ram_fit(threads) -> int`: how many of the wanted threads the
        #: RAM ledger says fit right now (≥ 1). Shrinks the request; the
        #: lanes are what a build waits for, never RAM.
        self.ram_fit = ram_fit
        self.poll_sec = float(poll_sec)
        self.queue_timeout_sec = float(queue_timeout_sec)
        self._post = post
        self._http_timeout = float(http_timeout)
        self._local = LocalBuildGate(local_threads)
        self._unreachable_logged = False

    def acquire(self, threads: int, hint: str = "") -> BuildLease:
        t0 = time.monotonic()
        want = max(1, int(threads))
        while True:
            waited = time.monotonic() - t0
            if waited > self.queue_timeout_sec:
                raise BuildQueueSaturated(
                    f"build queue saturated — waited {waited:.0f}s for a "
                    f"build lease ({want} thread(s), {hint!r}); the machine "
                    f"is over capacity, not this build")
            ask = want
            if self.ram_fit is not None:
                try:
                    ask = max(1, min(want, int(self.ram_fit(want))))
                except Exception:  # noqa: BLE001 — a broken reading never blocks a build
                    ask = want
            try:
                status, data = self._post(
                    f"{self.base_url}/build/lease",
                    {"threads": ask, "owner": self.owner, "hint": hint},
                    self._http_timeout)
            except (OSError, ValueError) as e:
                if not self._unreachable_logged:
                    print(f"[lake] gateway unreachable for a build lease "
                          f"({e}); bounding builds locally at "
                          f"{self._local.threads} thread(s) until it "
                          f"answers", flush=True)
                    self._unreachable_logged = True
                return self._local.acquire(want, hint)
            self._unreachable_logged = False
            if status == 200 and data.get("token"):
                return self._leased(str(data["token"]), int(data.get("threads") or 1),
                                    float(data.get("ttl_s") or 900.0))
            retry = float((data or {}).get("retry_after_s") or self.poll_sec)
            time.sleep(max(0.01, min(retry, self.poll_sec)))

    def _leased(self, token: str, threads: int, ttl_s: float) -> BuildLease:
        stop = threading.Event()

        def renew():
            try:
                self._post(f"{self.base_url}/build/lease/{token}/renew", {},
                           self._http_timeout)
            except (OSError, ValueError):
                pass

        def heartbeat():
            period = lease_heartbeat_period(ttl_s)
            while not stop.wait(period):
                renew()

        def release():
            stop.set()
            try:
                self._post(f"{self.base_url}/build/release/{token}", {},
                           self._http_timeout)
            except (OSError, ValueError):
                pass  # the TTL returns the lanes

        threading.Thread(target=heartbeat, name=f"build-lease-{token[:8]}",
                         daemon=True).start()
        return BuildLease(threads, release=release, renew=renew)


_GATE: "LocalBuildGate | GatewayBuildGate | None" = None
_GATE_LOCK = threading.Lock()
_INFLIGHT: "dict[tuple[str, ...], Future]" = {}
_INFLIGHT_LOCK = threading.Lock()


def install_build_gate(gate) -> None:
    """Dispatcher hook: None restores the default local gate."""
    global _GATE
    with _GATE_LOCK:
        _GATE = gate


def _gate():
    global _GATE
    with _GATE_LOCK:
        if _GATE is None:
            _GATE = LocalBuildGate()
        return _GATE


def _run_chunks(workspace: Path, chunks: "list[list[str]]",
                hint: str) -> tuple[bool, str]:
    gate = _gate()
    t0 = time.monotonic()
    try:
        lease = gate.acquire(default_build_threads(), hint)
    except BuildQueueSaturated as e:
        return False, str(e)
    queued = time.monotonic() - t0
    env = {**os.environ, "LEAN_NUM_THREADS": str(lease.threads)}
    ok_all = True
    outs: list[str] = []
    try:
        for chunk in chunks:
            try:
                r = subprocess.run(
                    ["lake", "build", *chunk],
                    cwd=str(workspace),
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    timeout=LAKE_BUILD_TIMEOUT_SEC, env=env,
                    creationflags=no_window_creationflags(),
                )
            except subprocess.TimeoutExpired:
                return False, (f"lake build {' '.join(chunk)} timed out "
                               f"({LAKE_BUILD_TIMEOUT_SEC}s) at "
                               f"{lease.threads} thread(s)"
                               + (f" after queueing {queued:.0f}s"
                                  if queued >= 1 else ""))
            out = (r.stdout + r.stderr).strip()
            if out:
                outs.append(out)
            if not (r.returncode == 0 and "error:" not in out.lower()):
                ok_all = False
    finally:
        lease.release()
    if queued >= 1:
        print(f"[lake] build {hint!r} queued {queued:.0f}s for its lease "
              f"({lease.threads} thread(s))", flush=True)
    return ok_all, "\n".join(outs)


def lake_build_modules(workspace: Path,
                       modules: list[str]) -> tuple[bool, str]:
    """Run `lake build <m1> <m2> ...` for one or many module names.

    Lake's internal scheduler resolves the dependency DAG and builds
    independent modules in parallel. Passing N modules in a single
    call is therefore much faster than N sequential single-target
    invocations whenever any of those modules can run in parallel
    (e.g. Backward writes 4 sibling sub-goal files plus 1 strategy
    file that imports them all — sub-goals build concurrently, then
    the strategy serially).

    Long module lists are split into command-line-sized chunks
    (`LAKE_CMDLINE_BUDGET`, see the WinError 206 note above); the
    result is the conjunction of the chunk results with outputs
    joined. An empty `modules` keeps the historical shape — one bare
    `lake build` (the workspace default target) — rather than a silent
    no-op; callers guard the empty case themselves.

    Gate (2026-08-30): identical module lists in flight share one
    build; every build runs under a lease (see the gate section).
    """
    key = (str(workspace),) + tuple(modules)
    with _INFLIGHT_LOCK:
        fut = _INFLIGHT.get(key)
        mine = fut is None
        if mine:
            fut = Future()
            _INFLIGHT[key] = fut
    if not mine:
        return fut.result()
    try:
        chunks = chunk_modules_for_cmdline(modules) if modules else [[]]
        hint = (f"{len(modules)} module(s): {modules[0]}"
                + (" …" if len(modules) > 1 else "")) if modules else "default target"
        result = _run_chunks(workspace, chunks, hint)
        fut.set_result(result)
        return result
    except BaseException as e:  # noqa: BLE001 — waiters must not hang
        fut.set_exception(e)
        raise
    finally:
        with _INFLIGHT_LOCK:
            _INFLIGHT.pop(key, None)


def lake_build(workspace: Path, target_lean: Path) -> tuple[bool, str]:
    """Build a single .lean file's module (resolves deps).

    Thin wrapper around `lake_build_modules` — kept for Builder /
    Verify call sites that only ever build one target at a time.
    """
    module = lean_path_to_module(workspace, target_lean)
    return lake_build_modules(workspace, [module])


def lake_build_batch(workspace: Path,
                     targets: list[Path]) -> tuple[bool, str]:
    """Build multiple .lean files in one lake invocation. Lake
    parallelizes independent targets internally."""
    modules = [lean_path_to_module(workspace, t) for t in targets]
    return lake_build_modules(workspace, modules)
