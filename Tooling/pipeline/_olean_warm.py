"""Promotion cold-build gate — the background builder behind
`verify.verify_housekeeping` (owner ruling 2026-08-30, task #231).

History. #103 put a best-effort `.olean` WARMER here: after
`verify_housekeeping` promoted a strategy (parent → `def <slug> :=
@s<N>` alias), the alias module was cold-built on this thread so the
later root integrity probe found the spine warm. Failures printed one
truncated line and changed nothing — "proved-in-DB is the source of
truth". The 2026-08-30 full cold build of union_closed then found
bricks that do not compile at all, and the warmer's own log carried 15
such failures nobody had read (seven from a single promotion whose
alias rewrite dropped the helper `def` its consumers cited).

Now the build is the GATE. Housekeeping submits `(strategy_id, modules)`
— the alias module plus every live strategy that imports the promoted
goal — and flips or rolls back only when the result comes back
(`drain_results`). Same threading contract as before: one serial daemon
worker, off the dispatcher main thread and off the LLM pool (#64/#118),
now going through the lake build lease like every other batch build.
A failure keeps its FULL output on disk and lands in the degraded
ledger; the failing module names the culprit for housekeeping.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import _lake


@dataclass
class BuildResult:
    strategy_id: int
    ok: bool
    failing_modules: list[str]
    detail: str
    delivered: bool = False
    modules: list[str] = field(default_factory=list)


LOG_DIR = Path(".asterism") / "logs" / "promotion_gate"

#: Pause before a fenced-out (`capped`) promotion build goes back on the
#: queue — the build itself already waited `_lake.ROOM_WAIT_SEC` for
#: room; this only keeps the serial worker from spinning on a machine
#: that stays full.
REQUEUE_PAUSE_SEC = 30.0


class PromotionGate:
    """Serial background cold build for promotions.

    `submit(sid, modules)` is non-blocking: one build per strategy id in
    flight (a re-submission while pending is ignored). Results wait in
    `drain_results()` for the main-thread housekeeping pass; `pending(sid)`
    is true from submit until the result is drained. Disabled instances
    are inert (`submit` records an immediate success so housekeeping
    keeps its old shape in tests that opt out).
    """

    def __init__(self, workspace: Path, *, enabled: bool = True) -> None:
        self._workspace = workspace
        self._enabled = enabled
        self._queue: "queue.Queue[tuple[int, list[str]] | None]" = queue.Queue()
        self._lock = threading.Lock()
        self._pending: set[int] = set()
        self._results: dict[int, BuildResult] = {}
        self._cv = threading.Condition(self._lock)
        self._thread: threading.Thread | None = None
        if enabled:
            self._thread = threading.Thread(
                target=self._loop, name="promotion-gate", daemon=True)
            self._thread.start()

    # ── main-thread side ──

    def submit(self, strategy_id: int, modules: list[str]) -> None:
        sid = int(strategy_id)
        with self._lock:
            if sid in self._pending or sid in self._results:
                return
            self._pending.add(sid)
        if not self._enabled:
            with self._lock:
                self._results[sid] = BuildResult(sid, True, [], "gate disabled",
                                                 modules=list(modules))
                self._pending.discard(sid)
            return
        self._queue.put((sid, list(modules)))

    def has_pending(self) -> bool:
        """Any promotion submitted and not yet drained — the dispatcher
        treats this as work in flight (no stall wake, no idle exit)."""
        with self._lock:
            return bool(self._pending) or any(
                not r.delivered for r in self._results.values())

    def pending(self, strategy_id: int) -> bool:
        with self._lock:
            sid = int(strategy_id)
            return sid in self._pending or (
                sid in self._results and not self._results[sid].delivered)

    def drain_results(self) -> list[BuildResult]:
        with self._lock:
            out = [r for r in self._results.values() if not r.delivered]
            for r in out:
                r.delivered = True
            for r in out:
                self._results.pop(r.strategy_id, None)
            return out

    def wait_result(self, strategy_id: int, timeout: float = 30.0
                    ) -> "BuildResult | None":
        """Test/CLI helper: block until the build for `strategy_id` lands."""
        deadline = time.monotonic() + timeout
        with self._cv:
            while True:
                r = self._results.get(int(strategy_id))
                if r is not None:
                    r.delivered = True
                    self._results.pop(int(strategy_id), None)
                    return r
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self._cv.wait(timeout=left)

    # ── worker side ──

    def _record_failure(self, sid: int, modules: list[str], failing: list[str],
                        detail: str) -> None:
        try:
            log_dir = self._workspace / LOG_DIR
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / f"s{sid}.txt").write_text(
                f"# promotion gate — strategy s{sid}\n# modules: "
                f"{' '.join(modules)}\n# failing: {' '.join(failing)}\n\n"
                f"{detail}", encoding="utf-8")
        except OSError:
            pass
        first = next((ln for ln in detail.splitlines()
                      if ln.startswith("error:") and ".lean" in ln), "")
        try:
            from ..core import degraded
            degraded.record(self._workspace, "promotion_build",
                            f"s{sid}: {' '.join(failing) or 'unknown module'}"
                            f" — {first[:200]}")
        except Exception:  # noqa: BLE001 — the ledger is best-effort
            pass

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                sid, modules = item
                try:
                    res = _lake.lake_build_modules(self._workspace, modules)
                    ok, detail = res
                except Exception as e:  # noqa: BLE001 — a crash is a failure
                    res, ok, detail = None, False, f"promotion gate error: {e}"
                if getattr(res, "capped", False):
                    # The OS fence stopped the build for lack of room
                    # (2026-09-02). Not a verdict on the promotion: the
                    # same job goes back on the queue, still pending to
                    # housekeeping, and runs again when there is room.
                    print(f"[promotion-gate] s{sid} capped — no room on the "
                          f"machine; requeued", flush=True)
                    time.sleep(REQUEUE_PAUSE_SEC)
                    self._queue.put((sid, list(modules)))
                    continue
                failing: list[str] = []
                if not ok:
                    from ..quality.verify import failing_modules_from_build_output
                    failing = failing_modules_from_build_output(detail or "")
                    self._record_failure(sid, modules, failing, detail or "")
                    print(f"[promotion-gate] s{sid} FAILED — "
                          f"{', '.join(failing) or 'no module named'}", flush=True)
                else:
                    print(f"[promotion-gate] s{sid} built "
                          f"{len(modules)} module(s)", flush=True)
                with self._cv:
                    self._results[sid] = BuildResult(
                        sid, bool(ok), failing, detail or "", modules=list(modules))
                    self._pending.discard(sid)
                    self._cv.notify_all()
            finally:
                self._queue.task_done()

    def shutdown(self, *, wait: bool = False, timeout: float = 5.0) -> None:
        if self._thread is None:
            return
        self._queue.put(None)
        if wait:
            self._thread.join(timeout=timeout)


# The #103 name, kept for call sites and tests that still say "warmer":
# the gate IS the warmer — the built oleans are the same side effect.
OleanWarmer = PromotionGate
