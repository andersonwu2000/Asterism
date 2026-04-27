"""Reactor (P1 skeleton): queue pop → Builder spawn → cascade.

Startup: connect DB → init_schema (idempotent) → recover_scan.
Main loop (P1, single-threaded, P=1):
  1. Pop one queue row (priority desc, id asc).
  2. Dispatch by kind (P1: Builder only).
  3. Builder.run() synchronously.
  4. Cascade rule: strategies.succeeded → goal proved + answer_data.
  5. Cascade SQL fail → emit fatal event + sys.exit(1).
  6. Queue empty → sys.exit(0).

--once and --daemon flags are P1-equivalent (both drain queue then exit).
P2+ will implement true daemon blocking on event_bus.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Tooling.commit import CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.pipelines.builder import Builder, BuilderConfig, BuilderResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FatalError(Exception):
    """Unrecoverable cascade SQL failure. Causes reactor to exit(1)."""


@dataclass
class ReactorConfig:
    t_wall: float = 30 * 60.0
    lake_timeout: float = 600.0
    base_dir: str = "."


class Reactor:
    def __init__(self, db_path: str | Path, config: ReactorConfig | None = None) -> None:
        self.db_path = Path(db_path)
        self.config = config or ReactorConfig()
        self.conn: Any = None

    def startup(self) -> None:
        """Connect DB, apply schema (idempotent), run recover_scan."""
        self.conn = connect(self.db_path)
        init_schema(self.conn)
        CommitWriter(self.conn).recover_scan()

    def run(self) -> None:
        """Entry point: startup then drain queue."""
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
    # Queue
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
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, task: dict[str, Any]) -> None:
        """Dispatch task to pipeline. P1 handles Builder only."""
        if task["kind"] == "Builder":
            strategy_id = int(task["target_id"])
            cfg = BuilderConfig(
                t_wall=self.config.t_wall,
                lake_timeout=self.config.lake_timeout,
                base_dir=self.config.base_dir,
            )
            result = Builder(strategy_id, self.conn, cfg).run()
            self._cascade(strategy_id, result)
        else:
            msg = f"Unsupported task kind: {task['kind']!r}"
            self._emit_fatal(msg)
            raise FatalError(msg)

    # ------------------------------------------------------------------
    # Cascade
    # ------------------------------------------------------------------

    def _cascade(self, strategy_id: int, result: BuilderResult) -> None:
        """Single cascade rule: strategies.succeeded → goal proved + answer_data.

        P1 trigger uses BuilderResult.outcome=='proved' rather than re-querying
        strategies.status=='succeeded' (phase1_skeleton.md ## Scope ## In line 27
        is DB-driven). Functionally equivalent in P1: Builder is the only
        producer and only emits BuilderResult after CommitWriter has UPDATE'd
        strategies.status='succeeded' in the same step (builder._commit_success).

        P2+ revisit: when Backward / Refuter / other pipelines may modify
        strategies.status independently, switch this trigger to a DB read of
        strategies.status to stay aligned with phase doc 字面 ground-truth.
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

        try:
            self._update_goal_proved(goal_id, answer_data)
            self._emit_event(
                "cascade",
                {
                    "strategy_id": strategy_id,
                    "goal_id": goal_id,
                    "rule": "succeeded→proved",
                },
            )
        except sqlite3.Error as exc:
            # phase1_skeleton.md ## Scope ## In: cascade SQL fail
            # (unique constraint / FK / json format) → fatal halt. P1 cascade
            # has no json.loads path; sqlite3.Error covers the realistic set.
            # Programming bugs (TypeError / AttributeError) intentionally
            # propagate uncaught for fast debugging in P1.
            self._emit_fatal(str(exc))
            raise FatalError(str(exc)) from exc

    def _update_goal_proved(self, goal_id: int, answer_data: str) -> None:
        """Write proved status to goals row (separated for testability)."""
        with self.conn:
            self.conn.execute(
                "UPDATE goals SET status = 'proved', answer_data = ? WHERE id = ?",
                (answer_data, goal_id),
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
