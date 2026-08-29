"""Stdio JSON-RPC client for `lake serve` (the Lean LSP wrapper).

Used by the long-living shared gateway (`lsp_gateway.py`) to drive a
single `lake serve` instance whose worker pool is shared across all
in-flight pipelines. The class is fully self-contained — no
module-level config, no globals.

Two threads run alongside the main thread once `start()` is called:
  * reader: pulls Content-Length-framed messages off lake serve's
    stdout; routes responses to per-request queues, latches
    publishDiagnostics into `_latest_diagnostics`, and queues
    everything else for `wait_for_file_done`.
  * stderr drainer: empties stderr to avoid pipe-buffer deadlock.

Diagnostics handling: publishDiagnostics is also pushed to the
notifications queue so wait_for_file_done can reason about it.
`diagnostics_for(uri)` reads the latest stash any time.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from ..core import config as _cfg
from ..core.process_group import (assign_to_job, create_capped_job,
                                  no_window_creationflags, terminate_job)
from ..state.metaprog import blocked_detail, scan_metaprogramming


class MetaprogrammingBlocked(RuntimeError):
    """Text carrying an elaboration-time metaprogramming entry was about
    to be pushed into a Lean worker.

    Raised at the LSP boundary — the ONE place every elaboration of every
    text in this framework passes through — so a gateway path added later
    cannot elaborate un-scanned agent text by forgetting a guard. The
    agent-facing gateway entries scan first and answer with a readable
    message; reaching this exception means some other path tried.
    """


def _guard_metaprogramming(file_path: Path, content: str) -> None:
    token = scan_metaprogramming(content)
    if token is not None:
        raise MetaprogrammingBlocked(
            blocked_detail(token, where=Path(file_path).name))


class LspClient:
    # Class-level default so partially-constructed instances (tests use
    # `__new__` to unit-test shutdown paths) still read a coherent None.
    _job = None

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.proc: subprocess.Popen | None = None
        self._job = None       # memory-capped Job Object over the lake tree
        self._next_id = 1
        self._pending: dict[int, queue.Queue] = {}
        self._notifications: queue.Queue = queue.Queue()
        self._stopped = threading.Event()
        self._init_stderr_tail()
        self._latest_diagnostics: dict[str, list] = {}
        self._diag_lock = threading.Lock()
        # Per-URI fileProgress state. Reader thread updates on every
        # `$/lean/fileProgress` message; pollers in `wait_for_file_done`
        # read without consuming. This avoids the queue-drain race that
        # occurs at multi-slot warmup, where slot N's wait pulled and
        # discarded slot M's fileProgress=[] message, leaving slot M's
        # later wait blocking until timeout.
        # `_file_progress[uri]` = most recent `processing` list (None
        # if Lean has never reported on this URI).
        # `_file_progress_seen_nonempty` = URIs for which Lean emitted
        # at least one processing=[…non-empty…] event. We require this
        # before treating processing=[] as "done", because Lean briefly
        # reports processing=[] right after didOpen before elaborate
        # actually starts.
        self._file_progress: dict[str, list] = {}
        self._file_progress_seen_nonempty: set[str] = set()
        self._file_progress_lock = threading.Lock()
        # Send-side mutex. Lake serve's stdin is a single byte stream;
        # without this lock concurrent threads (the gateway dispatches
        # MCP tool calls in an executor → multiple sessions hit one
        # backend in parallel) interleave their JSON-RPC frames and
        # corrupt the stream. Lock protects: _next_id increment,
        # _pending insertion, and the actual write to stdin. Response
        # wait happens outside the lock so distinct threads can have
        # multiple in-flight requests on the wire.
        self._send_lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    # ---- lifecycle ------------------------------------------------

    def start(self) -> None:
        # `lake serve` reads lakefile.lean for toolchain + LEAN_PATH,
        # then spawns `lean --server` (which spawns child workers via
        # `lean --worker`). The watchdog locates the worker binary via
        # env `LEAN_WORKER_PATH` (falling back to its own argv[0] —
        # i.e. stock `lean.exe`). See `Lean/Server/Watchdog.lean :: findWorkerPath`.
        #
        # If our custom `lean-asterism-server` binary is built, point
        # the watchdog at it instead. Workers then load
        # `Asterism.GatewayRpc`'s `builtin_initialize` and surface the
        # custom RPCs (`$/lean/rpc/call` with method `Asterism.writeOlean`
        # / `Asterism.printAxioms`). If the binary isn't built, fall
        # back silently to stock workers — verify_unification features
        # are then unavailable but the rest of the gateway still works.
        # cwd must be the workspace root regardless.
        env = dict(os.environ)
        suffix = ".exe" if os.name == "nt" else ""
        custom = self.workspace / ".lake" / "build" / "bin" / f"lean-asterism-server{suffix}"
        if custom.exists():
            env["LEAN_WORKER_PATH"] = str(custom)
            # `Lean.determineLakePath` (used by `setupFile` to spawn
            # `lake setup-file` for module setup) falls back to
            # `IO.appDir / "lake"` if neither LAKE nor LEAN_SYSROOT is
            # set. For our custom binary, IO.appDir is `.lake/build/bin/`
            # which doesn't contain `lake` → setup fails → header
            # processing reports `result?=none`. Set LAKE explicitly to
            # the toolchain's lake binary so setup-file works.
            if "LAKE" not in env:
                lake_path = shutil.which("lake")
                if lake_path:
                    env["LAKE"] = lake_path
        # POSIX: own session/process group so `_kill_tree` can `killpg`
        # the whole `lake serve → lean --server → lean --worker` tree.
        # Windows: `taskkill /T` walks the tree by PID, no flag needed.
        popen_kwargs: dict = {}
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(
            ["lake", "serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.workspace),
            env=env,
            bufsize=0,
            creationflags=no_window_creationflags(),
            **popen_kwargs,
        )
        # Memory-capped Job Object over the whole lake tree (2026-08-08
        # post-mortem: one worker's diverging kernel reduction reached
        # 102 GB of commit and took the workstation down; taskkill /T
        # missed it once orphaned). Descendants inherit membership, so
        # the cap and the job-kill cover workers taskkill cannot see.
        # Assigned immediately after Popen — lake takes seconds to spawn
        # lean, so the pre-assignment window is not a real gap. Soft:
        # None off-Windows / on refusal, and every use checks for it.
        cap_mb = _cfg.get("gateway.lean_memory_cap_mb", default=8192,
                          env_var="ASTERISM_LEAN_MEMORY_CAP_MB", cast=int)
        if cap_mb > 0:
            self._job = create_capped_job(cap_mb)
            if self._job is not None and not assign_to_job(
                    self._job, self.proc):
                terminate_job(self._job)   # close the empty job handle
                self._job = None
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True
        )
        self._reader_thread.start()
        self._stderr_thread = threading.Thread(
            target=self._stderr_loop, daemon=True
        )
        self._stderr_thread.start()

    def _kill_tree(self) -> None:
        """Kill `lake serve` AND its descendants (`lean --server`
        watchdog + `lean --worker` children). `proc.kill()` alone reaps
        only `lake serve`, orphaning a wedged worker that keeps burning
        CPU — a runaway elaboration then survives shutdown (the
        2026-06-12 gateway-hang root cause: a non-terminating elaborate
        was never reaped, so a backend restart could not recover it).

        Job first, taskkill second: `taskkill /T` walks the CURRENT
        parent-child chain, so a worker whose parent died first is
        re-parented and invisible to it — one such orphan outlived 21
        backend restarts and reached 102 GB (2026-08-08). Job
        membership survives re-parenting, so `terminate_job` reaps it;
        taskkill stays as the fallback for the no-job path."""
        if self.proc is None:
            return
        if self._job is not None:
            terminate_job(self._job)
            self._job = None
        pid = self.proc.pid
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True,
                           creationflags=no_window_creationflags())
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    self.proc.kill()
                except Exception:
                    pass

    def shutdown(self, timeout: float = 5.0) -> None:
        if self.proc is None:
            return
        try:
            self.notify("shutdown", None)
            self.notify("exit", None)
        except Exception:
            pass
        self._stopped.set()
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._kill_tree()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass
        # Even after a clean exit of `lake serve`, a re-parented worker
        # may survive; the job sweeps it and closes the handle.
        if self._job is not None:
            terminate_job(self._job)
            self._job = None

    # ---- protocol -------------------------------------------------

    def initialize(self, timeout: float = 60.0) -> dict:
        result = self.request("initialize", {
            "processId": os.getpid(),
            "rootUri": self.workspace.as_uri(),
            "capabilities": {},
        }, timeout=timeout)
        self.notify("initialized", {})
        return result

    def request(self, method: str, params: Any,
                timeout: float = 30.0) -> Any:
        # Atomically: allocate rid, register pending queue, write the
        # request frame to stdin. Multiple threads must not interleave
        # any of these three or rid races / stdin garble.
        q: queue.Queue = queue.Queue(maxsize=1)
        with self._send_lock:
            rid = self._next_id
            self._next_id += 1
            self._pending[rid] = q
            self._send_unlocked({"jsonrpc": "2.0", "id": rid,
                                 "method": method, "params": params})
        # Block on the response outside the lock so other threads can
        # have requests in flight concurrently. The reader thread
        # routes responses to per-rid queues.
        try:
            msg = q.get(timeout=timeout)
        except queue.Empty:
            self._pending.pop(rid, None)
            raise TimeoutError(f"LSP request {method!r} timed out")
        if "error" in msg:
            raise RuntimeError(f"LSP error for {method}: {msg['error']}")
        return msg.get("result")

    def notify(self, method: str, params: Any) -> None:
        with self._send_lock:
            self._send_unlocked({"jsonrpc": "2.0",
                                 "method": method, "params": params})

    def _send_unlocked(self, msg: dict) -> None:
        """Caller must hold `self._send_lock`. Writes one JSON-RPC
        frame (Content-Length header + body) to lake serve's stdin."""
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("LSP not started")
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self.proc.stdin.write(header + body)
        self.proc.stdin.flush()

    # ---- reader thread --------------------------------------------

    def _read_loop(self) -> None:
        try:
            while not self._stopped.is_set():
                msg = self._read_message()
                if msg is None:
                    break
                mid = msg.get("id")
                if mid is not None and ("result" in msg or "error" in msg):
                    q = self._pending.pop(mid, None)
                    if q is not None:
                        q.put(msg)
                else:
                    method = msg.get("method", "")
                    if method == "textDocument/publishDiagnostics":
                        params = msg.get("params") or {}
                        uri = params.get("uri", "")
                        if uri:
                            with self._diag_lock:
                                self._latest_diagnostics[uri] = (
                                    params.get("diagnostics", []) or []
                                )
                    elif method == "$/lean/fileProgress":
                        params = msg.get("params") or {}
                        doc = params.get("textDocument", {}) or {}
                        uri = doc.get("uri", "")
                        processing = params.get("processing", []) or []
                        if uri:
                            with self._file_progress_lock:
                                self._file_progress[uri] = processing
                                if processing:
                                    self._file_progress_seen_nonempty.add(uri)
                    self._notifications.put(msg)
        except Exception:
            pass  # reader exits on shutdown / pipe close

    def _read_message(self) -> dict | None:
        if self.proc is None or self.proc.stdout is None:
            return None
        # Read Content-Length: <N>\r\n\r\n header.
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            ch = self.proc.stdout.read(1)
            if not ch:
                return None
            header += ch
        # Parse Content-Length.
        length = None
        for line in header.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":", 1)[1].strip())
                break
        if length is None:
            return None
        body = b""
        while len(body) < length:
            chunk = self.proc.stdout.read(length - len(body))
            if not chunk:
                return None
            body += chunk
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _init_stderr_tail(self) -> None:
        """A bounded ring of the server's stderr chunks — a worker crash
        ("Server process … crashed") is otherwise a message with no
        cause attached (2026-08-30)."""
        import collections
        self._stderr_buf: "collections.deque[bytes]" = collections.deque(maxlen=256)

    def stderr_tail(self, limit: int = 4000) -> str:
        """The last `limit` characters the Lean server wrote to stderr."""
        raw = b"".join(self._stderr_buf)
        return raw.decode("utf-8", "replace")[-limit:]

    def _stderr_loop(self) -> None:
        # Just drain stderr to avoid pipe-buffer deadlock.
        if self.proc is None or self.proc.stderr is None:
            return
        try:
            while not self._stopped.is_set():
                chunk = self.proc.stderr.read(4096)
                if not chunk:
                    break
                self._stderr_buf.append(chunk)
        except Exception:
            pass

    # ---- custom RPC (Asterism builtin procedures) -----------------

    def rpc_call(self, slot_uri: str, method: str, params: dict,
                 timeout: float = 30.0) -> dict:
        """Invoke a custom Lean RPC method registered via
        `registerBuiltinRpcProcedure` in our `lean-asterism-server`
        binary. Two-step: connect to get a session id, then call.

        `slot_uri` must be a URI of an open document — the RPC
        handler runs in that document's worker context, with access
        to its elaborated `Environment`. Caller must have called
        `did_open` (and ideally waited for elaborate to finish) on
        `slot_uri` before this.

        Per-call connect is intentional: RPC sessions expire after
        30s (`RpcSession.keepAliveTimeMs`), and our usage (~one call
        per slot per verify) doesn't justify cache machinery.
        """
        connect = self.request("$/lean/rpc/connect",
                               {"uri": slot_uri}, timeout=timeout)
        session_id = connect.get("sessionId")
        if session_id is None:
            raise RuntimeError(f"$/lean/rpc/connect returned no sessionId: "
                               f"{connect}")
        return self.request("$/lean/rpc/call", {
            "sessionId": session_id,
            "method": method,
            "textDocument": {"uri": slot_uri},
            "position": {"line": 0, "character": 0},
            "params": params,
        }, timeout=timeout)

    # ---- file ops -------------------------------------------------

    def did_open(self, file_path: Path, content: str,
                 language_id: str = "lean") -> None:
        _guard_metaprogramming(file_path, content)
        self.notify("textDocument/didOpen", {
            "textDocument": {
                "uri": Path(file_path).resolve().as_uri(),
                "languageId": language_id,
                "version": 1,
                "text": content,
            }
        })

    def did_close(self, file_path: Path) -> None:
        """Close a document — which ENDS ITS WORKER PROCESS.

        Lean runs one `lean-asterism-server --worker <uri>` per open
        document, so this is the only handle the framework has on a
        single worker's lifetime. `did_change_full` swaps the content
        but keeps the same process and therefore the same heap: it
        cannot recycle memory, which is why slot recycling needs this
        verb rather than a content swap (measured 2026-08-14).

        No reply to wait for — the worker's death is asynchronous, and
        the caller re-opens and waits on `wait_for_file_done`.
        """
        self.notify("textDocument/didClose", {
            "textDocument": {"uri": Path(file_path).resolve().as_uri()},
        })

    def did_change_full(self, file_path: Path, full_text: str,
                        version: int) -> None:
        _guard_metaprogramming(file_path, full_text)
        self.notify("textDocument/didChange", {
            "textDocument": {
                "uri": Path(file_path).resolve().as_uri(),
                "version": version,
            },
            "contentChanges": [{"text": full_text}],
        })

    def plain_goal(self, file_path: Path, line: int, character: int,
                   timeout: float = 30.0) -> Any:
        return self.request("$/lean/plainGoal", {
            "textDocument": {"uri": Path(file_path).resolve().as_uri()},
            "position": {"line": line, "character": character},
        }, timeout=timeout)

    # ---- diagnostics ---------------------------------------------

    def diagnostics_for(self, uri: str) -> list:
        with self._diag_lock:
            return list(self._latest_diagnostics.get(uri, []))

    def clear_diagnostics(self, uri: str) -> None:
        with self._diag_lock:
            self._latest_diagnostics.pop(uri, None)

    def busy_uris(self) -> set[str]:
        """URIs whose Lean elaboration is currently in-flight (fileProgress
        reported non-empty). The gateway wedge-watchdog uses this to spot a
        worker stuck on a non-terminating elaborate — its 120s/300s wait
        already returned, but the runaway keeps burning the slot."""
        with self._file_progress_lock:
            return {u for u, v in self._file_progress.items() if v}

    def clear_file_progress(self, uri: str) -> None:
        """Reset per-URI fileProgress state so a subsequent
        `wait_for_file_done` only matches a NEW elaborate cycle.
        Call before `did_change_full` if the caller intends to wait
        for the new cycle to finish (otherwise stale "done" state
        from the previous elaborate would short-circuit the wait)."""
        with self._file_progress_lock:
            self._file_progress.pop(uri, None)
            self._file_progress_seen_nonempty.discard(uri)

    def wait_for_diagnostics(self, file_uri: str, version: int,
                              timeout: float = 180.0) -> None:
        """Block until Lean has finished elaborating `file_uri` at the
        given version AND has flushed all `publishDiagnostics`
        notifications for that version.

        Uses Lean's built-in `textDocument/waitForDiagnostics` request
        (see `Lean/Server/FileWorker/RequestHandling.lean` line 466
        and `ProtocolOverview.lean` line 407 — "Emitted in interactive
        tests to wait for all diagnostics up to a given point.").

        Server-side returns after:
          1. `doc.meta.version >= version` — our didChange is applied
          2. reporter task done — every publishDiagnostics for this
             version has been emitted
          3. `cmdSnaps.waitAll` — every command's elaborate finished

        This is the canonical "all done" signal. Replaces the older
        `wait_for_file_done` + `wait_for_diagnostics_settled` pair —
        no polling, no arbitrary settle window. After this returns,
        `diagnostics_for(uri)` reflects the full final set."""
        self.request("textDocument/waitForDiagnostics", {
            "uri": file_uri,
            "version": version,
        }, timeout=timeout)

    def wait_for_file_done(self, file_uri: str,
                           timeout: float = 180.0,
                           poll_interval: float = 0.05) -> str:
        """Block until $/lean/fileProgress reports `processing=[]` for
        `file_uri`. NOT a sufficient signal for "elaborate done" by
        itself — see wait_for_diagnostics_settled.

        Polls reader-thread-maintained per-URI state instead of draining
        `_notifications` queue. This is essential when multiple URIs are
        elaborating in parallel (e.g. gateway warmup of W slots): a
        queue-draining wait would consume sibling URIs' messages and
        leave their later waits blocking forever."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._file_progress_lock:
                seen = file_uri in self._file_progress_seen_nonempty
                cur = self._file_progress.get(file_uri)
            if seen and cur is not None and not cur:
                return "file_progress_empty"
            # Fast-fail if a publishDiagnostics with content already
            # arrived — Lean sometimes signals diagnostics before
            # fileProgress=[] (originally observed for tactic-level
            # errors that shortcut the elaborator).
            if self.diagnostics_for(file_uri):
                return "diagnostics_with_content"
            time.sleep(poll_interval)
        raise TimeoutError(f"file done signal not received within {timeout}s")

    def wait_for_diagnostics_settled(self, uri: str,
                                     stable_for: float = 3.0,
                                     max_wait: float = 90.0,
                                     poll_interval: float = 0.5) -> list:
        """Block until publishDiagnostics for `uri` is stable for
        `stable_for` consecutive seconds, or `max_wait` elapses.

        Why this exists: `$/lean/fileProgress processing=[]` does NOT
        mean elaborate is done — Lean emits publishDiagnostics in
        several waves (per-declaration, per-phase). Reading
        diagnostics right after the empty signal gets stale (often
        empty) results. For 100+ LOC proofs, full diagnostics take
        25-30s after didChange to fully arrive. This poller watches
        the diagnostics list and only returns once it stops changing,
        which is a reliable empirical signal of "Lean has finished
        and won't update further on its own."

        `stable_for=3.0` empirically chosen — 1s is too tight (Lean
        phase-to-phase gaps can exceed it), 5s wastes time on trivial
        files."""
        deadline = time.monotonic() + max_wait
        last_signature: tuple | None = None
        last_change_time = time.monotonic()
        while time.monotonic() < deadline:
            diags = self.diagnostics_for(uri)
            sig = (
                len(diags),
                tuple(sorted((d.get("message", "") or "")[:40]
                             for d in diags)),
            )
            if sig != last_signature:
                last_signature = sig
                last_change_time = time.monotonic()
            elif time.monotonic() - last_change_time >= stable_for:
                return diags
            time.sleep(poll_interval)
        return self.diagnostics_for(uri)
