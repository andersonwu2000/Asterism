"""Background .olean warming for promoted alias spines (#103).

When `verify.verify_housekeeping` promotes a strategy it rewrites the
parent goal file into an alias (`def <slug> := @s<sid>`). At that moment
the alias module is brand-new content (no `.olean`) and the strategy
scratch's old `.olean` is stale (its imported sub-goal oleans changed
from sorry-stub to real proof). Left lazy, the later root integrity
probe (`verify.root_integrity_gate`, main thread, 900s cap) pays one
cold closure build to materialize the whole spine — the "validate
suddenly took 120s" symptom.

#64 history: 9cc7322 built that `.olean` inline in housekeeping; 4128212
moved it out because a 10-strategy cascade × 30-60s lake build blocked
the dispatcher main thread (Jordan 2026-05-25, pool 0/4). So we cannot
build on the main thread, and we should not steal an LLM worker-pool
slot either (`dispatch.pool` is 1:1 with gateway backends, #118 — that
budget is for claude sessions, and a lake build there also contends with
the gateway's own `lake serve` workers).

This warmer is the third option: a dedicated background builder, off both
the main thread and the LLM pool. A single daemon worker thread drains a
queue of just-promoted alias modules and runs a cold `lake build` on
each (lake parallelizes the module's own dependency DAG internally, so
one serial issuer is enough — and serial avoids two concurrent
`lake build`s racing on the same `.lake` build lock).

Best-effort by contract: a failed/late warm only degrades dedupe + the
integrity probe's speed; `proved`-in-DB is the source of truth (same
spirit as 9cc7322). The worker thread is `daemon=True` so it never
blocks process exit; `shutdown()` enqueues a sentinel for clean drains
(tests / in-process callers).
"""
from __future__ import annotations

import queue
import threading
from pathlib import Path

from ._lake import lake_build, lean_path_to_module


class OleanWarmer:
    """Serial background `lake build` queue for promoted alias spines.

    `submit(path)` is non-blocking (microseconds): it resolves the
    module name, deduplicates against in-flight/queued modules, and
    hands the path to the worker thread. Disabled instances are inert
    no-ops so call sites need no guards.
    """

    def __init__(self, workspace: Path, *, enabled: bool = True) -> None:
        self._workspace = workspace
        self._enabled = enabled
        self._queue: "queue.Queue[Path | None]" = queue.Queue()
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._thread: threading.Thread | None = None
        if enabled:
            self._thread = threading.Thread(
                target=self._loop, name="olean-warm", daemon=True)
            self._thread.start()

    def _module_of(self, target_lean: Path) -> str:
        try:
            return lean_path_to_module(self._workspace, target_lean)
        except Exception:
            return str(target_lean)

    def submit(self, target_lean: Path) -> None:
        """Queue a best-effort cold `lake build` of `target_lean`'s
        module. Deduplicates: a module already queued or building is not
        re-enqueued (a re-promotion of the same alias is cheap to skip)."""
        if not self._enabled:
            return
        module = self._module_of(target_lean)
        with self._lock:
            if module in self._pending:
                return
            self._pending.add(module)
        self._queue.put(target_lean)

    def _loop(self) -> None:
        while True:
            target = self._queue.get()
            try:
                if target is None:  # shutdown sentinel
                    return
                module = self._module_of(target)
                try:
                    ok, detail = lake_build(self._workspace, target)
                    if ok:
                        print(f"[olean-warm] built {module}", flush=True)
                    else:
                        print(f"[olean-warm] build failed {module}: "
                              f"{detail[:160]}", flush=True)
                except Exception as e:  # noqa: BLE001 — best-effort
                    print(f"[olean-warm] error {module}: {e}", flush=True)
                finally:
                    with self._lock:
                        self._pending.discard(module)
            finally:
                self._queue.task_done()

    def shutdown(self, *, wait: bool = False, timeout: float = 5.0) -> None:
        """Signal the worker to stop after draining the current item.
        `wait=True` joins (bounded by `timeout`). Idempotent; safe on a
        disabled warmer."""
        if self._thread is None:
            return
        self._queue.put(None)
        if wait:
            self._thread.join(timeout=timeout)
