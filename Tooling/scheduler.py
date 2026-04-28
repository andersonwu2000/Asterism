"""Reactor (P2 daemon): event_bus block + 30s tick structural refill.

P1 single-task exit preserved via run() / _run_loop() for backward compat.
P2 adds:
  - run_daemon(): daemon loop blocking on _event_queue (threading.Queue)
  - Atomic pool: ThreadPoolExecutor(pool_size=P=4)
  - 4-event kind dispatch:
      pipeline_finished → 6-step cycle (steps 2/3/4/6 in P2)
      control_signal    → pause / resume / shutdown
      fatal             → halt (P1 mechanism)
      task_checkpoint   → P5; P2 silently discards
  - Structural refill BFS: open goals → Backward; all-subgoal-proved → Builder
  - N_block_after_failures=5 stop-gap (in-memory; P3 持久化接手)
  - Cascade step 3 (Builder): strategy succeeded + goal proved + trust set + accept rule
  - Cascade step 3 (Strategy dead): goal shelved if all strategies dead
  - Cancellation: mark same-goal running pipelines for natural exit
  - Hook stubs: _run_step1_stale_filter (P3), _run_step5_strategist_trigger (P7)
"""
from __future__ import annotations

import json
import os
import queue
import signal
import socket
import sqlite3
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Tooling.commit import CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.meta import MetaError, parse_meta
from Tooling.pipelines.backward import Backward, BackwardConfig, BackwardResult
from Tooling.pipelines.builder import Builder, BuilderConfig, BuilderResult
from Tooling.subsystems.cache import invalidate_for_goals_write
from Tooling.trust import build_trust_set, check_accept_rule, print_axioms


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FatalError(Exception):
    """Unrecoverable cascade SQL failure. Causes reactor to exit(1)."""


@dataclass
class ReactorConfig:
    t_wall: float = 30 * 60.0
    lake_timeout: float = 600.0
    base_dir: str = "."
    pool_size: int = 4                # P: atomic pool cap
    tick_interval: float = 30.0      # seconds between structural refill ticks
    d_max: int = 12                   # D_max depth limit (shelve if depth >= d_max)
    n_block_after_failures: int = 5  # stop-gap retry cap (in-memory)


class Reactor:
    def __init__(self, db_path: str | Path, config: ReactorConfig | None = None) -> None:
        self.db_path = Path(db_path)
        self.config = config or ReactorConfig()
        self.conn: Any = None
        # P2 daemon state
        self._event_queue: queue.Queue = queue.Queue()
        self._pool: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        # pipeline_id → (target_id, kind); target_id as string
        self._running: dict[str, tuple[str, str]] = {}
        # (goal_or_strategy_id_str, pipeline_kind) → failure_count; in-memory stop-gap
        self._failure_count: dict[tuple[str, str], int] = {}
        self._paused: bool = False
        self._shutdown_flag: bool = False
        self._scheduler_id: int | None = None
        self._last_seen_ctrl_id: int = 0

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def startup(self) -> None:
        """Connect DB, apply schema (idempotent), run recover_scan."""
        self.conn = connect(self.db_path)
        init_schema(self.conn)
        CommitWriter(self.conn).recover_scan()

    # ------------------------------------------------------------------
    # P1 entry point (backward compat)
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Entry point: startup then drain queue (P1 compat)."""
        self.startup()
        self._run_loop()

    def _run_loop(self) -> None:
        """Pop → dispatch loop. Exits 0 on empty queue, 1 on fatal.

        Cascade routing handles Backward.success → Builder enqueue inline
        (see _cascade_backward); sync mode does NOT call _run_structural_refill
        because BFS would re-enqueue Backward for any open goal whose Builder
        already exhausted in the same run, causing an unintended retry loop
        in P1-style single-shot scenarios.
        """
        try:
            while True:
                task = self._pop_queue()
                if task is None:
                    sys.exit(0)
                self._dispatch(task)
        except FatalError:
            sys.exit(1)

    # ------------------------------------------------------------------
    # P2 daemon entry point
    # ------------------------------------------------------------------

    def run_daemon(self) -> None:
        """Daemon loop: block on _event_queue; 30s tick → structural refill.

        Control signal IPC: asterism stop inserts a control_signal event with
        source='cli' into the DB. _poll_db_control_signals() reads it every
        ~2s and enqueues to _event_queue so _handle_control_signal responds
        within the 5s shutdown window (impl §6.5).
        """
        self.startup()
        self._register_scheduler()
        # Snapshot current max control_signal id so we ignore pre-existing rows.
        row = self.conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM events WHERE kind = 'control_signal'"
        ).fetchone()
        self._last_seen_ctrl_id = row[0]
        self._pool = ThreadPoolExecutor(max_workers=self.config.pool_size)
        self._run_structural_refill()
        self._try_spawn_from_queue()
        last_tick = time.monotonic()
        try:
            while not self._shutdown_flag:
                elapsed = time.monotonic() - last_tick
                # Cap wait at 2s so DB control_signal polling is timely (≤5s response).
                wait = max(0.1, min(self.config.tick_interval - elapsed, 2.0))
                try:
                    event = self._event_queue.get(timeout=wait)
                except queue.Empty:
                    self._poll_db_control_signals()
                    now = time.monotonic()
                    if now - last_tick >= self.config.tick_interval:
                        last_tick = now
                        self._run_structural_refill()
                        self._try_spawn_from_queue()
                    continue
                self._dispatch_event(event)
                if not self._shutdown_flag:
                    self._try_spawn_from_queue()
        finally:
            self._unregister_scheduler()
            if self._pool is not None:
                self._pool.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Event dispatch (P2)
    # ------------------------------------------------------------------

    def _dispatch_event(self, event: tuple) -> None:
        """Route in-process event tuple to the correct handler.

        R3 fix LOW-2: unknown kinds (other than spec'd task_checkpoint) emit
        a diagnostic 'control_signal' event so silent drops are visible.
        """
        kind = event[0]
        if kind == "pipeline_finished":
            _, task, result = event
            self._handle_pipeline_finished(task, result)
        elif kind == "control_signal":
            _, action = event
            self._handle_control_signal(action)
        elif kind == "fatal":
            _, error = event
            self._handle_fatal_event(error)
        elif kind == "task_checkpoint":
            return  # P5 handler; P2 silently discards per spec
        else:
            # Unknown event kind: emit diagnostic instead of silent drop
            self._emit_event(
                "control_signal",
                {"action": "unknown_event_kind", "kind": str(kind)},
            )

    def _handle_pipeline_finished(self, task: dict, result: Any) -> None:
        """6-step cycle on pipeline_finished: P2 runs steps 2/3/4/6.

        NOTE (R2 finding F + R3 MED-3): step1 stale_filter is a P3 hook (no-op)
        and _cancel_running_for_goal is also a no-op for thread runtime. P2
        therefore accepts that a Backward/Builder running against an
        already-proved Goal will complete and may commit orphan rows; this is
        a documented spec compromise — see _cancel_running_for_goal docstring.
        """
        self._run_step1_stale_filter(task, result)        # P3 hook — empty
        self._run_step2_cancellation(task, result)
        self._run_step3_cascade(task, result)
        self._run_step4_trust_set(task, result)           # integrated into step 3
        self._run_step5_strategist_trigger(task, result)  # P7 hook — empty
        self._run_step6_spawn()

    def _handle_control_signal(self, action: str) -> None:
        """control_signal handler: pause / resume / shutdown. set_budget留P7.

        R3 fix LOW-1: unknown actions emit a diagnostic event so P7 set_budget
        or any future action that misses the dispatch table is observable.
        """
        if action == "pause":
            with self._lock:
                self._paused = True
            self._emit_event("control_signal", {"action": "pause", "status": "applied"})
        elif action == "resume":
            with self._lock:
                self._paused = False
            self._emit_event("control_signal", {"action": "resume", "status": "applied"})
        elif action == "shutdown":
            self._emit_event("control_signal", {"action": "shutdown", "status": "applying"})
            self._do_shutdown()
        else:
            self._emit_event(
                "control_signal",
                {"action": "unknown_action", "received": str(action)},
            )

    def _do_shutdown(self) -> None:
        """Shutdown: stop spawning, wait up to 5s for in-flight pipelines, then exit."""
        with self._lock:
            self._paused = True  # stop spawning immediately
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with self._lock:
                if not self._running:
                    break
            time.sleep(0.2)
        self._shutdown_flag = True  # signal daemon loop to exit

    def _handle_fatal_event(self, error: str) -> None:
        """Fatal event: emit to DB and halt reactor."""
        self._emit_fatal(error)
        self._shutdown_flag = True

    # ------------------------------------------------------------------
    # Scheduler liveness (minimal: register/unregister on daemon start/stop)
    # ------------------------------------------------------------------

    def _register_scheduler(self) -> None:
        """Insert a row into schedulers table; track id for cleanup."""
        now = _now()
        try:
            with self.conn:
                cursor = self.conn.execute(
                    "INSERT INTO schedulers (host, pid, started_at, last_heartbeat) "
                    "VALUES (?, ?, ?, ?)",
                    (socket.gethostname(), os.getpid(), now, now),
                )
                self._scheduler_id = cursor.lastrowid
        except sqlite3.Error as exc:
            self._event_queue.put(
                ("fatal", f"_register_scheduler INSERT fail: {exc}")
            )
            raise FatalError(f"_register_scheduler fail: {exc}") from exc

    def _unregister_scheduler(self) -> None:
        """Remove scheduler row on clean daemon exit."""
        if self._scheduler_id is None:
            return
        try:
            with self.conn:
                self.conn.execute(
                    "DELETE FROM schedulers WHERE id = ?", (self._scheduler_id,)
                )
        except sqlite3.Error as exc:
            self._event_queue.put(
                ("fatal", f"_unregister_scheduler DELETE fail: {exc}")
            )

    # ------------------------------------------------------------------
    # DB control signal poll (IPC: asterism stop → daemon)
    # ------------------------------------------------------------------

    def _poll_db_control_signals(self) -> None:
        """Read control_signal events inserted by CLI (source='cli') since last poll.

        Filters on source='cli' to skip internal diagnostic events emitted by
        _handle_control_signal, which would otherwise create a feedback loop.
        Only actions in (pause, resume, shutdown) are forwarded to _event_queue.
        """
        try:
            rows = self.conn.execute(
                "SELECT id, payload FROM events "
                "WHERE kind = 'control_signal' AND id > ? ORDER BY id ASC",
                (self._last_seen_ctrl_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            self._event_queue.put(
                ("fatal", f"control_signal poll SQL fail: {exc}")
            )
            return
        for row_id, payload_json in rows:
            self._last_seen_ctrl_id = row_id
            try:
                payload = json.loads(payload_json) if payload_json else {}
            except json.JSONDecodeError:
                continue
            if payload.get("source") != "cli":
                continue
            action = payload.get("action", "")
            if action in ("pause", "resume", "shutdown"):
                self._event_queue.put(("control_signal", action))

    # ------------------------------------------------------------------
    # 6-step cycle steps (P2)
    # ------------------------------------------------------------------

    def _run_step1_stale_filter(self, task: dict, result: Any) -> None:
        """P3: filter stale pipeline results before cascade. P2 no-op."""
        pass  # P3 接手

    def _run_step2_cancellation(self, task: dict, result: Any) -> None:
        """Cancel same-Goal running pipelines when Builder proves the goal."""
        if not (hasattr(result, "outcome") and result.outcome == "proved"):
            return
        if task.get("kind") != "Builder":
            return
        strategy_id = int(task["target_id"])
        row = self.conn.execute(
            "SELECT goal_id FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()
        if row is None:
            return
        self._cancel_running_for_goal(str(row[0]))

    def _run_step3_cascade(self, task: dict, result: Any) -> None:
        """Cascade rules: Builder proved / dead; Backward success / exhausted."""
        kind = task.get("kind")
        if kind == "Builder":
            self._cascade_builder(int(task["target_id"]), result)
        elif kind == "Backward":
            self._cascade_backward(int(task["target_id"]), result)

    def _run_step4_trust_set(self, task: dict, result: Any) -> None:
        """Trust set construction is integrated into _cascade_builder. P2 no-op."""
        pass

    def _run_step5_strategist_trigger(self, task: dict, result: Any) -> None:
        """P7: Strategist trigger. P2 no-op."""
        pass  # P7 接手

    def _run_step6_spawn(self) -> None:
        """Structural refill + spawn from queue."""
        self._run_structural_refill()
        self._try_spawn_from_queue()

    # ------------------------------------------------------------------
    # Cascade implementations (step 3)
    # ------------------------------------------------------------------

    def _cascade_builder(self, strategy_id: int, result: BuilderResult) -> None:
        """Cascade for Builder pipeline outcome (P2 daemon path).

        strict_trust_set=True so print_axioms failure → fail-shut. P1 sync
        `_dispatch` calls _cascade(...) directly (strict=False) to preserve
        Phase 1 acceptance compat where lake may misconfigure but goals still
        prove (P1 had no accept-rule contract).
        """
        if result.outcome == "proved":
            self._cascade(strategy_id, result, strict_trust_set=True)
        else:
            # non-proved: mark strategy dead, maybe shelve goal
            self._mark_strategy_dead(strategy_id)
            row = self.conn.execute(
                "SELECT goal_id FROM strategies WHERE id = ?", (strategy_id,)
            ).fetchone()
            if row:
                self._inc_failure_count(str(row[0]), "Builder")
                # P3 C24 R3 MED-1: phase3 §In line 37 字面「Backward / Builder
                # 都會觸發 blocked_pipelines」. Builder dead_attempts already
                # written by Builder._record_dead_attempts; just check threshold.
                from Tooling.stages.failure_archive import archive_check
                archive_check(self.conn, int(row[0]), "Builder")

    def _mark_strategy_dead(self, strategy_id: int) -> None:
        """Mark strategy dead; shelve parent goal if all strategies are dead."""
        row = self.conn.execute(
            "SELECT goal_id FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()
        if row is None:
            return
        goal_id = row[0]
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE strategies SET status = 'dead' WHERE id = ?",
                    (strategy_id,),
                )
            non_dead = self.conn.execute(
                "SELECT count(*) FROM strategies "
                "WHERE goal_id = ? AND status != 'dead'",
                (goal_id,),
            ).fetchone()[0]
            if non_dead == 0:
                with self.conn:
                    self.conn.execute(
                        "UPDATE goals SET status = 'shelved', "
                        "status_changed_at = ? WHERE id = ?",
                        (_now(), goal_id),
                    )
                # P3 C21 cache invalidation hook (impl §2.3): goals UPDATE
                # → kill local_goals + dedupe cache rows. Re-raise on SQL
                # error per silent-failure red line — this UPDATE block
                # already raises sqlite3.Error to outer handler.
                invalidate_for_goals_write(self.conn)
                self._emit_event(
                    "cascade",
                    {"goal_id": goal_id, "rule": "all_strategies_dead→shelved"},
                )
        except sqlite3.Error as exc:
            self._emit_fatal(str(exc))
            raise FatalError(str(exc)) from exc

    def _cascade_backward(self, goal_id: int, result: BackwardResult) -> None:
        """Cascade for Backward pipeline outcome.

        'success': sub-goals + strategy already committed by Backward.run().
                   Daemon mode picks up via _run_structural_refill (30s tick
                   or step 6 of pipeline_finished cycle). Sync mode (--once)
                   needs an inline enqueue of Builder for the new strategy
                   when there are no sub-goals to wait on (leaf strategy);
                   when sub-goals exist, BFS in daemon mode handles cascade
                   upward after they are proved.
        'exhausted' / 'unproductive': increment stop-gap failure count +
                                       INSERT dead_attempts row + run
                                       failure_archive checks (N=5 generic
                                       and IH-trap special-case).
        """
        if result.outcome != "success":
            self._inc_failure_count(str(goal_id), "Backward")
            self._record_backward_failure(goal_id, result.outcome)
            # P3 C24: persistent blocked_pipelines via failure_archive.
            from Tooling.stages.failure_archive import (
                archive_check,
                archive_ih_trap,
            )
            archive_check(self.conn, goal_id, "Backward")
            archive_ih_trap(self.conn, goal_id, "Backward")
            return
        # Inline Builder enqueue for leaf-strategy success (no sub-goals).
        # Without this, sync mode never builds the new strategy.
        if result.strategy_id is not None and not result.subgoal_ids:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO queue (kind, target_id, priority, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    ("Builder", str(result.strategy_id), 0, _now()),
                )

    def _record_backward_failure(self, goal_id: int, outcome: str) -> None:
        """INSERT dead_attempts row for Backward exhausted/unproductive outcome.

        Looks up the most recent Backward pipeline for this goal to satisfy
        the dead_attempts.pipeline_id FK. R3 fix MED-3: Backward.run is the
        only producer of Backward pipeline rows; finding none here means an
        invariant has been violated (orphan cascade or stale ordering).
        Emit fatal + raise FatalError per scheduler-wide silent-failure
        discipline (mirrors _mark_strategy_dead pattern, not the lenient
        cascade-warning pattern of _record_accept_reject_dead_attempt).
        """
        pipeline_row = self.conn.execute(
            "SELECT id FROM pipelines WHERE target_id = ? AND kind = 'Backward' "
            "ORDER BY started_at DESC LIMIT 1",
            (str(goal_id),),
        ).fetchone()
        if pipeline_row is None:
            msg = (
                f"backward_failure_no_pipeline_id goal_id={goal_id} "
                f"outcome={outcome}"
            )
            self._emit_fatal(msg)
            raise FatalError(msg)
        with self.conn:
            self.conn.execute(
                "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
                "pipeline_kind, outcome, reason_summary, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(goal_id),
                    "Goal",
                    pipeline_row[0],
                    "Backward",
                    outcome,
                    f"Backward outcome={outcome}",
                    _now(),
                ),
            )

    # ------------------------------------------------------------------
    # Atomic pool: spawn from queue
    # ------------------------------------------------------------------

    def _try_spawn_from_queue(self) -> None:
        """Pop queue items and submit to thread pool while below pool cap."""
        if self._pool is None:
            return
        while True:
            with self._lock:
                if self._paused or len(self._running) >= self.config.pool_size:
                    return
            task = self._pop_queue()
            if task is None:
                return
            self._submit_task(task)

    def _submit_task(self, task: dict) -> None:
        """Register task in _running and submit to thread pool."""
        pipeline_id = str(uuid.uuid4())
        with self._lock:
            self._running[pipeline_id] = (task["target_id"], task["kind"])
        self._pool.submit(self._run_pipeline_thread, pipeline_id, task)

    def _run_pipeline_thread(self, pipeline_id: str, task: dict) -> None:
        """Thread body: own DB connection, run pipeline, emit pipeline_finished.

        Exception routing (R3 fix HIGH-1):
          - FatalError       → emit ("fatal", error) to in-memory _event_queue,
                               do NOT emit pipeline_finished, return early.
                               daemon's _handle_fatal_event halts the loop.
          - other Exception  → emit ("fatal", ...) AND a correctly-typed default
                               result (BuilderResult / BackwardResult) so cascade
                               step3 still records the failure.
          - inner DB write failure surfaces as best-effort write to in-memory
                               event queue; we never silently swallow.
        """
        conn = connect(self.db_path)
        result: Any = None
        try:
            try:
                result = self._execute_task_with_conn(task, conn)
            except FatalError as exc:
                self._event_queue.put((
                    "fatal",
                    f"thread FatalError in {task.get('kind')!r}: {exc}",
                ))
                return  # do NOT emit pipeline_finished
            except Exception as exc:
                # Pipeline-internal failure: still emit fatal so daemon halts,
                # but return a typed result so step3 cascade records it.
                self._event_queue.put((
                    "fatal",
                    f"thread exc in {task.get('kind')!r}: {exc}",
                ))
                if task.get("kind") == "Backward":
                    result = BackwardResult(outcome="exhausted")
                else:
                    result = BuilderResult(outcome="exhausted")
        finally:
            try:
                conn.close()
            except Exception:
                pass
            with self._lock:
                self._running.pop(pipeline_id, None)
            if result is not None:
                self._event_queue.put(("pipeline_finished", task, result))

    def _execute_task_with_conn(self, task: dict, conn: Any) -> Any:
        """Run Builder or Backward pipeline with provided connection."""
        kind = task["kind"]
        if kind == "Builder":
            strategy_id = int(task["target_id"])
            cfg = BuilderConfig(
                t_wall=self.config.t_wall,
                lake_timeout=self.config.lake_timeout,
                base_dir=self.config.base_dir,
            )
            return Builder(strategy_id, conn, cfg).run()
        elif kind == "Backward":
            goal_id = int(task["target_id"])
            cfg = BackwardConfig(
                base_dir=self.config.base_dir,
                lake_cwd=self.config.base_dir,
                lean_timeout=self.config.lake_timeout,
            )
            chain = self._make_fallback_chain()
            return Backward(conn, chain, cfg).run(goal_id)
        else:
            raise FatalError(f"Unsupported task kind in thread: {kind!r}")

    def _make_fallback_chain(self) -> Any:
        """Create a claude FallbackChain. Tests mock Builder/Backward directly."""
        from Tooling.agent.provider import FallbackChain
        from Tooling.agent.providers.claude import ClaudeProvider
        return FallbackChain(providers=[ClaudeProvider()])

    # ------------------------------------------------------------------
    # Structural refill BFS
    # ------------------------------------------------------------------

    def _run_structural_refill(self) -> None:
        """BFS goals: enqueue Backward for open goals; Builder for all-proved strategies."""
        self._bfs_enqueue_backward()
        self._bfs_enqueue_builder()

    def _bfs_enqueue_backward(self) -> None:
        """Enqueue Backward for open theorem Goals, respecting D_max + stop-gap.

        R3 fix MED-2: filter commit_state='live' so mid-commit pending rows
        (impl §1.3 commit protocol) are not picked up before stage_file completes.
        """
        rows = self.conn.execute(
            "SELECT id, depth FROM goals "
            "WHERE status = 'open' AND kind = 'theorem' "
            "AND commit_state = 'live'"
        ).fetchall()
        for goal_id, depth in rows:
            goal_id_s = str(goal_id)
            # D_max: shelve deep goals instead of decomposing further
            if depth is not None and depth >= self.config.d_max:
                # Separate the UPDATE from the cache invalidation: the UPDATE
                # is best-effort here (we may race with another scheduler tick
                # that already shelved the goal), but the cache invalidation
                # MUST surface its failures (silent-failure red line —
                # cache.py docstring: "callers must observe the failure").
                update_ok = False
                try:
                    with self.conn:
                        self.conn.execute(
                            "UPDATE goals SET status = 'shelved', "
                            "status_changed_at = ? WHERE id = ?",
                            (_now(), goal_id),
                        )
                    update_ok = True
                except sqlite3.Error:
                    pass
                if update_ok:
                    invalidate_for_goals_write(self.conn)
                continue
            # Stop-gap: skip if Backward has failed n_block_after_failures times
            # (in-memory; P3 C25 will remove this in favor of persistent
            # goals.blocked_pipelines).
            if (
                self._get_failure_count(goal_id_s, "Backward")
                >= self.config.n_block_after_failures
            ):
                continue
            # P3 C24: persistent blocked_pipelines filter (impl §6.X /
            # phase3_cache.md §In). Survives scheduler restart unlike
            # in-memory _failure_count.
            from Tooling.subsystems.blocked_pipelines import is_blocked
            if is_blocked(self.conn, int(goal_id), "Backward"):
                continue
            # Avoid duplicate dispatch
            if self._is_already_dispatched(goal_id_s, "Backward"):
                continue
            self._enqueue_task("Backward", goal_id_s, priority=0)

    def _bfs_enqueue_builder(self) -> None:
        """Enqueue Builder for proposed strategies whose sub-goals are all proved.

        R3 fix MED-2: filter commit_state='live' so mid-commit strategies are
        not picked up before stage_file completes.
        """
        rows = self.conn.execute(
            "SELECT s.id, s.goal_id FROM strategies s "
            "WHERE s.status = 'proposed' AND s.commit_state = 'live'"
        ).fetchall()
        for strategy_id, goal_id in rows:
            strategy_id_s = str(strategy_id)
            # Stop-gap keyed on goal_id (per spec: dict[(goal_id, pipeline_kind)])
            if (
                self._get_failure_count(str(goal_id), "Builder")
                >= self.config.n_block_after_failures
            ):
                continue
            # P3 C24: persistent blocked_pipelines filter for Builder too.
            from Tooling.subsystems.blocked_pipelines import is_blocked
            if is_blocked(self.conn, int(goal_id), "Builder"):
                continue
            if self._is_already_dispatched(strategy_id_s, "Builder"):
                continue
            # Check sub-goal status
            subgoal_rows = self.conn.execute(
                "SELECT g.status FROM strategy_subgoals ss "
                "JOIN goals g ON g.id = ss.subgoal_id "
                "WHERE ss.strategy_id = ?",
                (strategy_id,),
            ).fetchall()
            if not subgoal_rows:
                # Leaf strategy (no sub-goals) — enqueue Builder
                self._enqueue_task("Builder", strategy_id_s, priority=5)
            elif all(row[0] == "proved" for row in subgoal_rows):
                # Cascade upward: all sub-goals proved — enqueue Builder
                self._enqueue_task("Builder", strategy_id_s, priority=10)

    def _is_already_dispatched(self, target_id: str, kind: str) -> bool:
        """True if a pipeline for this (target_id, kind) is running or queued."""
        with self._lock:
            for tid, k in self._running.values():
                if tid == target_id and k == kind:
                    return True
        row = self.conn.execute(
            "SELECT id FROM queue WHERE target_id = ? AND kind = ?",
            (target_id, kind),
        ).fetchone()
        return row is not None

    def _enqueue_task(self, kind: str, target_id: str, priority: int = 0) -> None:
        """Insert a task into the DB queue table."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO queue (kind, target_id, priority, created_at) "
                "VALUES (?, ?, ?, ?)",
                (kind, target_id, priority, _now()),
            )

    # ------------------------------------------------------------------
    # Stop-gap failure count (in-memory; P3 持久化接手)
    # ------------------------------------------------------------------

    def _get_failure_count(self, key_id: str, kind: str) -> int:
        return self._failure_count.get((key_id, kind), 0)

    def _inc_failure_count(self, key_id: str, kind: str) -> None:
        key = (key_id, kind)
        self._failure_count[key] = self._failure_count.get(key, 0) + 1

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def _cancel_running_for_goal(self, goal_id: str) -> None:
        """Signal running pipelines for goal_id to stop.

        P2 spec deliberately accepts no-op for thread-pool runtime: threads
        cannot be SIGTERM'd from outside, and step1_stale_filter is also a
        P3 hook. The audit-recognized trade-off (R2 finding F):
          - In-flight Backward / Builder against an already-proved Goal will
            run to completion and may commit orphan sub-goals / strategies.
          - BFS structural refill on the next tick MAY then dispatch Builder
            against those orphans (also wasteful, but functionally harmless:
            their sub-goals' parent Goal is already proved, so the cascade
            will re-prove a duplicate trust_set into the same goals row).
          - P3 step1_stale_filter takes over: it will gate
            _handle_pipeline_finished by re-reading goal.status before cascade
            so stale results are dropped pre-DB-write.
          - P4 subprocess-based runtime can SIGTERM real OS processes here.
        """
        return  # P3: step1_stale_filter; P4: subprocess SIGTERM

    # ------------------------------------------------------------------
    # Queue (P1 compat)
    # ------------------------------------------------------------------

    def _pop_queue(self) -> dict[str, Any] | None:
        """Pop highest-priority (then oldest) task. Returns None if empty."""
        row = self.conn.execute(
            "SELECT id, kind, target_id, payload FROM queue "
            "ORDER BY priority DESC, id ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        q_id, kind, target_id, payload = row
        with self.conn:
            self.conn.execute("DELETE FROM queue WHERE id = ?", (q_id,))
        return {"id": q_id, "kind": kind, "target_id": target_id, "payload": payload}

    # ------------------------------------------------------------------
    # P1 synchronous dispatch (+ P2 Backward support)
    # ------------------------------------------------------------------

    def _dispatch(self, task: dict[str, Any]) -> None:
        """Synchronous dispatch used by P1 _run_loop. P2 adds Backward kind.

        Builder branch keeps P1 cascade-only behavior (no _mark_strategy_dead
        on exhausted) to preserve `--once` semantics required by Phase 1
        acceptance tests (TestAC7SorryDetection: exhausted Strategy leaves
        Goal open). Daemon mode uses _cascade_builder which marks strategy
        dead — that asymmetry is intentional and noted in audit R2 finding H.
        """
        kind = task["kind"]
        if kind == "Builder":
            strategy_id = int(task["target_id"])
            cfg = BuilderConfig(
                t_wall=self.config.t_wall,
                lake_timeout=self.config.lake_timeout,
                base_dir=self.config.base_dir,
            )
            result = Builder(strategy_id, self.conn, cfg).run()
            self._cascade(strategy_id, result)
        elif kind == "Backward":
            goal_id = int(task["target_id"])
            back_cfg = BackwardConfig(
                base_dir=self.config.base_dir,
                lake_cwd=self.config.base_dir,
                lean_timeout=self.config.lake_timeout,
            )
            result = Backward(
                self.conn, self._make_fallback_chain(), back_cfg
            ).run(goal_id)
            self._cascade_backward(goal_id, result)
        else:
            msg = f"Unsupported task kind: {kind!r}"
            self._emit_fatal(msg)
            raise FatalError(msg)

    # ------------------------------------------------------------------
    # Cascade (P1 + P2 trust set + strategy succeeded)
    # ------------------------------------------------------------------

    def _cascade(
        self,
        strategy_id: int,
        result: BuilderResult,
        *,
        strict_trust_set: bool = False,
    ) -> None:
        """Builder proved cascade: trust set + accept rule + goal proved.

        P1 trigger: BuilderResult.outcome=='proved'. P2 additionally:
          - UPDATE strategies SET status='succeeded'
          - Build trust_set via print_axioms (#print axioms)
          - Load allowed axioms from Problems/<problem>/META.md
          - Accept rule check; skip if META.md missing (test environments)
          - Write trust_set JSON to goals.trust_set

        strict_trust_set (R3 fix MED-1):
          - True (P2 daemon, called via _cascade_builder): RuntimeError from
            print_axioms triggers fail-shut (do NOT mark proved + emit pause).
          - False (P1 sync `--once`, called via _dispatch): RuntimeError +
            OSError fall through silently to trust_set=None + still proved.
            Preserves Phase 1 acceptance compat — P1 had no accept-rule
            contract and tests run with misconfigured lake.
        """
        if result.outcome != "proved":
            return

        row = self.conn.execute(
            "SELECT goal_id, lean_path FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()
        if row is None:
            return
        goal_id, lean_path = row

        answer_data = json.dumps({"type": "classical", "lean_path": lean_path})
        trust_set_json: str | None = None
        should_prove = True

        # --- Trust set construction + accept rule ---
        goal_row = self.conn.execute(
            "SELECT problem FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()
        if goal_row is not None:
            problem = goal_row[0]
            thm_name = Path(lean_path).stem
            try:
                axioms = print_axioms(thm_name, self.config.base_dir)
                trust_entries = build_trust_set(axioms)
                trust_set_json = json.dumps(trust_entries)
                # Accept rule: load allowed axioms from META.md
                try:
                    meta = parse_meta(
                        Path(self.config.base_dir) / "Problems" / problem
                    )
                    accepted, rejected = check_accept_rule(trust_entries, meta.axioms)
                    if not accepted:
                        should_prove = False
                        self._emit_event(
                            "cascade",
                            {
                                "strategy_id": strategy_id,
                                "goal_id": goal_id,
                                "rule": "accept_rule_rejected",
                                "rejected_axioms": rejected,
                            },
                        )
                        # R3 fix HIGH-2: spec architecture.md line 480 +
                        # acceptance #7 — write dead_attempts + emit pause
                        # control_signal so the reactor pauses for human review.
                        self._record_accept_reject_dead_attempt(
                            goal_id, strategy_id, rejected
                        )
                        self._event_queue.put(("control_signal", "pause"))
                except MetaError:
                    pass  # No META.md → skip accept rule (test environments)
            except (RuntimeError, OSError) as exc:
                # R3 fix MED-1: trust_set construction failure routing.
                # strict_trust_set=True (P2 daemon path): impl §5.3 字面
                #   "proved 前必驗" → fail-shut. emit cascade warning + pause.
                # strict_trust_set=False (P1 sync path): silent fallback to
                #   trust_set=None + still proved. P1 had no accept-rule
                #   contract; phase 1 acceptance suite relies on this.
                if strict_trust_set:
                    should_prove = False
                    self._emit_event(
                        "cascade",
                        {
                            "strategy_id": strategy_id,
                            "goal_id": goal_id,
                            "rule": "trust_set_construction_failed",
                            "error": str(exc),
                        },
                    )
                    self._event_queue.put(("control_signal", "pause"))
                else:
                    trust_set_json = None

        if not should_prove:
            return

        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE strategies SET status = 'succeeded' WHERE id = ?",
                    (strategy_id,),
                )
            self._update_goal_proved(goal_id, answer_data, trust_set_json)
            self._emit_event(
                "cascade",
                {
                    "strategy_id": strategy_id,
                    "goal_id": goal_id,
                    "rule": "succeeded→proved",
                },
            )
        except sqlite3.Error as exc:
            self._emit_fatal(str(exc))
            raise FatalError(str(exc)) from exc

    def _update_goal_proved(
        self,
        goal_id: int,
        answer_data: str,
        trust_set_json: str | None = None,
    ) -> None:
        """Write proved status to goals row (separated for testability).

        P3 C21 cache invalidation hook (impl §2.3): a Goal flipping to proved
        changes both local_goals search results (proved Goals are search
        candidates) and dedupe results (proved Goal types now match against
        future candidates). Kill both scopes.
        """
        with self.conn:
            self.conn.execute(
                "UPDATE goals SET status = 'proved', answer_data = ?, "
                "trust_set = ?, status_changed_at = ? WHERE id = ?",
                (answer_data, trust_set_json, _now(), goal_id),
            )
        invalidate_for_goals_write(self.conn)

    def _record_accept_reject_dead_attempt(
        self,
        goal_id: int,
        strategy_id: int,
        rejected_axioms: list[str],
    ) -> None:
        """Insert dead_attempts row recording an accept-rule rejection.

        Spec (architecture.md line 480 + acceptance #7): when trust_set fails
        the accept rule, write `dead_attempts` row recording 'trust_set rejected:
        <違規 entries>'. dead_attempts.pipeline_id is FK→pipelines(id), so we
        look up the most recent Builder pipeline that produced this strategy's
        proof; if missing (defensive), we emit a warning event but do NOT
        silently skip — silent skip would re-introduce the silent-PASS pattern.
        """
        pipeline_row = self.conn.execute(
            "SELECT id FROM pipelines WHERE target_id = ? AND kind = 'Builder' "
            "ORDER BY started_at DESC LIMIT 1",
            (str(strategy_id),),
        ).fetchone()
        if pipeline_row is None:
            # Defensive: no Builder pipeline found. Emit a warning event so the
            # rejection is still observable in the audit log even though the
            # dead_attempts FK can't be satisfied.
            self._emit_event(
                "cascade",
                {
                    "goal_id": goal_id,
                    "strategy_id": strategy_id,
                    "rule": "accept_rule_rejected_no_pipeline_id",
                    "rejected_axioms": rejected_axioms,
                },
            )
            return
        pipeline_id = pipeline_row[0]
        reason = f"trust_set rejected: {', '.join(rejected_axioms)}"
        with self.conn:
            self.conn.execute(
                "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
                "pipeline_kind, outcome, reason_summary, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(goal_id),
                    "Goal",
                    pipeline_id,
                    "Builder",
                    "trust_set_rejected",
                    reason,
                    _now(),
                ),
            )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _emit_event(self, kind: str, payload: dict[str, Any]) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                (kind, json.dumps(payload), _now()),
            )

    def _emit_fatal(self, error: str) -> None:
        """Emit fatal event; best-effort (does not mask original exception)."""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                    ("fatal", json.dumps({"error": error}), _now()),
                )
        except Exception:
            pass
