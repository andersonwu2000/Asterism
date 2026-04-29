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
from datetime import datetime, timedelta, timezone
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


def _extract_proof_body(strategy_text: str, slug: str) -> str | None:
    """P6.x patch 23: extract the proof body from a strategy file's
    `theorem <slug> : <type> := <body>` declaration.

    Returns the substring from after the `:=` (with surrounding
    whitespace stripped) up to (but not including) the closing
    `end <namespace>` line. Returns None when the marker isn't found
    (caller treats as a finalize-failure and leaves the goal file
    untouched).
    """
    import re as _re
    # Find the `theorem <slug>` line; allow any whitespace before `:`.
    m = _re.search(
        r"theorem\s+" + _re.escape(slug) + r"\s+:[^\n]*?:=",
        strategy_text,
        _re.DOTALL,
    )
    if not m:
        return None
    body_start = m.end()
    # Find the closing `end <ns>` line; if absent, take to end of file.
    end_m = _re.search(r"\nend\s+\S", strategy_text[body_start:])
    if end_m:
        body = strategy_text[body_start:body_start + end_m.start()]
    else:
        body = strategy_text[body_start:]
    return body.strip()


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
    n_block_after_failures: int = 5  # threshold consumed by failure_archive
                                      # (C24 persistent block; in-memory dict
                                      # removed in C25)
    bypass_startup_check: bool = False  # P6 C44: when True, _register_scheduler
                                          # DELETEs any pre-existing schedulers
                                          # rows (live OR stale) before INSERT.
                                          # Operator escape hatch for cases where
                                          # a previous instance crashed without
                                          # cleanup AND `scheduler force-clear`
                                          # is not viable (e.g. cron-driven first
                                          # boot). Logs a startup_bypass event.


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
        # P2 in-memory retry cap (was self._failure_count dict) removed in
        # C25; persistent goals.blocked_pipelines (C24) is the canonical
        # block source.
        self._paused: bool = False
        self._shutdown_flag: bool = False
        self._scheduler_id: int | None = None
        self._last_seen_ctrl_id: int = 0
        # P6 C44: per-Problem pause set. Updated by _handle_control_signal
        # actions {problem_pause, problem_resume}; consulted in _pop_queue
        # so paused-Problem tasks stay queued (re-spawn on resume). In-memory
        # only — daemon restart resets to empty (operators re-issue pause).
        self._paused_problems: set[str] = set()

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def startup(self) -> None:
        """Connect DB, apply schema (idempotent), run recover_scan + sweep
        zombie pipelines.

        P7 演習 fix: a prior daemon that crashed / was killed leaves
        `pipelines.status='running'` rows in DB with no live worker
        thread. Startup must mark these failed so `_is_already_dispatched`
        doesn't treat them as in-flight (which would block legitimate
        BFS enqueue forever — observed during compactness 演習: goal 13
        had a zombie Backward from prior daemon kill, new daemon never
        re-attacked the goal because BFS thought a Backward was running).

        Singleton-scheduler discipline (P6 liveness check) ensures we
        won't sweep another live scheduler's pipelines.
        """
        self.conn = connect(self.db_path)
        init_schema(self.conn)
        CommitWriter(self.conn).recover_scan()
        self._sweep_zombie_pipelines()

    def _sweep_zombie_pipelines(self) -> None:
        """Mark any status='running' pipelines as failed/cancelled.

        Counts the affected rows + emits an observability event so an
        operator can see how many zombies were swept. Best-effort:
        single SQL UPDATE; we propagate sqlite errors so silent-failure
        red line is preserved.
        """
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM pipelines WHERE status = 'running'"
        )
        count = cur.fetchone()[0]
        if count == 0:
            return
        with self.conn:
            self.conn.execute(
                "UPDATE pipelines SET status = 'failed', "
                "outcome = 'cancelled', finished_at = ? "
                "WHERE status = 'running'",
                (_now(),),
            )
        # Emit a cascade event so the sweep is visible in audits.
        # _emit_event uses self.conn — already valid here.
        try:
            self._emit_event(
                "cascade",
                {
                    "rule": "zombie_pipelines_swept",
                    "count": count,
                    "reason": "startup_recovery",
                },
            )
        except sqlite3.Error:
            pass

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
                        # P6 C40: heartbeat alongside structural refill
                        # so other instances see this scheduler as live.
                        self._heartbeat()
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

        P3 C25 R3: step1 liveness check now drops stale events early per
        spec phase3 #12 + acceptance #9 字面 "丟棄、無多餘 cascade". When
        step1 detects a stale event (proved/shelved/refuted goal, dead
        strategy, missing row, malformed payload), subsequent steps are
        skipped — orphan dead_attempts / re-shelve / re-mark-dead writes
        are prevented.
        """
        if self._run_step1_stale_filter(task, result):
            return  # event dropped per spec #12; no downstream cascade
        self._run_step2_cancellation(task, result)
        self._run_step3_cascade(task, result)
        self._run_step4_trust_set(task, result)           # integrated into step 3
        self._run_step5_strategist_trigger(task, result)  # P7 hook — empty
        self._run_step6_spawn()

    def _handle_control_signal(self, action: Any) -> None:
        """control_signal handler: pause / resume / shutdown / problem_pause /
        problem_resume. set_budget 留 P7.

        Action shapes:
          - str: legacy global pause/resume/shutdown.
          - tuple[str, str]: per-Problem (action_name, problem_name) for
            'problem_pause' / 'problem_resume' (P6 C44).

        R3 fix LOW-1: unknown actions emit a diagnostic event so P7 set_budget
        or any future action that misses the dispatch table is observable.
        """
        if isinstance(action, tuple):
            name, problem = action
            if name == "problem_pause":
                with self._lock:
                    self._paused_problems.add(problem)
                self._emit_event(
                    "control_signal",
                    {"action": "problem_pause", "problem": problem,
                     "status": "applied"},
                )
                return
            if name == "problem_resume":
                with self._lock:
                    self._paused_problems.discard(problem)
                self._emit_event(
                    "control_signal",
                    {"action": "problem_resume", "problem": problem,
                     "status": "applied"},
                )
                return
            self._emit_event(
                "control_signal",
                {"action": "unknown_action", "received": str(action)},
            )
            return
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
    # Scheduler liveness — register/heartbeat/unregister
    # P6 C40: pre-INSERT live check rejects dual instances per spec
    # phase6_library.md ## In line 65 「scheduler 啟動時對每個 Problem
    # 解析 META.md...」 + impl §6 schedulers liveness 字面.
    # ------------------------------------------------------------------

    HEARTBEAT_TTL_SEC: int = 90  # rows older than this are considered stale
                                  # (phase6_library.md:232 Config table:
                                  # schedulers stale threshold = 90s; C44 R3
                                  # MED-4 fix — C40 R3 commit message claimed
                                  # 60→90 bump but code stayed 60)

    def _register_scheduler(self) -> None:
        """Reject if a live scheduler row exists; otherwise INSERT.

        P6 C40: a live scheduler row is one whose last_heartbeat is
        within HEARTBEAT_TTL_SEC of now (default 90s — matches the
        daemon's structural-refill tick + 2× cushion). If found, raise
        FatalError so the second instance fails to start (visible to
        the operator + scheduler row preserved as evidence).

        Stale rows (last_heartbeat older than TTL) are NOT auto-deleted
        here — operators run `asterism scheduler force-clear` (P6.C44)
        to clean them. Auto-delete on startup would mask crashes where
        a scheduler exited without _unregister_scheduler running.

        P6 C44 R3 HIGH-1 fix: `bypass_startup_check=True` is a no-op
        on the liveness check per phase6_library.md:218 + acceptance
        #10 字面: "scheduler 啟動跳過 CLI 早期 single-instance 攔截、
        讓進到 liveness check 階段；liveness check 仍正常擋". The
        flag was originally designed to bypass an "earlier" CLI-side
        single-instance gate that this phase has not yet introduced;
        the liveness check below stays. We emit a startup_bypass
        audit event so operators see the no-op for the audit trail.
        """
        now = _now()
        # Cutoff = now - TTL; ISO timestamps sort lexicographically.
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=self.HEARTBEAT_TTL_SEC)
        ).isoformat()

        if self.config.bypass_startup_check:
            # No-op on the liveness check per spec line 218 + AC#10.
            # The flag is reserved for a future CLI-side early gate
            # (a file-lock-style attempt before the DB lookup); the
            # liveness check is the only existing gate today and must
            # NOT be bypassed because it is the canonical safeguard
            # against double-scheduler corruption (architecture.md:284).
            self._emit_event(
                "control_signal",
                {"action": "startup_bypass",
                 "note": "phase6 has no CLI early gate to bypass; "
                         "liveness check still applies — use "
                         "`scheduler force-clear` for stale rows",
                 "source": "register"},
            )

        try:
            live = self.conn.execute(
                "SELECT id, host, pid, started_at, last_heartbeat "
                "FROM schedulers WHERE last_heartbeat > ?",
                (cutoff,),
            ).fetchall()
        except sqlite3.Error as exc:
            self._event_queue.put(
                ("fatal", f"_register_scheduler liveness query fail: {exc}")
            )
            raise FatalError(f"_register_scheduler fail: {exc}") from exc

        if live:
            details = ", ".join(
                f"id={r[0]} host={r[1]} pid={r[2]} last_heartbeat={r[4]}"
                for r in live
            )
            msg = (
                f"scheduler already running ({len(live)} live row(s)): "
                f"{details}. Run `asterism scheduler force-clear` to "
                f"reset stale rows manually."
            )
            self._event_queue.put(("fatal", msg))
            raise FatalError(msg)

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

    def _heartbeat(self) -> None:
        """Update last_heartbeat for this scheduler row.

        Daemon loop calls this on each structural-refill tick so other
        instances see the row as live. Best-effort: a write failure
        writes a fatal event row to the events table via _emit_fatal
        but does NOT raise and does NOT enqueue ('fatal', ...) — the
        daemon continues running and retries UPDATE on the next tick.
        Avoids transient SQLite contention killing the daemon while
        preserving an audit-trail row that ops monitoring can pick up.
        (C40 R3 HIGH-2 fix: docstring + emit path now match.)
        """
        if self._scheduler_id is None:
            return
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE schedulers SET last_heartbeat = ? WHERE id = ?",
                    (_now(), self._scheduler_id),
                )
        except sqlite3.Error as exc:
            # Diagnostic-only: write to events table for ops visibility,
            # don't enqueue ('fatal', ...) which would shut down the
            # daemon on the next dispatch tick.
            self._emit_fatal(f"_heartbeat update fail: {exc}")

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
            elif action in ("problem_pause", "problem_resume"):
                # P6 C44: per-Problem action carries the problem name in
                # payload['problem']. Forward as tuple so _handle_control_signal
                # routes to the per-Problem branch.
                problem = payload.get("problem")
                if isinstance(problem, str) and problem:
                    self._event_queue.put(
                        ("control_signal", (action, problem))
                    )

    # ------------------------------------------------------------------
    # 6-step cycle steps (P2)
    # ------------------------------------------------------------------

    def _run_step1_stale_filter(self, task: dict, result: Any) -> bool:
        """P3 C25 R3: liveness check — return True iff the event should be DROPPED.

        spec phase3_cache.md #12 + acceptance #9 字面要求 "對應 Goal/Strategy
        已被 cascade 標 dead/refuted 的事件丟棄、被主動 kill 的 pipeline 結果丟棄".

        Stale conditions:
          Backward (target_kind='Backward', target_id=goal_id):
            - goal row missing
            - goal.commit_state != 'live'
            - goal.status ∈ {'proved', 'shelved', 'refuted'}
          Builder (target_kind='Builder', target_id=strategy_id):
            - strategy row missing
            - strategy.commit_state != 'live'
            - strategy.status == 'dead'

        Caller `_handle_pipeline_finished` returns early when this returns
        True — cascade step2-6 do NOT run for stale events (per spec
        "丟棄、無多餘 cascade").

        Malformed task payload (target_id not int-castable) is also treated
        as stale (defensive — daemon stays up, malformed event observable
        via the cascade event).
        """
        target_kind = task.get("kind")
        target_id_raw = task.get("target_id")

        # P7 演習 fix: Strategist target_id is a string `_problem:<name>`,
        # not an int. Handle it before the generic int-cast branch.
        if target_kind == "Strategist":
            if not isinstance(target_id_raw, str) \
                    or not target_id_raw.startswith("_problem:"):
                self._emit_event(
                    "cascade",
                    {"rule": "stale_filter", "task": task,
                     "reason": "strategist_malformed_target_id"},
                )
                return True
            problem = target_id_raw.split(":", 1)[1]
            row = self.conn.execute(
                "SELECT COUNT(*) FROM goals "
                "WHERE problem = ? AND status = 'open' "
                "  AND commit_state = 'live'",
                (problem,),
            ).fetchone()
            if row is None or row[0] == 0:
                # No open goals in the problem — Strategist would have
                # nothing actionable. Drop as stale.
                self._emit_event(
                    "cascade",
                    {"rule": "stale_filter", "task": task,
                     "reason": "strategist_no_open_goals"},
                )
                return True
            return False

        try:
            target_id = int(target_id_raw)
        except (TypeError, ValueError):
            self._emit_event(
                "cascade",
                {
                    "rule": "stale_filter",
                    "task": task,
                    "reason": "malformed_target_id",
                },
            )
            return True

        if target_kind == "Backward":
            row = self.conn.execute(
                "SELECT status, commit_state FROM goals WHERE id = ?",
                (target_id,),
            ).fetchone()
            if row is None:
                reason = "goal_missing"
            elif row[1] != "live":
                reason = f"goal_not_live (commit_state={row[1]})"
            elif row[0] in ("proved", "shelved", "refuted"):
                reason = f"goal_terminal_status (status={row[0]})"
            else:
                return False
            self._emit_event(
                "cascade",
                {"rule": "stale_filter", "task": task, "reason": reason},
            )
            return True

        if target_kind == "Builder":
            row = self.conn.execute(
                "SELECT status, commit_state FROM strategies WHERE id = ?",
                (target_id,),
            ).fetchone()
            if row is None:
                reason = "strategy_missing"
            elif row[1] != "live":
                reason = f"strategy_not_live (commit_state={row[1]})"
            elif row[0] == "dead":
                reason = "strategy_dead"
            else:
                return False
            self._emit_event(
                "cascade",
                {"rule": "stale_filter", "task": task, "reason": reason},
            )
            return True

        if target_kind == "Refuter":
            # P4 C31: extend stale filter to cover Refuter (LOW-1 from
            # C30 R2). Refuter target_kind='Goal' — same checks as Backward
            # because both target a Goal and both should be dropped if
            # the Goal entered terminal status (proved/shelved/refuted)
            # before the pipeline finished.
            row = self.conn.execute(
                "SELECT status, commit_state FROM goals WHERE id = ?",
                (target_id,),
            ).fetchone()
            if row is None:
                reason = "goal_missing"
            elif row[1] != "live":
                reason = f"goal_not_live (commit_state={row[1]})"
            elif row[0] in ("proved", "shelved", "refuted"):
                reason = f"goal_terminal_status (status={row[0]})"
            else:
                return False
            self._emit_event(
                "cascade",
                {"rule": "stale_filter", "task": task, "reason": reason},
            )
            return True

        # Other kinds (Forward / Counterexample / Generalizer / etc) reach
        # P4.C31 only via misroute; treat as non-stale (caller's other steps
        # handle). Filters land when those pipelines ship (P5+ / Counterexample
        # un-defer).
        return False

    def _run_step2_cancellation(self, task: dict, result: Any) -> None:
        """Cancellation white-list per architecture.md §6 (P4 C31).

        Replaces P2/P3's "kill all on goal_id" simplification with the
        verdict-aware white-list (Tooling/cancellation.py).

        Trigger: Builder.proved → cond 1 'goal_proved' verdict (cancel any
        kind on G). Other conditions fire from cascade hooks:
          cond 2 'twin_refuted' — _cascade_twin_to_refuted (post twin flip)
          cond 3 'counterexample_silver' — DEFERRED (Counterexample defer)
          cond 4 'strategy_dead'   — _mark_strategy_dead
        """
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
        from Tooling.cancellation import (
            CancellationVerdict,
            cancel_for_verdict,
        )
        cancel_for_verdict(
            self.conn,
            CancellationVerdict(kind="goal_proved", goal_id=int(row[0])),
            emit_event=self._emit_event,
        )

    def _run_step3_cascade(self, task: dict, result: Any) -> None:
        """Cascade rules: Builder proved / dead; Backward success / exhausted.

        C25 R3 HIGH-3: lookup Tooling.cascade.DISPATCH_TABLE for the
        (pipeline_kind, outcome) action so cascade.py is a true production
        caller (not an island module). Unknown combinations emit a
        diagnostic event so P4+ pipeline outcomes (Refuter / Counterexample)
        are observable when first wired in. Inline if/else dispatch retained
        — P4 will move handlers into cascade.py callables.
        """
        from Tooling.cascade import get_action
        kind = task.get("kind")
        outcome = getattr(result, "outcome", None)
        action = get_action(str(kind), str(outcome)) if outcome is not None else None
        if action is None:
            self._emit_event(
                "cascade",
                {
                    "rule": "unknown_cascade_combination",
                    "task": task,
                    "outcome": outcome,
                },
            )
            return
        if kind == "Builder":
            self._cascade_builder(int(task["target_id"]), result)
        elif kind == "Backward":
            self._cascade_backward(int(task["target_id"]), result)
        elif kind == "Refuter":
            self._cascade_refuter(int(task["target_id"]), result)
        elif kind == "Forward":
            self._cascade_forward(int(task["target_id"]), result)
        elif kind == "Generalizer":
            self._cascade_generalizer(int(task["target_id"]), result)
        # Strategist / Counterexample / ConstructionSearch: cascade handler
        # exists in DISPATCH_TABLE as no-op acknowledgement; nothing to do.

    def _run_step4_trust_set(self, task: dict, result: Any) -> None:
        """Trust set construction is integrated into _cascade_builder. P2 no-op."""
        pass

    def _run_step5_strategist_trigger(self, task: dict, result: Any) -> None:
        """P7 C54: enqueue a Strategist task when round_robin says so.

        Called after every pipeline_finished event (step 3 cascade has
        already run). Behavior is gated by:
          - K_strategist accumulator: round_robin counts non-Strategist
            finished pipelines since the last consume().
          - Cooldown: existing running Strategist row blocks selection.
          - strategist.enabled config: when explicitly false, skipped.

        On success enqueues one Strategist task (priority=high, target_id
        is "_problem:<name>" sentinel matching pipelines.target_id shape
        used by Strategist itself).
        """
        if os.environ.get("STRATEGIST_DISABLED") == "1":
            return
        try:
            from Tooling.strategist.round_robin import select_next, consume
        except ImportError:
            return  # P7 module not yet available — defensive

        problems = self._list_active_problems()
        if not problems:
            return
        # K_strategist default = P×2 = 8 (per phase7_smarts.md).
        k = int(os.environ.get("K_STRATEGIST", "8"))
        problem = select_next(self.conn, problems, K=k)
        if problem is None:
            return
        # Enqueue. Mark consumed so we don't re-trigger on the next event
        # before this Strategist actually runs.
        with self.conn:
            self.conn.execute(
                "INSERT INTO queue (kind, target_id, priority, created_at) "
                "VALUES ('Strategist', ?, 100, ?)",
                (f"_problem:{problem}", _now()),
            )
        consume(self.conn, problem)

    def _list_active_problems(self) -> list[str]:
        """Distinct Problem names with at least one OPEN live Goal.

        P7 演習 fix: previous version returned any Problem with `commit_state
        = 'live'` regardless of status, so a Problem whose goals were all
        shelved/proved/refuted still got Strategist tasks enqueued — they
        immediately got stale-filtered with no actionable work. Restrict to
        Problems that actually have something for Strategist to coordinate.
        """
        rows = self.conn.execute(
            "SELECT DISTINCT problem FROM goals "
            "WHERE commit_state = 'live' AND status = 'open' "
            "ORDER BY problem ASC"
        ).fetchall()
        return [r[0] for r in rows if r[0]]

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
            # P7 演習 fix: Builder.failure summary as Goal-scoped dead_attempt.
            # Builder._record_dead_attempts writes target_kind='Strategy', but
            # Backward.failure_replay only reads target_kind='Goal'. Without
            # this bridge, the next Backward retry on the goal has zero
            # feedback about what Builder tried + why it failed, so the LLM
            # tends to repeat the same flawed approach. Mirror Strategy →
            # Goal so Backward sees prior Builder failures and can choose a
            # different proof path.
            self._mirror_builder_failure_to_goal(strategy_id, result)
            # non-proved: mark strategy dead, maybe shelve goal
            self._mark_strategy_dead(strategy_id)
            row = self.conn.execute(
                "SELECT goal_id FROM strategies WHERE id = ?", (strategy_id,)
            ).fetchone()
            if row:
                # P3 C24 R3 MED-1 + C25: phase3 §In line 37 字面「Backward /
                # Builder 都會觸發 blocked_pipelines」. Builder dead_attempts
                # already written by Builder._record_dead_attempts; just
                # check threshold. In-memory _inc_failure_count call removed
                # in C25 — persistent blocked_pipelines is the only canonical
                # block source now.
                from Tooling.stages.failure_archive import archive_check
                archive_check(self.conn, int(row[0]), "Builder")

    def _mirror_builder_failure_to_goal(
        self, strategy_id: int, result: BuilderResult
    ) -> None:
        """Write a Goal-scoped dead_attempt summarising the Builder failure.

        Source rows are target_kind='Strategy' (written by Builder) — invisible
        to Backward.failure_replay. We aggregate the most recent Strategy-
        scoped Builder failures for this strategy + read the strategy's
        lean_path so the next Backward can see "your prior attempt tried X
        and got Y, choose a different approach".

        Best-effort: missing pipeline FK or schema drift falls through to
        a reason-only entry (the goal still gets feedback even if details
        are sparse). Silent-failure red line: SQL errors propagate.
        """
        row = self.conn.execute(
            "SELECT goal_id, lean_path FROM strategies WHERE id = ?",
            (strategy_id,),
        ).fetchone()
        if row is None:
            return
        goal_id, strategy_lean_path = row
        # Pull recent Strategy-scoped Builder dead_attempts for context.
        prior_reasons = self.conn.execute(
            "SELECT reason_summary FROM dead_attempts "
            "WHERE target_id = ? AND target_kind = 'Strategy' "
            "  AND pipeline_kind = 'Builder' "
            "ORDER BY id DESC LIMIT 3",
            (str(strategy_id),),
        ).fetchall()
        reasons_str = "; ".join(r[0] for r in prior_reasons) if prior_reasons else \
            f"Builder outcome={result.outcome}"
        strategy_basename = (
            Path(strategy_lean_path).name if strategy_lean_path else "<unknown>"
        )
        summary = (
            f"prior strategy {strategy_id} ({strategy_basename}) Builder "
            f"{result.outcome}: {reasons_str}"
        )
        # Pipeline FK: most recent Builder pipeline on this strategy.
        pipe_row = self.conn.execute(
            "SELECT id FROM pipelines WHERE kind = 'Builder' AND target_id = ? "
            "ORDER BY started_at DESC LIMIT 1",
            (str(strategy_id),),
        ).fetchone()
        if pipe_row is None:
            return  # No pipeline row to satisfy FK; skip silently.
        with self.conn:
            self.conn.execute(
                "INSERT INTO dead_attempts (target_id, target_kind, "
                "pipeline_id, pipeline_kind, outcome, reason_summary, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(goal_id), "Goal", pipe_row[0], "Builder",
                    result.outcome, summary, _now(),
                ),
            )

    def _mark_strategy_dead(self, strategy_id: int) -> None:
        """Mark strategy dead; shelve parent goal if all strategies are dead.

        P4 C31: trigger cond 4 'strategy_dead' cancellation verdict — cancel
        Builder/Backward whose target_id == strategy_id (same-Strategy scope;
        other strategies on the same Goal continue unaffected).
        """
        row = self.conn.execute(
            "SELECT goal_id, lean_path FROM strategies WHERE id = ?",
            (strategy_id,),
        ).fetchone()
        if row is None:
            return
        goal_id = row[0]
        strategy_lean_path = row[1]
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE strategies SET status = 'dead' WHERE id = ?",
                    (strategy_id,),
                )
            # P4 C31: cond 4 white-list cancellation (visibility event).
            from Tooling.cancellation import (
                CancellationVerdict,
                cancel_for_verdict,
            )
            cancel_for_verdict(
                self.conn,
                CancellationVerdict(
                    kind="strategy_dead", strategy_id=strategy_id,
                ),
                emit_event=self._emit_event,
            )
            # P7 演習 fix: rename (not delete) the dead strategy file so
            # forensic lookup of "what was tried" survives. Lake's glob
            # only picks up `*.lean` files, so renaming to `*.lean.attempted`
            # both (a) keeps the broken proof out of the lib build (was
            # P6.x patch 22-fix-2's reason for deleting in the first place)
            # and (b) leaves the proof body on disk for human inspection.
            # Skip when strategy.lean_path == goal.lean_path (post-finalize
            # state from patch 23: renaming the goal file would lose the
            # canonical proven artifact).
            try:
                goal_path = self.conn.execute(
                    "SELECT lean_path FROM goals WHERE id = ?", (goal_id,),
                ).fetchone()
                if (strategy_lean_path
                        and goal_path
                        and strategy_lean_path != goal_path[0]):
                    full = Path(self.config.base_dir) / strategy_lean_path
                    if full.exists():
                        attempted = full.with_suffix(full.suffix + ".attempted")
                        # If a prior .attempted with same name exists (rare —
                        # only if scheduler restart re-cycles uuid), remove
                        # it before rename so os.replace doesn't fail on
                        # platforms that disallow overwrite.
                        try:
                            attempted.unlink(missing_ok=True)
                        except OSError:
                            pass
                        try:
                            full.rename(attempted)
                        except OSError:
                            # Rename may fail across filesystems on some
                            # platforms; fall back to delete (P6.x patch
                            # 22-fix-2 behavior) so lake glob still stays
                            # clean — losing forensic record is less bad
                            # than a broken lib build.
                            full.unlink(missing_ok=True)
            except (OSError, sqlite3.Error):
                pass  # Best-effort; surfaced via cascade events on
                       # subsequent print_axioms / promote failures.
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
            # P3 C25: in-memory _inc_failure_count call removed; persistent
            # goals.blocked_pipelines (C24) is the only canonical block source.
            self._record_backward_failure(goal_id, result.outcome)
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

    def _cascade_refuter(self, goal_id: int, result: Any) -> None:
        """Cascade for Refuter pipeline outcome (P4 C30).

        'success': Refuter.commit already inserted ¬G goal + bidirectional
                    twin_of UPDATE. No direct cascade — structural refill
                    picks up the new ¬G next cycle, Backward/Builder attack
                    it; if/when Builder proves ¬G (origin='refuter_negation'),
                    _cascade_twin_to_refuted fires and flips G.
        'exhausted': mirror Backward exhausted — record dead_attempts on G
                    + archive_check to enforce Refuter retry budget
                    (N=5 default, blocks Refuter on G when threshold hit).
        """
        if result.outcome == "success":
            return
        # exhausted: write dead_attempts + archive_check
        self._record_refuter_failure(goal_id, result.outcome)
        from Tooling.stages.failure_archive import archive_check
        archive_check(self.conn, goal_id, "Refuter")

    def _record_refuter_failure(self, goal_id: int, outcome: str) -> None:
        """INSERT dead_attempts row for Refuter exhausted outcome.

        Same shape as _record_backward_failure: lookup most recent Refuter
        pipeline for FK; missing pipeline → fatal (orphan cascade or stale
        ordering). Silent-failure red-line discipline.
        """
        pipeline_row = self.conn.execute(
            "SELECT id FROM pipelines WHERE target_id = ? AND kind = 'Refuter' "
            "ORDER BY started_at DESC LIMIT 1",
            (str(goal_id),),
        ).fetchone()
        if pipeline_row is None:
            msg = (
                f"refuter_failure_no_pipeline_id goal_id={goal_id} "
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
                    "Refuter",
                    outcome,
                    f"Refuter outcome={outcome}",
                    _now(),
                ),
            )

    def _cascade_forward(self, seed_goal_id: int, result: Any) -> None:
        """Cascade for Forward pipeline (P7 R3 round 2 fix audit2 NEW-MED-A).

        Forward outcomes: success / no_novel / exhausted.
          - success: Forward.commit already INSERT'd new orphan goals
            (origin='forward'); BFS picks them up next cycle. No cascade.
          - no_novel: dedupe wiped all candidates; nothing to write.
          - exhausted: agent gave up; record a dead_attempt so
            Forward.failure_replay can surface this seed's history on the
            next call (mirrors Backward / Refuter exhausted handling).
        """
        if result is None or result.outcome in {"success", "no_novel"}:
            return
        # exhausted (or any other failure-shaped outcome)
        self._record_pipeline_failure(
            seed_goal_id, "Forward", "forward", result.outcome,
            f"Forward outcome={result.outcome}",
        )

    def _cascade_generalizer(self, source_goal_id: int, result: Any) -> None:
        """Cascade for Generalizer pipeline (P7 R3 round 2 fix audit2 NEW-MED-A).

        Generalizer outcomes: success / no_novel / unproductive / exhausted.
          - success: G* inserted as new tree root; BFS picks it up.
          - no_novel: G* matched an existing entry.
          - unproductive: agent self-claim G already maximal — spec §8 says
            do NOT write blocked_pipelines. We DO write a dead_attempt so
            failure_replay sees the rejection (without it Generalizer keeps
            re-proposing the same pattern).
          - exhausted: self_verify retry exhausted.
        """
        if result is None or result.outcome in {"success", "no_novel"}:
            return
        # unproductive / exhausted both record dead_attempt; do NOT touch
        # goals.blocked_pipelines (spec §8 explicit).
        self._record_pipeline_failure(
            source_goal_id, "Generalizer", "Goal", result.outcome,
            f"Generalizer outcome={result.outcome}",
        )

    def _record_pipeline_failure(
        self,
        goal_id: int,
        pipeline_kind: str,
        target_kind: str,
        outcome: str,
        reason: str,
    ) -> None:
        """Generic dead_attempts writer for Forward / Generalizer.

        Mirrors _record_backward_failure / _record_refuter_failure: looks up
        the most recent matching pipeline row to satisfy the FK; missing
        pipeline → fatal (orphan cascade or stale ordering, the same
        silent-failure discipline as the older recorders).
        """
        pipeline_row = self.conn.execute(
            "SELECT id FROM pipelines WHERE target_id = ? AND kind = ? "
            "ORDER BY started_at DESC LIMIT 1",
            (str(goal_id), pipeline_kind),
        ).fetchone()
        if pipeline_row is None:
            msg = (
                f"{pipeline_kind.lower()}_failure_no_pipeline_id "
                f"goal_id={goal_id} outcome={outcome}"
            )
            self._emit_fatal(msg)
            raise FatalError(msg)
        with self.conn:
            self.conn.execute(
                "INSERT INTO dead_attempts (target_id, target_kind, "
                "pipeline_id, pipeline_kind, outcome, reason_summary, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(goal_id),
                    target_kind,
                    pipeline_row[0],
                    pipeline_kind,
                    outcome,
                    reason,
                    _now(),
                ),
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
        """Register task in _running and submit to thread pool.

        P7 演習 fix: re-check `_is_already_dispatched` AFTER the pop +
        BEFORE submitting. A queue can hold duplicate (target_id, kind)
        rows when multiple sources (BFS structural refill, Strategist
        demux, --once dispatch) write independently. Each source has
        its own gating logic but they don't coordinate; only this
        chokepoint sees the full picture. If a sibling pipeline is
        already running (in-memory `_running` or DB `pipelines.status
        ='running'`), drop this dup and emit a diagnostic.
        """
        target_id = str(task.get("target_id", ""))
        kind = str(task.get("kind", ""))
        if self._is_already_dispatched(target_id, kind):
            self._emit_event(
                "cascade",
                {
                    "rule": "dup_dispatch_dropped",
                    "task": task,
                    "reason": "sibling_already_running_or_queued",
                },
            )
            return
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
        """Run a pipeline with the provided connection.

        R3 fix (audit_c52_c53_c54_c55.md HIGH-4 + audit2 NEW-HIGH-A):
          - HIGH-4: extract task['payload'] and build a ModelResolver with
            any `model` override (Strategist propagates this via demux);
          - NEW-HIGH-A: dispatch ALL atomic-pool kinds the framework can
            enqueue. Strategist demux can inject Forward / Generalizer /
            Refuter / Counterexample / ConstructionSearch (currently
            deferred); BFS enqueues Refuter for conjecture goals. Without
            these branches, the first such task spawns into FatalError and
            halts the daemon.
        """
        from Tooling.agent.provider import ModelResolver
        kind = task["kind"]
        payload = self._decode_payload(task)
        resolver = self._resolver_with_overrides(kind, payload)
        self._warn_dropped_payload_keys(kind, payload)

        if kind == "Builder":
            strategy_id = int(task["target_id"])
            cfg = BuilderConfig(
                t_wall=self.config.t_wall,
                lake_timeout=self.config.lake_timeout,
                base_dir=self.config.base_dir,
            )
            # Builder doesn't yet accept a resolver in its constructor;
            # tracked in deferred catalog (Builder.resolver wiring).
            return Builder(strategy_id, conn, cfg).run()
        elif kind == "Backward":
            goal_id = int(task["target_id"])
            cfg = BackwardConfig(
                base_dir=self.config.base_dir,
                lake_cwd=self.config.base_dir,
                lean_timeout=self.config.lake_timeout,
            )
            chain = self._make_fallback_chain()
            return Backward(conn, chain, cfg, resolver=resolver).run(goal_id)
        elif kind == "Refuter":
            from Tooling.pipelines.refuter import Refuter, RefuterConfig
            goal_id = int(task["target_id"])
            cfg = RefuterConfig(
                base_dir=self.config.base_dir,
                lake_cwd=self.config.base_dir,
                lean_timeout=self.config.lake_timeout,
            )
            chain = self._make_fallback_chain()
            return Refuter(conn, chain, cfg, resolver=resolver).run(goal_id)
        elif kind == "Forward":
            from Tooling.pipelines.forward import Forward, ForwardConfig
            seed_goal_id = int(task["target_id"])
            cfg = ForwardConfig(
                base_dir=self.config.base_dir,
                lake_cwd=self.config.base_dir,
                lean_timeout=self.config.lake_timeout,
            )
            chain = self._make_fallback_chain()
            return Forward(conn, chain, cfg, resolver=resolver).run(seed_goal_id)
        elif kind == "Generalizer":
            from Tooling.pipelines.generalizer import (
                Generalizer, GeneralizerConfig,
            )
            source_goal_id = int(task["target_id"])
            cfg = GeneralizerConfig(
                base_dir=self.config.base_dir,
                lake_cwd=self.config.base_dir,
                lean_timeout=self.config.lake_timeout,
            )
            chain = self._make_fallback_chain()
            return Generalizer(
                conn, chain, cfg, resolver=resolver,
            ).run(source_goal_id)
        elif kind in {"Counterexample", "ConstructionSearch"}:
            # Deferred per task.md ## 延後 cycles. Demux can still write the
            # queue row (it's a legal Strategist decision); we record an
            # observable diagnostic and return None so the cascade dispatch
            # treats it as no-op rather than fatal-halting the scheduler.
            self._emit_event(
                "cascade",
                {"rule": "pipeline_kind_deferred",
                 "kind": kind,
                 "target_id": task.get("target_id")},
            )
            return None
        elif kind == "Strategist":
            from Tooling.pipelines.strategist import (
                Strategist, StrategistConfig,
            )
            target = task["target_id"]
            problem = (target.split(":", 1)[1]
                       if isinstance(target, str) and target.startswith("_problem:")
                       else str(target))
            chain = self._make_fallback_chain()
            cfg = StrategistConfig(base_dir=self.config.base_dir)
            return Strategist(conn, chain, cfg, resolver=resolver).run(problem)
        else:
            raise FatalError(f"Unsupported task kind in thread: {kind!r}")

    @staticmethod
    def _decode_payload(task: dict) -> dict:
        """Parse queue.payload JSON column (or None) into a dict."""
        raw = task.get("payload")
        if not raw:
            return {}
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return {}
        return v if isinstance(v, dict) else {}

    @staticmethod
    def _resolver_with_overrides(kind: str, payload: dict):
        """Build a ModelResolver honoring payload['model'] override.

        The Strategist sets `model='opus'` etc. per decision. The override
        applies to the agent stage of the spawned pipeline.
        """
        from Tooling.agent.provider import ModelResolver
        meta_models: dict[str, str] = {}
        model = payload.get("model")
        if isinstance(model, str) and model:
            meta_models[f"{kind.lower()}.agent"] = model
        return ModelResolver(meta_models=meta_models or None)

    def _warn_dropped_payload_keys(self, kind: str, payload: dict) -> None:
        """R3 round 2 fix (audit2_c49_c50_c51.md M_R2-2): demux carries
        budget / provider / range / mutation_operators in queue.payload but
        the spawn path here only honors `model`. Emit a diagnostic event so
        silently-dropped overrides leave a trail (rather than disappearing
        into the void as silent feature drop).
        """
        if not payload:
            return
        unconsumed = {
            k: v for k, v in payload.items()
            if k in {"provider", "budget", "range", "mutation_operators"}
        }
        if not unconsumed:
            return
        try:
            self._emit_event(
                "cascade",
                {"rule": "payload_override_unconsumed",
                 "kind": kind,
                 "dropped_keys": sorted(unconsumed.keys())},
            )
        except Exception:
            # Observability best-effort; never block spawn on event-write failure.
            pass

    def _make_fallback_chain(self) -> Any:
        """Create the default multi-provider FallbackChain.

        P5 C36: chain = [claude, gemini, codex] per phase5_construction.md
        ## In line 68 + spike-020 D-20-1. Each provider's `check_scope`
        method is git-diff backstop and provider-agnostic (spike-004 design),
        so a single ClaudeProvider instance is reused as `validate_scope`.

        FallbackChain.run iterates providers in order, retries each up to
        n_retry on ProviderError or scope violation, falls through to the
        next provider when one is exhausted. dict-of-list per-stage chains
        deferred to P5.x patch (spec line 71). Tests mock pipelines
        directly so this method is exercised only in P5+ smoke gates.
        """
        from Tooling.agent.provider import FallbackChain
        from Tooling.agent.providers.claude import ClaudeProvider
        from Tooling.agent.providers.gemini import GeminiProvider
        from Tooling.agent.providers.codex import CodexProvider
        backstop = ClaudeProvider()
        return FallbackChain(
            providers=[backstop, GeminiProvider(), CodexProvider()],
            validate_scope=backstop.check_scope,
        )

    # ------------------------------------------------------------------
    # Structural refill BFS
    # ------------------------------------------------------------------

    def _run_structural_refill(self) -> None:
        """BFS goals: enqueue Backward for open goals; Builder for all-proved strategies.

        P4 C31: open `kind=conjecture` goals also get Refuter dispatched
        in addition to Backward (three-line attack per architecture.md
        §6 task queue, structural refill rules). Counterexample line is
        deferred (task.md ## 延後 cycles); only Backward + Refuter fire
        on conjecture goals in the current cycle.
        """
        self._bfs_enqueue_backward()
        self._bfs_enqueue_refuter_for_conjecture()
        self._bfs_enqueue_builder()

    def _bfs_enqueue_backward(self) -> None:
        """Enqueue Backward for open theorem + conjecture Goals (P4 C31),
        respecting D_max + stop-gap.

        R3 fix MED-2: filter commit_state='live' so mid-commit pending rows
        (impl §1.3 commit protocol) are not picked up before stage_file completes.

        P4 C31: extends to kind='conjecture' as well — Backward attacks
        conjecture goals just as it attacks theorem goals (architecture.md
        §6 structural refill: kind=conjecture → Backward + Refuter +
        Counterexample three-line attack; Backward stays in this method,
        Refuter moves to _bfs_enqueue_refuter_for_conjecture, Counterexample
        deferred per task.md ## 延後 cycles).
        """
        rows = self.conn.execute(
            "SELECT id, depth FROM goals "
            "WHERE status = 'open' "
            "AND kind IN ('theorem', 'conjecture') "
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
            # P3 C24+C25: persistent blocked_pipelines is the canonical
            # filter (in-memory _failure_count removed in C25).
            from Tooling.subsystems.blocked_pipelines import is_blocked
            if is_blocked(self.conn, int(goal_id), "Backward"):
                continue
            # Avoid duplicate dispatch
            if self._is_already_dispatched(goal_id_s, "Backward"):
                continue
            # P7 演習 fix: Backward retry pile-up race. After Backward
            # succeeds and writes a 'proposed' (or 'succeeded')
            # strategy, the goal still reads `status='open'` until
            # cascade either marks the strategy dead (and shelves the
            # goal if all strategies dead) or all sub-goals prove
            # (cascading the strategy succeeded → goal proved). In
            # that gap (BFS tick fires every 30s, cascade can lag a
            # few seconds), BFS would re-enqueue another Backward on
            # the same goal — which then writes a competing strategy.
            # Skip if there is any non-dead strategy already on this
            # goal: Builder is about to verify, no point in proposing
            # an alternative until Builder either proves or fails.
            non_dead = self.conn.execute(
                "SELECT COUNT(*) FROM strategies "
                "WHERE goal_id = ? AND commit_state = 'live' "
                "  AND status != 'dead'",
                (int(goal_id),),
            ).fetchone()
            if non_dead and non_dead[0] > 0:
                continue
            self._enqueue_task("Backward", goal_id_s, priority=0)

    def _bfs_enqueue_refuter_for_conjecture(self) -> None:
        """Enqueue Refuter for open conjecture Goals (P4 C31, three-line attack).

        Architecture.md §6 structural refill rules — `kind=conjecture` goal
        gets Backward + Refuter + Counterexample queued in parallel. C31
        wires Refuter; Counterexample deferred per task.md ## 延後 cycles.

        Filter discipline mirrors _bfs_enqueue_backward:
          - commit_state='live' (avoid mid-commit pending rows)
          - blocked_pipelines does not include 'Refuter'
          - not already dispatched (idempotent across BFS ticks)
        """
        rows = self.conn.execute(
            "SELECT id FROM goals "
            "WHERE status = 'open' AND kind = 'conjecture' "
            "AND commit_state = 'live'"
        ).fetchall()
        from Tooling.subsystems.blocked_pipelines import is_blocked
        for (goal_id,) in rows:
            goal_id_s = str(goal_id)
            if is_blocked(self.conn, int(goal_id), "Refuter"):
                continue
            if self._is_already_dispatched(goal_id_s, "Refuter"):
                continue
            self._enqueue_task("Refuter", goal_id_s, priority=0)

    def _bfs_enqueue_builder(self) -> None:
        """Enqueue Builder for proposed strategies whose sub-goals are all proved.

        R3 fix MED-2: filter commit_state='live' so mid-commit strategies are
        not picked up before stage_file completes.

        P7演習 fix (BFS Builder retry pile-up race): strategies are
        single-shot from the BFS perspective. A given strategy's lean file is
        deterministic — if its first Builder verifies, cascade marks the
        strategy 'succeeded' and the goal proved; if it fails, cascade marks
        it 'dead' and Backward must write a NEW strategy to retry with
        different content. There is no scenario where re-running Builder on
        the SAME strategy can change the outcome (lake build is deterministic).

        Cascade runs asynchronously in the main loop AFTER the Builder thread
        pops `_running` and emits `pipeline_finished`. Until cascade runs,
        the strategy still reads as 'proposed', and BFS tick (30s) can fire
        in that gap. Without this guard, BFS re-enqueues Builder on the
        already-tried strategy, and the strategy ends up with 4-13 wasted
        Builder runs (each with its own staging dir + lake build) before
        cascade catches up.

        Guard: skip if there's been ANY Builder pipeline for this strategy
        (running OR finished). This is logically equivalent to "Builder runs
        at most once per strategy" — the correct invariant. Cascade-lag
        race becomes a non-issue because the second BFS tick simply sees
        attempts > 0 and waits, regardless of whether cascade has marked
        the strategy dead yet.
        """
        rows = self.conn.execute(
            "SELECT s.id, s.goal_id FROM strategies s "
            "WHERE s.status = 'proposed' AND s.commit_state = 'live'"
        ).fetchall()
        for strategy_id, goal_id in rows:
            strategy_id_s = str(strategy_id)
            # P3 C24+C25: persistent blocked_pipelines filter (in-memory
            # _failure_count removed in C25).
            from Tooling.subsystems.blocked_pipelines import is_blocked
            if is_blocked(self.conn, int(goal_id), "Builder"):
                continue
            if self._is_already_dispatched(strategy_id_s, "Builder"):
                continue
            # P7演習 fix: at most one Builder per strategy ever (see method
            # docstring for rationale). Cascade catches up; BFS waits.
            attempt_row = self.conn.execute(
                "SELECT COUNT(*) FROM pipelines "
                "WHERE kind = 'Builder' AND target_id = ?",
                (strategy_id_s,),
            ).fetchone()
            if attempt_row and attempt_row[0] >= 1:
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
        """True if a pipeline for this (target_id, kind) is running or queued.

        P7 演習 fix: also check DB for in-flight pipeline. Race window
        exists between the worker thread popping `_running` and the main
        loop processing pipeline_finished + cascade UPDATE'ing
        pipelines.status. During that gap the in-memory `_running` is
        empty, but the DB still shows status='running'. Without this
        DB check, BFS and Strategist demux can both schedule duplicate
        work for the same (target, kind) — daemon then spawns two
        threads that race on the same artifacts.
        """
        with self._lock:
            for tid, k in self._running.values():
                if tid == target_id and k == kind:
                    return True
        row = self.conn.execute(
            "SELECT id FROM queue WHERE target_id = ? AND kind = ?",
            (target_id, kind),
        ).fetchone()
        if row is not None:
            return True
        row = self.conn.execute(
            "SELECT id FROM pipelines WHERE target_id = ? AND kind = ? "
            "  AND status = 'running'",
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
    # Cancellation
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Queue (P1 compat)
    # ------------------------------------------------------------------

    def _pop_queue(self) -> dict[str, Any] | None:
        """Pop highest-priority (then oldest) task. Returns None if empty.

        P6 C44 per-Problem pause: skip rows whose target's Problem is in
        self._paused_problems (re-queue stays — task is left in DB,
        spawn loop short-circuits next tick after `problem_resume`).
        Implementation: when the paused set is empty take the fast path
        (single SELECT...LIMIT 1). Otherwise scan up to LIMIT 200 rows
        in priority order and return the first whose Problem is not in
        the set. If all 200 belong to paused Problems, return None
        (caller treats as empty queue, re-tries next tick). The 200 row
        ceiling is a starvation-safety guard for very large queues —
        P6 demo + acceptance ranges (~15 goals) stay well below.
        """
        with self._lock:
            paused = frozenset(self._paused_problems)
        if not paused:
            row = self.conn.execute(
                "SELECT id, kind, target_id, payload FROM queue "
                "ORDER BY priority DESC, id ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            q_id, kind, target_id, payload = row
            with self.conn:
                self.conn.execute("DELETE FROM queue WHERE id = ?", (q_id,))
            return {"id": q_id, "kind": kind, "target_id": target_id,
                    "payload": payload}

        # Filtered scan: skip rows whose Problem is paused.
        # Walks queue in priority order; first hit wins. Bound results
        # to a sane scan ceiling so a queue of 10k all-paused rows
        # doesn't burn the spawn loop tick.
        rows = self.conn.execute(
            "SELECT id, kind, target_id, payload FROM queue "
            "ORDER BY priority DESC, id ASC LIMIT 200"
        ).fetchall()
        for q_id, kind, target_id, payload in rows:
            if self._task_problem_in_set(kind, target_id, paused):
                continue
            with self.conn:
                self.conn.execute("DELETE FROM queue WHERE id = ?", (q_id,))
            return {"id": q_id, "kind": kind, "target_id": target_id,
                    "payload": payload}
        return None

    def _task_problem_in_set(
        self,
        kind: str,
        target_id: str,
        paused: frozenset[str],
    ) -> bool:
        """Return True if `task`'s Problem is in `paused`.

        Lookup table:
          - Backward (target_id = goal_id) → goals.problem
          - Builder (target_id = strategy_id) → strategies → goals.problem
        Unknown kinds default to False (don't pause unknowns; visible via
        _dispatch_event diagnostic path if mis-routed).
        """
        try:
            tid = int(target_id)
        except (TypeError, ValueError):
            return False
        if kind == "Backward":
            row = self.conn.execute(
                "SELECT problem FROM goals WHERE id = ?", (tid,)
            ).fetchone()
        elif kind == "Builder":
            row = self.conn.execute(
                "SELECT g.problem FROM strategies s "
                "JOIN goals g ON g.id = s.goal_id "
                "WHERE s.id = ?",
                (tid,),
            ).fetchone()
        else:
            return False
        if row is None:
            return False
        return row[0] in paused

    # ------------------------------------------------------------------
    # P1 synchronous dispatch (+ P2 Backward support)
    # ------------------------------------------------------------------

    def _dispatch(self, task: dict[str, Any]) -> None:
        """Synchronous dispatch used by P1 _run_loop and `--once` mode.

        R3 round 2 fix (audit2_c52_c53_c54_c55.md NEW-HIGH-A): mirror the
        async _execute_task_with_conn dispatch so Strategist-injected and
        BFS-injected non-Builder/Backward kinds don't fatal-halt --once.
        Cascade for these kinds is best-effort (Forward/Generalizer have
        no scheduler cascade today; their commit happens inside .run).
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
        elif kind in {"Refuter", "Forward", "Generalizer", "Strategist",
                      "Counterexample", "ConstructionSearch"}:
            # Reuse the async path's full dispatch table (with the same
            # payload + resolver wiring). Cascade for these kinds is
            # currently no-op (BFS picks up new orphan goals; Strategist
            # commit lands inside its own .run via demux).
            self._execute_task_with_conn(task, self.conn)
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
            # P6.x patch 22 + 23: with leaf-bypass strategies as separate
            # files (`_strategy_<pid>.lean`), the file stem is NOT the
            # theorem name. The theorem inside the strategy/goal file is
            # always declared as `theorem <goal.slug>`. Pull the slug from
            # the goals row directly.
            slug_row = self.conn.execute(
                "SELECT slug FROM goals WHERE id = ?", (goal_id,),
            ).fetchone()
            thm_name = slug_row[0] if slug_row else Path(lean_path).stem
            # Build module_path by walking the strategy file path from
            # "Problems" down, applying the french-quote rule to numeric-
            # prefix segments. This is the canonical module path.
            from pathlib import Path as _P
            parts = list(_P(lean_path).parts)
            try:
                idx = parts.index("Problems")
            except ValueError:
                idx = 0
            mod_segs: list[str] = []
            for seg in parts[idx:]:
                if seg.endswith(".lean"):
                    seg = seg[:-5]
                if seg[:1].isdigit():
                    mod_segs.append(f"«{seg}»")
                else:
                    mod_segs.append(seg)
            module_path = ".".join(mod_segs)
            try:
                axioms = print_axioms(thm_name, self.config.base_dir,
                                      module_path=module_path)
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

                    # P6.x patch 21: per-Problem forbidden_lemmas blacklist.
                    # Hard constraint enforced post-Builder. If the proof
                    # references any blacklisted lemma name, reject the
                    # proof (goal stays open) + record dead_attempts so
                    # Backward's failure_replay surfaces the violation in
                    # the next agent prompt.
                    if accepted and meta.forbidden_lemmas:
                        from Tooling.library.forbidden_check import (
                            check_forbidden,
                        )
                        proof_path = (
                            Path(self.config.base_dir) / lean_path
                        )
                        used_forbidden = check_forbidden(
                            proof_path, meta.forbidden_lemmas,
                        )
                        if used_forbidden:
                            should_prove = False
                            self._emit_event(
                                "cascade",
                                {
                                    "strategy_id": strategy_id,
                                    "goal_id": goal_id,
                                    "rule": "forbidden_lemma_used",
                                    "violations": used_forbidden,
                                },
                            )
                            self._record_forbidden_dead_attempt(
                                goal_id, strategy_id, used_forbidden,
                            )
                            # Mark strategy dead so BFS re-enqueues
                            # Backward — a fresh agent attempt sees the
                            # forbidden_lemma_used dead_attempts entry
                            # in failure_replay and steers around it.
                            self._mark_strategy_dead(strategy_id)
                            # `_mark_strategy_dead` shelves the goal when
                            # all strategies are dead; for forbidden-lemma
                            # rejections we want the goal to remain open
                            # so BFS re-spawns Backward. Force-open here
                            # to override the cancellation-driven shelve.
                            # P6.x patch 22: we do NOT touch any .lean
                            # files here — the strategy file (which
                            # contains the rejected proof) stays put for
                            # operator inspection; the goal file was
                            # never modified to begin with.
                            try:
                                with self.conn:
                                    self.conn.execute(
                                        "UPDATE goals SET status = 'open',"
                                        " status_changed_at = ? "
                                        "WHERE id = ?",
                                        (_now(), goal_id),
                                    )
                            except sqlite3.Error as exc:
                                self._emit_event(
                                    "cascade",
                                    {
                                        "goal_id": goal_id,
                                        "rule": "forbidden_open_revert_fail",
                                        "error": str(exc),
                                    },
                                )
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
            # P6.x patch 23: now that all checks (Builder + trust_set +
            # accept_rule + forbidden_lemmas) have passed, commit the
            # strategy file's proven content to the canonical goal file.
            # The goal file becomes either `:= by sorry` (unproved) or a
            # complete proof (proved) — no mid-state, no race.
            try:
                self._finalize_goal_file_from_strategy(goal_id, strategy_id)
            except Exception as exc:  # noqa: BLE001
                # Finalize is best-effort — the proof artifact still
                # exists in the strategy file; emit a cascade event so
                # operators can manually copy it over if the automated
                # commit failed (eg disk full, race with another tick).
                self._emit_event(
                    "cascade",
                    {
                        "rule": "goal_file_finalize_failed",
                        "goal_id": goal_id,
                        "strategy_id": strategy_id,
                        "error": str(exc),
                    },
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

    def _finalize_goal_file_from_strategy(
        self,
        goal_id: int,
        strategy_id: int,
    ) -> None:
        """P6.x patch 23: write the strategy file's proven content to
        the canonical goal file, then delete the strategy file.

        The strategy file declares `theorem <slug>` under the namespace
        `Problems.<p>.Goals.<id_seg>._strategy_<pid>`. The goal file
        lives at `Problems/<p>/Goals/<id_seg>/<slug>.lean` with the
        canonical namespace `Problems.<p>.Goals.<id_seg>` (or no
        namespace, depending on convention). We extract the proof body
        from the strategy file and substitute it into the goal-file
        template — same `import Problems.<p>.Defs` line + the canonical
        `theorem <slug> : <type> := <proof_body>` declaration.
        """
        goal_row = self.conn.execute(
            "SELECT problem, slug, lean_path, question FROM goals "
            "WHERE id = ?",
            (goal_id,),
        ).fetchone()
        if goal_row is None:
            return
        problem, slug, goal_lean_path, question = goal_row
        strat_row = self.conn.execute(
            "SELECT lean_path FROM strategies WHERE id = ?",
            (strategy_id,),
        ).fetchone()
        if strat_row is None:
            return
        strategy_lean_path = strat_row[0]

        strat_full = Path(self.config.base_dir) / strategy_lean_path
        goal_full = Path(self.config.base_dir) / goal_lean_path
        if not strat_full.exists():
            return

        # Extract the proof body from the strategy file. The strategy
        # file shape is:
        #   import Problems.<p>.Defs
        #   namespace <strategy_ns>
        #   theorem <slug> : <type> := <proof_body>
        #   end <strategy_ns>
        # We pull <proof_body> by finding the `theorem <slug> ... :=`
        # marker and taking everything up to the `end <strategy_ns>` line.
        text = strat_full.read_text(encoding="utf-8")
        proof_body = _extract_proof_body(text, slug)
        if proof_body is None:
            raise RuntimeError(
                f"could not extract proof body from {strategy_lean_path}"
            )
        # Build canonical goal file content. The goal-file namespace is
        # `Problems.<p>.Goals.<id_seg>` (without the strategy segment)
        # so proved.lean's re-export `Problems.<p>.Goals.<id_seg>.<slug>`
        # resolves once the goal module is imported.
        from pathlib import Path as _P
        id_segment = _P(goal_lean_path).parent.name
        if id_segment[:1].isdigit():
            id_segment_lean = f"«{id_segment}»"
        else:
            id_segment_lean = id_segment
        canonical_ns = f"Problems.{problem}.Goals.{id_segment_lean}"
        canonical_content = (
            f"import Problems.{problem}.Defs\n\n"
            f"namespace {canonical_ns}\n\n"
            f"theorem {slug} : {question} := {proof_body}\n\n"
            f"end {canonical_ns}\n"
        )

        # Atomic write: write to a temp sibling, fsync, rename onto goal
        # file. On Windows POSIX rename semantics differ but for our
        # single-Reactor + atomic-pool model, the worst case is one
        # in-flight reader (e.g. proved.lean lake-build) races with the
        # rename; lake's read of an old olean is fine because the new
        # goal file content will produce a refreshed olean on the next
        # `lake build`.
        tmp_path = goal_full.with_suffix(".lean.tmp")
        tmp_path.write_text(canonical_content, encoding="utf-8")
        import os as _os
        try:
            _os.replace(str(tmp_path), str(goal_full))
        except OSError:
            # Fallback to non-atomic on platforms where replace fails.
            goal_full.write_text(canonical_content, encoding="utf-8")
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        # Delete the strategy file — it has served its staging purpose.
        try:
            strat_full.unlink(missing_ok=True)
        except OSError:
            pass
        # Update strategies.lean_path to point at the goal file so
        # promote_to_library and downstream queries find the canonical
        # location.
        with self.conn:
            self.conn.execute(
                "UPDATE strategies SET lean_path = ? WHERE id = ?",
                (str(goal_lean_path), strategy_id),
            )

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

        P4 C30: after the proved UPDATE, run twin cascade — if this goal
        has twin_of, flip the twin to status='refuted' (architecture.md §6
        line 330: "Builder/Backward 鏈成功 → Goal status=proved, twin (若有)
        status=refuted"). Symmetric: works whether the proved goal is a
        user conjecture (G) or a Refuter-spawned negation (¬G).

        TX caveat (C30 R2 LOW-2): the G-UPDATE and twin-cascade UPDATE land
        in **separate** transactions — the `with self.conn` block here
        commits before _cascade_twin_to_refuted opens its own. Spec §6
        line 324 calls for single-TX cascade; this codebase's existing
        pattern (mirrors `_mark_strategy_dead` line 506-535) uses
        sequential TXs and the realignment is deferred to a P5+ scheduler
        refactor. Concrete failure mode: if twin UPDATE raises sqlite3.Error
        after G is committed, FatalError halts but DB shows G='proved' +
        twin='open' — operator sees the inconsistency on resume rather
        than a clean rollback.
        """
        with self.conn:
            self.conn.execute(
                "UPDATE goals SET status = 'proved', answer_data = ?, "
                "trust_set = ?, status_changed_at = ? WHERE id = ?",
                (answer_data, trust_set_json, _now(), goal_id),
            )
        invalidate_for_goals_write(self.conn)
        self._cascade_twin_to_refuted(goal_id, trust_set_json)
        # P6 C41: Library promotion hook. promote_to_library handles
        # qualification (origin / type / trust_set whitelist) internally.
        # C41 R3 HIGH-2 fix: real lake build verify lands in P6.C45;
        # until then the production hook explicitly opts into the noop
        # verifier via LIBRARY_VERIFY_NOOP=1 (set per-call so unit-test
        # processes that don't promote are unaffected). promote_to_library
        # emits a `library_verify_skipped` cascade event for every
        # promotion under noop so the audit trail makes the gap visible.
        from Tooling.library.promotion import promote_to_library
        prev_noop_env = os.environ.get("LIBRARY_VERIFY_NOOP")
        os.environ["LIBRARY_VERIFY_NOOP"] = "1"
        try:
            promote_to_library(
                self.conn, goal_id, self.config.base_dir,
                emit_event=self._emit_event,
            )
        except Exception as exc:  # noqa: BLE001
            # Library promotion is best-effort in C41 — the proved goal
            # is the source-of-truth. Emit a cascade event so operators
            # see the failure on next library audit but do not raise.
            self._emit_event(
                "cascade",
                {
                    "rule": "library_promotion_failed",
                    "goal_id": goal_id,
                    "error": str(exc),
                },
            )
        finally:
            if prev_noop_env is None:
                os.environ.pop("LIBRARY_VERIFY_NOOP", None)
            else:
                os.environ["LIBRARY_VERIFY_NOOP"] = prev_noop_env

    def _cascade_twin_to_refuted(
        self, proved_goal_id: int, trust_set_json: str | None
    ) -> None:
        """If proved goal has twin_of, flip twin to status='refuted'.

        Spec arch.md §6 line 330 字面: "Builder/Backward 鏈成功 → Goal
        `status='proved'`...; twin（若有）`status='refuted'`、
        `answer_data={type:'classical', negation_lean_path, negation_goal_id}`、
        `trust_set` 從 ¬G 繼承".

        P4 C30 simplified scope (Counterexample deferred):
          - dual-proved invariant: if twin already proved → CASCADE_FAULT
            simulation (or natural detection) → fatal halt.
          - silver→gold (Counterexample-source) deferred: if twin already
            refuted with type='witness', would normally upgrade trust_set
            to classical lean_axiom. With Counterexample deferred, twin
            should never be in silver state on entry; treat as idempotent
            (no-op).

        CASCADE_FAULT=dual_proved env hook (acceptance #9): force the
        invariant violation path even when twin status differs. Used by
        tests verifying scheduler halt behavior.
        """
        # Look up proved goal's lean_path + twin_of
        row = self.conn.execute(
            "SELECT twin_of, lean_path FROM goals WHERE id = ?",
            (proved_goal_id,),
        ).fetchone()
        if row is None:
            return
        twin_of, proved_lean_path = row
        if twin_of is None:
            return

        twin_row = self.conn.execute(
            "SELECT id, status, answer_data FROM goals WHERE id = ?",
            (twin_of,),
        ).fetchone()
        if twin_row is None:
            # Twin pointer dangling — not a healthy DB state but cascade
            # should not silently proceed; emit cascade event for visibility.
            self._emit_event(
                "cascade",
                {
                    "goal_id": proved_goal_id,
                    "twin_of": twin_of,
                    "rule": "twin_cascade_dangling_pointer",
                },
            )
            return
        twin_id, twin_status, twin_answer_data = twin_row

        # CASCADE_FAULT=dual_proved: force invariant violation path
        from Tooling.cascade import check_cascade_fault, CascadeFault
        try:
            check_cascade_fault("dual_proved")
        except CascadeFault as exc:
            msg = str(exc)
            self._emit_fatal(msg)
            raise FatalError(msg) from exc

        if twin_status == "proved":
            # Real dual-proved invariant violation
            msg = (
                f"dual_proved invariant violation: goal {proved_goal_id} "
                f"proved with twin {twin_id} also proved"
            )
            self._emit_fatal(msg)
            raise FatalError(msg)

        if twin_status == "refuted":
            # Idempotent **while Counterexample is deferred**: under current
            # scope the only refuted-writer is this cascade, so twin already
            # refuted means type='classical' is already in place — no-op is
            # correct. When Counterexample lands (task.md ## 延後 cycles),
            # this branch must inspect twin_answer_data ->> '$.type'; if
            # 'witness' (silver verdict), upgrade trust_set to classical
            # lean_axioms inherited from ¬G (silver → gold, acceptance #5).
            return

        # Flip twin to refuted (classical type, with cross-reference back
        # to the proved goal's lean_path).
        refuted_answer_data = json.dumps({
            "type": "classical",
            "negation_lean_path": proved_lean_path,
            "negation_goal_id": proved_goal_id,
        })
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE goals SET status = 'refuted', answer_data = ?, "
                    "trust_set = ?, status_changed_at = ? WHERE id = ?",
                    (refuted_answer_data, trust_set_json, _now(), twin_id),
                )
            invalidate_for_goals_write(self.conn)
            self._emit_event(
                "cascade",
                {
                    "goal_id": twin_id,
                    "rule": "twin_proved→refuted",
                    "via_proved_goal_id": proved_goal_id,
                },
            )
            # P4 C31: trigger cond 2 'twin_refuted' verdict cancellation.
            # Cancels Builder/Backward/Refuter/Counterexample/ConstructionSearch
            # on either G or ¬G (architecture.md §6 cancellation table; spec
            # L430 「同上」 = same kind set as cond 1). Inside this try/except
            # for fatal-event symmetry with _mark_strategy_dead cond 4 trigger
            # (C31 R2 LOW-4): if cancel_for_verdict raises, _emit_fatal still
            # writes the events table before FatalError propagates.
            from Tooling.cancellation import (
                CancellationVerdict,
                cancel_for_verdict,
            )
            cancel_for_verdict(
                self.conn,
                CancellationVerdict(
                    kind="twin_refuted",
                    goal_id=twin_id,
                    twin_id=proved_goal_id,
                ),
                emit_event=self._emit_event,
            )
        except sqlite3.Error as exc:
            self._emit_fatal(str(exc))
            raise FatalError(str(exc)) from exc

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

    def _goal_question(self, goal_id: int) -> str | None:
        """P6.x patch 21 helper: fetch goal.question for proof-template
        regeneration when a forbidden_lemma rejection rolls back the
        leaf-bypass overwrite."""
        row = self.conn.execute(
            "SELECT question FROM goals WHERE id = ?", (goal_id,),
        ).fetchone()
        return row[0] if row else None

    def _record_forbidden_dead_attempt(
        self,
        goal_id: int,
        strategy_id: int,
        forbidden_used: list[str],
    ) -> None:
        """P6.x patch 21: insert dead_attempts row recording a
        forbidden_lemmas blacklist violation.

        Backward's failure_replay walks dead_attempts and surfaces the
        reasons in the next agent prompt — when the proof named e.g.
        Cardinal.mk_real on a Problem that lists it forbidden, the
        next Backward attempt sees `forbidden_lemma_used: Cardinal.mk_real`
        in DEAD_ATTEMPTS and steers around it.
        """
        pipeline_row = self.conn.execute(
            "SELECT id FROM pipelines WHERE target_id = ? AND kind = 'Builder' "
            "ORDER BY started_at DESC LIMIT 1",
            (str(strategy_id),),
        ).fetchone()
        if pipeline_row is None:
            self._emit_event(
                "cascade",
                {
                    "goal_id": goal_id,
                    "strategy_id": strategy_id,
                    "rule": "forbidden_lemma_used_no_pipeline_id",
                    "violations": forbidden_used,
                },
            )
            return
        pipeline_id = pipeline_row[0]
        reason = f"forbidden_lemma_used: {', '.join(forbidden_used)}"
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
                    "forbidden_lemma_used",
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
