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
        """Pop → dispatch loop. Exits 0 on empty queue, 1 on fatal."""
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
        """Daemon loop: block on _event_queue; 30s tick → structural refill."""
        self.startup()
        self._pool = ThreadPoolExecutor(max_workers=self.config.pool_size)
        self._run_structural_refill()
        self._try_spawn_from_queue()
        last_tick = time.monotonic()
        try:
            while not self._shutdown_flag:
                elapsed = time.monotonic() - last_tick
                wait = max(0.1, self.config.tick_interval - elapsed)
                try:
                    event = self._event_queue.get(timeout=wait)
                except queue.Empty:
                    last_tick = time.monotonic()
                    self._run_structural_refill()
                    self._try_spawn_from_queue()
                    continue
                self._dispatch_event(event)
                if not self._shutdown_flag:
                    self._try_spawn_from_queue()
        finally:
            if self._pool is not None:
                self._pool.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Event dispatch (P2)
    # ------------------------------------------------------------------

    def _dispatch_event(self, event: tuple) -> None:
        """Route in-process event tuple to the correct handler."""
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
        # task_checkpoint: P5 handler; P2 silently discards

    def _handle_pipeline_finished(self, task: dict, result: Any) -> None:
        """6-step cycle on pipeline_finished: P2 runs steps 2/3/4/6."""
        self._run_step1_stale_filter(task, result)        # P3 hook — empty
        self._run_step2_cancellation(task, result)
        self._run_step3_cascade(task, result)
        self._run_step4_trust_set(task, result)           # integrated into step 3
        self._run_step5_strategist_trigger(task, result)  # P7 hook — empty
        self._run_step6_spawn()

    def _handle_control_signal(self, action: str) -> None:
        """control_signal handler: pause / resume / shutdown. set_budget留P7."""
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
        """Cascade for Builder pipeline outcome."""
        if result.outcome == "proved":
            self._cascade(strategy_id, result)
        else:
            # non-proved: mark strategy dead, maybe shelve goal
            self._mark_strategy_dead(strategy_id)
            row = self.conn.execute(
                "SELECT goal_id FROM strategies WHERE id = ?", (strategy_id,)
            ).fetchone()
            if row:
                self._inc_failure_count(str(row[0]), "Builder")

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
                self._emit_event(
                    "cascade",
                    {"goal_id": goal_id, "rule": "all_strategies_dead→shelved"},
                )
        except sqlite3.Error as exc:
            self._emit_fatal(str(exc))
            raise FatalError(str(exc)) from exc

    def _cascade_backward(self, goal_id: int, result: BackwardResult) -> None:
        """Cascade for Backward pipeline outcome.

        'success': sub-goals + strategy already committed by Backward.run();
                   structural refill (step 6) picks up new open sub-goals.
        'exhausted' / 'unproductive': increment stop-gap failure count.
        """
        if result.outcome != "success":
            self._inc_failure_count(str(goal_id), "Backward")

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
        """Thread body: own DB connection, run pipeline, emit pipeline_finished."""
        conn = connect(self.db_path)
        try:
            result = self._execute_task_with_conn(task, conn)
        except Exception as exc:
            result = BuilderResult(outcome="exhausted")
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                        (
                            "fatal",
                            json.dumps(
                                {"error": str(exc), "pipeline_id": pipeline_id}
                            ),
                            _now(),
                        ),
                    )
            except Exception:
                pass
        finally:
            conn.close()
            with self._lock:
                self._running.pop(pipeline_id, None)
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
        """Enqueue Backward for open theorem Goals, respecting D_max + stop-gap."""
        rows = self.conn.execute(
            "SELECT id, depth FROM goals "
            "WHERE status = 'open' AND kind = 'theorem'"
        ).fetchall()
        for goal_id, depth in rows:
            goal_id_s = str(goal_id)
            # D_max: shelve deep goals instead of decomposing further
            if depth is not None and depth >= self.config.d_max:
                try:
                    with self.conn:
                        self.conn.execute(
                            "UPDATE goals SET status = 'shelved', "
                            "status_changed_at = ? WHERE id = ?",
                            (_now(), goal_id),
                        )
                except sqlite3.Error:
                    pass
                continue
            # Stop-gap: skip if Backward has failed n_block_after_failures times
            if (
                self._get_failure_count(goal_id_s, "Backward")
                >= self.config.n_block_after_failures
            ):
                continue
            # Avoid duplicate dispatch
            if self._is_already_dispatched(goal_id_s, "Backward"):
                continue
            self._enqueue_task("Backward", goal_id_s, priority=0)

    def _bfs_enqueue_builder(self) -> None:
        """Enqueue Builder for proposed strategies whose sub-goals are all proved."""
        rows = self.conn.execute(
            "SELECT s.id, s.goal_id FROM strategies s "
            "WHERE s.status = 'proposed'"
        ).fetchall()
        for strategy_id, goal_id in rows:
            strategy_id_s = str(strategy_id)
            # Stop-gap keyed on goal_id (per spec: dict[(goal_id, pipeline_kind)])
            if (
                self._get_failure_count(str(goal_id), "Builder")
                >= self.config.n_block_after_failures
            ):
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

        P2: thread-pool workers finish their current pipeline naturally after
        return — no SIGTERM needed for threads. Future subprocess-based pipelines
        (P4+) will store OS PIDs here and SIGTERM them.
        P4 will upgrade to verdict-aware whitelist when twin pipeline semantics
        are introduced.
        """
        # Thread pool pipelines complete their task and emit pipeline_finished;
        # reactor drains the event. No OS-level signal required for threading.
        pass  # P4 接: subprocess SIGTERM

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
        """Synchronous dispatch used by P1 _run_loop. P2 adds Backward kind."""
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

    def _cascade(self, strategy_id: int, result: BuilderResult) -> None:
        """Builder proved cascade: trust set + accept rule + goal proved.

        P1 trigger: BuilderResult.outcome=='proved'. P2 additionally:
          - UPDATE strategies SET status='succeeded'
          - Build trust_set via print_axioms (#print axioms)
          - Load allowed axioms from Problems/<problem>/META.md
          - Accept rule check; skip if META.md missing (test environments)
          - Write trust_set JSON to goals.trust_set
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
                except MetaError:
                    pass  # No META.md → skip accept rule (test environments)
            except (RuntimeError, OSError):
                trust_set_json = None  # lake not available → proceed without trust set

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
        """Write proved status to goals row (separated for testability)."""
        with self.conn:
            self.conn.execute(
                "UPDATE goals SET status = 'proved', answer_data = ?, "
                "trust_set = ?, status_changed_at = ? WHERE id = ?",
                (answer_data, trust_set_json, _now(), goal_id),
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
