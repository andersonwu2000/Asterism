"""Unit tests for Tooling.scheduler.Reactor.

Existing coverage (20 tests):
  1. startup: recover_scan triggered; DB schema created
  2. queue pop: task returned + row deleted; None when empty; priority/FIFO order
  3. dispatch: Builder spawned with correct strategy_id; unknown kind raises FatalError
  4. cascade proved: goal status=proved, answer_data set, cascade event emitted
  5. cascade exhausted: goal status unchanged, no cascade event
  6. fatal halt: cascade SQL error → fatal event emitted + FatalError raised
  7. run loop: FatalError → sys.exit(1); empty queue → sys.exit(0)

New coverage (34 tests):
  8.  Backward dispatch
  9.  Daemon mode: run_daemon exits on shutdown, creates pool
  10. Event dispatch: 4-event kind dispatch
  11. Atomic pool: cap, pause, _running tracking
  12. Structural refill BFS: open goals, D_max, leaf strategy, all-proved, no-dup
  13. N_block_after_failures stop-gap
  14. Cascade V2: strategy dead → shelved; not-all-dead; backward failure count
  15. Trust set + accept rule
  16. Cancellation step 2
  17. Control signal: pause / resume / shutdown
  18. Hook placeholder no-ops (step 1 / step 5)

lake / Builder / Backward fully mocked; no real subprocess.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from Tooling.commit import CommitWriter
from Tooling.db.connect import init_schema
from Tooling.pipelines.backward import BackwardResult
from Tooling.pipelines.builder import BuilderResult
from Tooling.scheduler import FatalError, Reactor, ReactorConfig


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    yield conn
    conn.close()


def _make_reactor(db: sqlite3.Connection, tmp_path: Path) -> Reactor:
    """Build a Reactor with conn already injected (bypasses startup)."""
    reactor = Reactor(
        str(tmp_path / "test.db"),
        ReactorConfig(base_dir=str(tmp_path)),
    )
    reactor.conn = db
    return reactor


def _make_rows(
    conn: sqlite3.Connection,
    strategy_lean: Path,
    goal_lean: Path,
    *,
    slug: str = "add_zero",
    problem: str = "example",
) -> tuple[int, int]:
    """Insert goal + strategy rows; return (goal_id, strategy_id)."""
    now = "2026-01-01T00:00:00+00:00"
    with conn:
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (problem, slug, str(goal_lean), "root", "theorem",
             "open", "live", now, now),
        )
        goal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO strategies "
            "(goal_id, lean_path, status, commit_state, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (goal_id, str(strategy_lean), "proposed", "live", now),
        )
        strategy_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return goal_id, strategy_id


def _enqueue(
    conn: sqlite3.Connection,
    kind: str,
    target_id: str,
    priority: int = 0,
) -> int:
    now = "2026-01-01T00:00:00+00:00"
    with conn:
        conn.execute(
            "INSERT INTO queue (kind, target_id, priority, created_at) VALUES (?, ?, ?, ?)",
            (kind, target_id, priority, now),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_open_goal(
    conn: sqlite3.Connection,
    tmp_path: Path,
    *,
    slug: str = "g",
    depth: int = 0,
    problem: str = "ex",
) -> int:
    """Insert a minimal open theorem goal; return goal_id."""
    lean = tmp_path / f"{slug}.lean"
    lean.write_text("placeholder", "utf-8")
    now = "2026-01-01T00:00:00+00:00"
    with conn:
        conn.execute(
            "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
            "commit_state, depth, created_at, updated_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (problem, slug, str(lean), "root", "theorem", "open", "live",
             depth, now, now),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_strategy(
    conn: sqlite3.Connection,
    tmp_path: Path,
    goal_id: int,
    *,
    slug: str = "s",
    status: str = "proposed",
) -> int:
    """Insert a strategy row; return strategy_id."""
    lean = tmp_path / f"{slug}.lean"
    lean.write_text("placeholder", "utf-8")
    now = "2026-01-01T00:00:00+00:00"
    with conn:
        conn.execute(
            "INSERT INTO strategies (goal_id, lean_path, status, commit_state, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (goal_id, str(lean), status, "live", now),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_proved_goal(
    conn: sqlite3.Connection,
    tmp_path: Path,
    *,
    slug: str = "pg",
) -> int:
    """Insert a proved sub-goal; return goal_id."""
    lean = tmp_path / f"{slug}.lean"
    lean.write_text("placeholder", "utf-8")
    now = "2026-01-01T00:00:00+00:00"
    with conn:
        conn.execute(
            "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
            "commit_state, depth, created_at, updated_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ex", slug, str(lean), "backward", "theorem", "proved", "live",
             1, now, now),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _link_subgoal(
    conn: sqlite3.Connection, strategy_id: int, subgoal_id: int, position: int = 0
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
            "VALUES (?, ?, ?)",
            (strategy_id, subgoal_id, position),
        )


def _insert_pipeline_row(
    conn: sqlite3.Connection,
    *,
    pid: str = "pipe-test",
    kind: str = "Backward",
    target_id: str = "0",
    target_kind: str = "Goal",
    started_at: str = "2026-01-01T00:00:00+00:00",
) -> str:
    """C24 R3 MED-3: pre-insert a pipelines row so _record_backward_failure
    can satisfy the dead_attempts.pipeline_id FK without raising FatalError."""
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, started_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (pid, kind, "atomic", target_id, target_kind, "succeeded", started_at),
        )
    return pid


# ---------------------------------------------------------------------------
# 1. startup
# ---------------------------------------------------------------------------


class TestStartup:
    def test_recover_scan_called(self, tmp_path: Path) -> None:
        """startup() must invoke CommitWriter.recover_scan exactly once."""
        db_path = tmp_path / "test.db"
        reactor = Reactor(str(db_path))
        with patch.object(CommitWriter, "recover_scan") as mock_scan:
            reactor.startup()
        mock_scan.assert_called_once()

    def test_startup_creates_schema(self, tmp_path: Path) -> None:
        """startup() creates DB file and applies all expected tables."""
        db_path = tmp_path / "test.db"
        reactor = Reactor(str(db_path))
        reactor.startup()
        assert db_path.exists()
        tables = {
            t[0]
            for t in reactor.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for expected in ("goals", "strategies", "queue", "events"):
            assert expected in tables


# ---------------------------------------------------------------------------
# 2. queue pop
# ---------------------------------------------------------------------------


class TestQueuePop:
    def test_pop_returns_task(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        _enqueue(db, "Builder", "42")
        reactor = _make_reactor(db, tmp_path)
        task = reactor._pop_queue()
        assert task is not None
        assert task["kind"] == "Builder"
        assert task["target_id"] == "42"

    def test_pop_deletes_row(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        _enqueue(db, "Builder", "1")
        reactor = _make_reactor(db, tmp_path)
        reactor._pop_queue()
        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0

    def test_pop_none_when_empty(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        reactor = _make_reactor(db, tmp_path)
        assert reactor._pop_queue() is None

    def test_pop_priority_highest_first(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        _enqueue(db, "Builder", "low", priority=0)
        _enqueue(db, "Builder", "high", priority=10)
        reactor = _make_reactor(db, tmp_path)
        task = reactor._pop_queue()
        assert task is not None
        assert task["target_id"] == "high"

    def test_pop_fifo_within_same_priority(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        _enqueue(db, "Builder", "first", priority=5)
        _enqueue(db, "Builder", "second", priority=5)
        reactor = _make_reactor(db, tmp_path)
        task = reactor._pop_queue()
        assert task is not None
        assert task["target_id"] == "first"


# ---------------------------------------------------------------------------
# 3. dispatch (Builder + updated unknown-kind test)
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_builder_spawned_with_correct_strategy_id(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_dispatch instantiates Builder(strategy_id, conn, cfg) and calls .run()."""
        reactor = _make_reactor(db, tmp_path)
        task = {"id": 1, "kind": "Builder", "target_id": "99", "payload": None}

        with patch("Tooling.scheduler.Builder") as MockBuilder:
            MockBuilder.return_value.run.return_value = BuilderResult(outcome="exhausted")
            reactor._dispatch(task)

        MockBuilder.assert_called_once_with(99, db, ANY)
        MockBuilder.return_value.run.assert_called_once()

    def test_dispatch_unknown_kind_raises_fatal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Unknown kind: FatalError raised AND fatal event emitted (R2 #3)."""
        reactor = _make_reactor(db, tmp_path)
        task = {"id": 1, "kind": "Refuter", "target_id": "1", "payload": None}
        with pytest.raises(FatalError):
            reactor._dispatch(task)

        event = db.execute(
            "SELECT kind, payload FROM events WHERE kind = 'fatal'"
        ).fetchone()
        assert event is not None
        payload = json.loads(event[1])
        assert "Refuter" in payload["error"]


# ---------------------------------------------------------------------------
# 3b. Backward dispatch (P2 new)
# ---------------------------------------------------------------------------


class TestBackwardDispatch:
    def test_backward_spawned_with_correct_goal_id(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_dispatch with Backward calls Backward(conn, chain, cfg).run(goal_id)."""
        reactor = _make_reactor(db, tmp_path)
        # C24 R3 MED-3: cascade now requires Backward pipeline row for FK.
        _insert_pipeline_row(db, pid="pipe-99", target_id="99")
        task = {"id": 1, "kind": "Backward", "target_id": "99", "payload": None}

        with patch("Tooling.scheduler.Backward") as MockBackward, \
             patch.object(reactor, "_make_fallback_chain", return_value=MagicMock()):
            MockBackward.return_value.run.return_value = BackwardResult(outcome="exhausted")
            reactor._dispatch(task)

        MockBackward.return_value.run.assert_called_once_with(99)

    def test_backward_exhausted_records_dead_attempt(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25: Backward exhausted in _dispatch → dead_attempts row written
        (was: _inc_failure_count on the removed in-memory dict)."""
        reactor = _make_reactor(db, tmp_path)
        _insert_pipeline_row(db, pid="pipe-77", target_id="77")
        task = {"id": 1, "kind": "Backward", "target_id": "77", "payload": None}

        with patch("Tooling.scheduler.Backward") as MockBackward, \
             patch.object(reactor, "_make_fallback_chain", return_value=MagicMock()):
            MockBackward.return_value.run.return_value = BackwardResult(outcome="exhausted")
            reactor._dispatch(task)

        rows = db.execute(
            "SELECT outcome FROM dead_attempts WHERE target_id = '77' "
            "AND pipeline_kind = 'Backward'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "exhausted"


# ---------------------------------------------------------------------------
# 4. cascade proved
# ---------------------------------------------------------------------------


class TestCascadeProved:
    def test_goal_status_set_proved(
        self, db: sqlite3.Connection, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # PRINT_AXIOMS_MOCK=none: trust_set=[] (trivial proof) → cascade proceeds.
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "none")
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._cascade(
            strategy_id, BuilderResult(outcome="proved")
        )

        row = db.execute("SELECT status FROM goals WHERE id = ?", (goal_id,)).fetchone()
        assert row[0] == "proved"

    def test_answer_data_written(
        self, db: sqlite3.Connection, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "none")
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._cascade(
            strategy_id, BuilderResult(outcome="proved")
        )

        raw = db.execute("SELECT answer_data FROM goals WHERE id = ?", (goal_id,)).fetchone()[0]
        answer = json.loads(raw)
        assert answer["type"] == "classical"
        assert answer["lean_path"] == str(strategy_lean)

    def test_cascade_event_emitted(
        self, db: sqlite3.Connection, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "none")
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._cascade(
            strategy_id, BuilderResult(outcome="proved")
        )

        event = db.execute(
            "SELECT kind FROM events WHERE kind = 'cascade'"
        ).fetchone()
        assert event is not None


# ---------------------------------------------------------------------------
# 5. cascade: exhausted — no side effects
# ---------------------------------------------------------------------------


class TestCascadeExhausted:
    def test_goal_status_unchanged(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._cascade(
            strategy_id, BuilderResult(outcome="exhausted")
        )

        row = db.execute("SELECT status FROM goals WHERE id = ?", (goal_id,)).fetchone()
        assert row[0] == "open"

    def test_no_events_emitted(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._cascade(
            strategy_id, BuilderResult(outcome="exhausted")
        )

        count = db.execute("SELECT count(*) FROM events").fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# 6. fatal halt: cascade SQL error
# ---------------------------------------------------------------------------


class TestFatalHalt:
    def test_cascade_sql_error_emits_fatal_event(
        self, db: sqlite3.Connection, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SQL error in _update_goal_proved → fatal event written to events table."""
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "none")
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        reactor = _make_reactor(db, tmp_path)
        with patch.object(
            reactor,
            "_update_goal_proved",
            side_effect=sqlite3.IntegrityError("UNIQUE constraint failed"),
        ):
            with pytest.raises(FatalError):
                reactor._cascade(strategy_id, BuilderResult(outcome="proved"))

        event = db.execute(
            "SELECT kind, payload FROM events WHERE kind = 'fatal'"
        ).fetchone()
        assert event is not None
        payload = json.loads(event[1])
        assert "UNIQUE constraint failed" in payload["error"]

    def test_cascade_sql_error_raises_fatal_error(
        self, db: sqlite3.Connection, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SQL error in cascade → FatalError is raised (not swallowed)."""
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "none")
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        reactor = _make_reactor(db, tmp_path)
        with patch.object(
            reactor,
            "_update_goal_proved",
            side_effect=sqlite3.IntegrityError("injected"),
        ):
            with pytest.raises(FatalError):
                reactor._cascade(strategy_id, BuilderResult(outcome="proved"))

    def test_run_loop_exits_nonzero_on_fatal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_run_loop catches FatalError from dispatch → sys.exit(1)."""
        reactor = _make_reactor(db, tmp_path)
        _enqueue(db, "Builder", "1")

        with patch.object(reactor, "_dispatch", side_effect=FatalError("injected")):
            with pytest.raises(SystemExit) as exc_info:
                reactor._run_loop()

        assert exc_info.value.code == 1

    def test_cascade_fatal_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Acceptance #11 end-to-end (R2 #4):
        queue → _pop_queue → _dispatch (Builder mock proved) → _cascade
        (real SQL fail) → fatal event in DB + SystemExit(1) + DB 現場保留.
        """
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "none")
        db_path = tmp_path / "test.db"

        # Pre-populate DB before reactor.startup() opens its own connection.
        setup_conn = sqlite3.connect(str(db_path))
        setup_conn.execute("PRAGMA foreign_keys = ON")
        init_schema(setup_conn)
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(setup_conn, strategy_lean, goal_lean)
        _enqueue(setup_conn, "Builder", str(strategy_id))
        setup_conn.close()

        reactor = Reactor(str(db_path), ReactorConfig(base_dir=str(tmp_path)))

        with patch("Tooling.scheduler.Builder") as MockBuilder:
            MockBuilder.return_value.run.return_value = BuilderResult(outcome="proved")
            reactor.startup()
            with patch.object(
                reactor,
                "_update_goal_proved",
                side_effect=sqlite3.IntegrityError("UNIQUE constraint failed"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    reactor._run_loop()

        assert exc_info.value.code == 1

        event = reactor.conn.execute(
            "SELECT kind, payload FROM events WHERE kind = 'fatal'"
        ).fetchone()
        assert event is not None
        assert "UNIQUE constraint failed" in json.loads(event[1])["error"]

        # DB 現場保留: strategy + goal rows still present.
        assert reactor.conn.execute(
            "SELECT id FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone() is not None
        assert reactor.conn.execute(
            "SELECT id FROM goals WHERE id = ?", (goal_id,)
        ).fetchone() is not None


# ---------------------------------------------------------------------------
# 7. queue empty exit
# ---------------------------------------------------------------------------


class TestQueueEmptyExit:
    def test_run_loop_exits_zero_on_empty(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_run_loop with empty queue → sys.exit(0)."""
        reactor = _make_reactor(db, tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            reactor._run_loop()
        assert exc_info.value.code == 0

    def test_run_exits_zero_integration(self, tmp_path: Path) -> None:
        """run() on a fresh empty DB → startup + empty queue → sys.exit(0)."""
        db_path = tmp_path / "test.db"
        reactor = Reactor(str(db_path), ReactorConfig(base_dir=str(tmp_path)))
        with pytest.raises(SystemExit) as exc_info:
            reactor.run()
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# 8. Daemon mode (P2)
# ---------------------------------------------------------------------------


class TestDaemonMode:
    def test_run_daemon_exits_on_shutdown(self, tmp_path: Path) -> None:
        """run_daemon exits cleanly when shutdown control_signal is received."""
        db_path = tmp_path / "test.db"
        reactor = Reactor(str(db_path), ReactorConfig(tick_interval=10.0))

        def _send_shutdown() -> None:
            time.sleep(0.05)
            reactor._event_queue.put(("control_signal", "shutdown"))

        t = threading.Thread(target=_send_shutdown)
        t.start()
        reactor.run_daemon()
        t.join(timeout=2.0)
        assert reactor._shutdown_flag

    def test_run_daemon_creates_thread_pool(self, tmp_path: Path) -> None:
        """run_daemon creates a ThreadPoolExecutor before the event loop."""
        db_path = tmp_path / "test.db"
        reactor = Reactor(str(db_path), ReactorConfig(tick_interval=10.0))

        def _shutdown_soon() -> None:
            time.sleep(0.05)
            reactor._event_queue.put(("control_signal", "shutdown"))

        t = threading.Thread(target=_shutdown_soon)
        t.start()
        reactor.run_daemon()
        t.join(timeout=2.0)
        assert reactor._pool is not None


# ---------------------------------------------------------------------------
# 9. Event dispatch (P2)
# ---------------------------------------------------------------------------


class TestEventDispatch:
    def test_pipeline_finished_routes_to_handler(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """pipeline_finished event → _handle_pipeline_finished called."""
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": "1"}
        result = BuilderResult(outcome="exhausted")

        with patch.object(reactor, "_handle_pipeline_finished") as mock_h:
            reactor._dispatch_event(("pipeline_finished", task, result))

        mock_h.assert_called_once_with(task, result)

    def test_control_signal_routes_to_handler(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """control_signal event → _handle_control_signal called with action."""
        reactor = _make_reactor(db, tmp_path)

        with patch.object(reactor, "_handle_control_signal") as mock_h:
            reactor._dispatch_event(("control_signal", "pause"))

        mock_h.assert_called_once_with("pause")

    def test_fatal_event_routes_to_handler(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """fatal event → _handle_fatal_event called."""
        reactor = _make_reactor(db, tmp_path)

        with patch.object(reactor, "_handle_fatal_event") as mock_h:
            reactor._dispatch_event(("fatal", "something went wrong"))

        mock_h.assert_called_once_with("something went wrong")

    def test_task_checkpoint_silently_discarded(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """task_checkpoint: P5 handler; P2 discards without error or event."""
        reactor = _make_reactor(db, tmp_path)
        # Should not raise
        reactor._dispatch_event(("task_checkpoint", {"data": "ignored"}))
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0

    def test_pipeline_finished_calls_all_6_steps(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_handle_pipeline_finished invokes all 6 step methods in order."""
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": "1"}
        result = BuilderResult(outcome="exhausted")
        call_order: list[str] = []

        def _record(name: str):
            def _inner(*a, **kw):
                call_order.append(name)
            return _inner

        with patch.object(reactor, "_run_step1_stale_filter", side_effect=_record("s1")), \
             patch.object(reactor, "_run_step2_cancellation", side_effect=_record("s2")), \
             patch.object(reactor, "_run_step3_cascade", side_effect=_record("s3")), \
             patch.object(reactor, "_run_step4_trust_set", side_effect=_record("s4")), \
             patch.object(reactor, "_run_step5_strategist_trigger", side_effect=_record("s5")), \
             patch.object(reactor, "_run_step6_spawn", side_effect=_record("s6")):
            reactor._handle_pipeline_finished(task, result)

        assert call_order == ["s1", "s2", "s3", "s4", "s5", "s6"]


# ---------------------------------------------------------------------------
# 10. Atomic pool
# ---------------------------------------------------------------------------


class TestAtomicPool:
    def test_submit_task_adds_to_running(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_submit_task registers (target_id, kind) in _running before thread starts."""
        reactor = _make_reactor(db, tmp_path)
        reactor._pool = MagicMock()
        task = {"kind": "Builder", "target_id": "42", "payload": None}

        reactor._submit_task(task)

        with reactor._lock:
            entries = list(reactor._running.values())
        assert any(tid == "42" and k == "Builder" for tid, k in entries)

    def test_try_spawn_respects_pool_cap(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_try_spawn_from_queue does not pop when pool is at capacity."""
        reactor = _make_reactor(db, tmp_path)
        reactor.config = ReactorConfig(pool_size=1)
        reactor._pool = MagicMock()
        reactor._running["fake"] = ("1", "Builder")  # pool at cap
        _enqueue(db, "Builder", "2")

        with patch.object(reactor, "_submit_task") as mock_submit:
            reactor._try_spawn_from_queue()

        mock_submit.assert_not_called()
        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 1

    def test_try_spawn_skips_when_paused(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_try_spawn_from_queue does not pop tasks when reactor is paused."""
        reactor = _make_reactor(db, tmp_path)
        reactor._pool = MagicMock()
        reactor._paused = True
        _enqueue(db, "Builder", "1")

        with patch.object(reactor, "_submit_task") as mock_submit:
            reactor._try_spawn_from_queue()

        mock_submit.assert_not_called()
        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# 11. Structural refill BFS
# ---------------------------------------------------------------------------


class TestStructuralRefill:
    def test_bfs_enqueues_backward_for_open_goal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Open theorem goal → Backward enqueued in queue table."""
        goal_id = _insert_open_goal(db, tmp_path, slug="thm1")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_backward()

        row = db.execute(
            "SELECT kind, target_id FROM queue WHERE kind='Backward'"
        ).fetchone()
        assert row is not None
        assert row[1] == str(goal_id)

    def test_bfs_shelves_goal_at_d_max(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Goal at depth >= D_max → shelved, NOT enqueued."""
        goal_id = _insert_open_goal(db, tmp_path, slug="deep", depth=12)
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_backward()

        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status == "shelved"
        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0

    def test_bfs_enqueues_builder_for_leaf_strategy(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Strategy with no sub-goals (leaf) → Builder enqueued."""
        goal_id = _insert_open_goal(db, tmp_path, slug="leaf_g")
        strat_id = _insert_strategy(db, tmp_path, goal_id, slug="leaf_s")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_builder()

        row = db.execute(
            "SELECT kind, target_id FROM queue WHERE kind='Builder'"
        ).fetchone()
        assert row is not None
        assert row[1] == str(strat_id)

    def test_bfs_enqueues_builder_for_all_proved_subgoals(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Strategy with all sub-goals proved → Builder enqueued (cascade upward)."""
        goal_id = _insert_open_goal(db, tmp_path, slug="parent_g")
        strat_id = _insert_strategy(db, tmp_path, goal_id, slug="parent_s")
        sg_id = _insert_proved_goal(db, tmp_path, slug="proved_sg")
        _link_subgoal(db, strat_id, sg_id, position=0)

        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_builder()

        row = db.execute(
            "SELECT kind, target_id FROM queue WHERE kind='Builder'"
        ).fetchone()
        assert row is not None
        assert row[1] == str(strat_id)

    def test_bfs_no_dup_when_already_queued(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """BFS does not double-enqueue a goal already in the queue."""
        goal_id = _insert_open_goal(db, tmp_path, slug="dup_g")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_backward()  # first pass
        reactor._bfs_enqueue_backward()  # second pass — must not add again

        count = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Backward' AND target_id=?",
            (str(goal_id),),
        ).fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# 12. N_block_after_failures stop-gap
# ---------------------------------------------------------------------------


class TestFailureCountStopGap:
    def test_bfs_skips_backward_after_n_failures(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25: BFS skips goals whose persistent blocked_pipelines contains 'Backward'."""
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        goal_id = _insert_open_goal(db, tmp_path, slug="blocked")
        reactor = _make_reactor(db, tmp_path)
        block_pipeline(db, goal_id, "Backward")

        reactor._bfs_enqueue_backward()

        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0

    def test_bfs_skips_builder_after_persistent_block(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25: BFS skips strategies whose parent goal has 'Builder' in blocked_pipelines."""
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        goal_id = _insert_open_goal(db, tmp_path, slug="bcap_g")
        _insert_strategy(db, tmp_path, goal_id, slug="bcap_s")
        reactor = _make_reactor(db, tmp_path)
        block_pipeline(db, goal_id, "Builder")

        reactor._bfs_enqueue_builder()

        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0

    def test_block_persists_across_reactor_instances(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25: persistent block survives scheduler restart (key advantage
        over the removed in-memory _failure_count)."""
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        goal_id = _insert_open_goal(db, tmp_path, slug="reset_g")
        r1 = _make_reactor(db, tmp_path)
        block_pipeline(db, goal_id, "Backward")
        r1._bfs_enqueue_backward()
        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0

        # New reactor: block remains because it's in the DB
        r2 = _make_reactor(db, tmp_path)
        r2._bfs_enqueue_backward()
        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 13. Cascade V2: strategy dead / goal shelved
# ---------------------------------------------------------------------------


class TestCascadeV2:
    def test_mark_strategy_dead_updates_status(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_mark_strategy_dead sets strategy.status = 'dead'."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("placeholder", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._mark_strategy_dead(strategy_id)

        status = db.execute(
            "SELECT status FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()[0]
        assert status == "dead"

    def test_all_strategies_dead_shelves_goal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When all strategies are dead, goal.status → shelved + cascade event."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("placeholder", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._mark_strategy_dead(strategy_id)

        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status == "shelved"

        event = db.execute(
            "SELECT payload FROM events WHERE kind='cascade'"
        ).fetchone()
        assert event is not None
        assert "all_strategies_dead" in json.loads(event[0]).get("rule", "")

    def test_not_all_dead_leaves_goal_open(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """With two strategies, killing one still leaves goal open."""
        now = "2026-01-01T00:00:00+00:00"
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        s1_lean = tmp_path / "s1.lean"
        s1_lean.write_text("placeholder", "utf-8")
        s2_lean = tmp_path / "s2.lean"
        s2_lean.write_text("placeholder", "utf-8")

        with db:
            db.execute(
                "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
                "commit_state, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("ex", "two_s", str(goal_lean), "root", "theorem", "open", "live", now, now),
            )
            goal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO strategies (goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (goal_id, str(s1_lean), "proposed", "live", now),
            )
            s1_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO strategies (goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (goal_id, str(s2_lean), "proposed", "live", now),
            )

        _make_reactor(db, tmp_path)._mark_strategy_dead(s1_id)

        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status == "open"

    def test_cascade_backward_records_dead_attempt_on_exhausted(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25: cascade writes dead_attempts on non-success outcomes (was:
        _inc_failure_count on removed in-memory dict). success → no row."""
        reactor = _make_reactor(db, tmp_path)
        # C24 R3 MED-3: cascade now requires Backward pipeline row for FK.
        _insert_pipeline_row(db, pid="pipe-42", target_id="42")
        reactor._cascade_backward(42, BackwardResult(outcome="exhausted"))
        reactor._cascade_backward(42, BackwardResult(outcome="unproductive"))
        reactor._cascade_backward(42, BackwardResult(outcome="success"))

        rows = db.execute(
            "SELECT outcome FROM dead_attempts WHERE target_id = '42' "
            "AND pipeline_kind = 'Backward' ORDER BY id"
        ).fetchall()
        assert [r[0] for r in rows] == ["exhausted", "unproductive"]
        # success outcome does NOT write dead_attempts


# ---------------------------------------------------------------------------
# 14. Trust set + accept rule
# ---------------------------------------------------------------------------


class TestTrustSetAndAccept:
    def test_trust_set_written_when_print_axioms_succeeds(
        self,
        db: sqlite3.Connection,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """trust_set JSON written to goal when print_axioms returns axioms."""
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "propext,Classical.choice")
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        _make_reactor(db, tmp_path)._cascade(
            strategy_id, BuilderResult(outcome="proved")
        )

        raw = db.execute(
            "SELECT trust_set FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert raw is not None
        trust = json.loads(raw)
        names = {e["name"] for e in trust}
        assert "propext" in names
        assert "Classical.choice" in names

    def test_accept_rule_rejects_forbidden_axiom(
        self,
        db: sqlite3.Connection,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Accept rule reject: goal not proved + cascade event with rule='accept_rule_rejected'."""
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "Classical.choice")
        problems_dir = tmp_path / "Problems" / "example"
        problems_dir.mkdir(parents=True)
        (problems_dir / "META.md").write_text(
            "---\nproblem_name: example\naxioms:\n  - propext\n---\n",
            encoding="utf-8",
        )
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("placeholder", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        config = ReactorConfig(base_dir=str(tmp_path))
        reactor = Reactor(str(tmp_path / "test.db"), config)
        reactor.conn = db
        reactor._cascade(strategy_id, BuilderResult(outcome="proved"))

        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status != "proved"

        event = db.execute(
            "SELECT payload FROM events WHERE kind='cascade'"
        ).fetchone()
        assert event is not None
        assert json.loads(event[0]).get("rule") == "accept_rule_rejected"

    def test_trust_set_construction_failure_strict_is_fail_shut(
        self,
        db: sqlite3.Connection,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R3 fix MED-1: print_axioms failure on the P2 daemon path
        (strict_trust_set=True, reached via _cascade_builder) → fail-shut.

        Goal must NOT be marked proved. Cascade emits a
        'trust_set_construction_failed' event AND a pause control_signal
        so the daemon halts spawning new pipelines for human review.
        Silent fallback to `trust_set=None + still proved` was the
        silent-PASS pattern flagged by R2 audit.
        """
        monkeypatch.delenv("PRINT_AXIOMS_MOCK", raising=False)

        def _raise(*args, **kwargs):
            raise RuntimeError("print_axioms('t') exit 1: stderr='unknown'")

        monkeypatch.setattr("Tooling.scheduler.print_axioms", _raise)

        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        reactor = _make_reactor(db, tmp_path)
        # Daemon path enters via _cascade_builder which sets strict_trust_set=True
        reactor._cascade_builder(strategy_id, BuilderResult(outcome="proved"))

        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status != "proved"

        event = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade'"
        ).fetchone()
        assert event is not None
        assert json.loads(event[0]).get("rule") == "trust_set_construction_failed"

        events: list = []
        while not reactor._event_queue.empty():
            events.append(reactor._event_queue.get_nowait())
        assert ("control_signal", "pause") in events

    def test_trust_set_construction_failure_lenient_silent_fallback(
        self,
        db: sqlite3.Connection,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R3 fix MED-1: print_axioms failure on the P1 sync path
        (strict_trust_set=False, reached via _dispatch / _cascade direct)
        intentionally retains silent fallback for P1 acceptance compat.

        P1 acceptance suite (test_phase1_acceptance.py) runs `--once` mode
        with lake misconfigured; tests expect goals to still prove since P1
        had no accept-rule contract. We honor that path WITHOUT re-introducing
        silent-PASS in production (P2 daemon path is fail-shut, see test above).
        """
        monkeypatch.delenv("PRINT_AXIOMS_MOCK", raising=False)

        def _raise(*args, **kwargs):
            raise RuntimeError("print_axioms('t') exit 1: stderr='unknown'")

        monkeypatch.setattr("Tooling.scheduler.print_axioms", _raise)

        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # P1 sync path: _cascade with default strict_trust_set=False
        _make_reactor(db, tmp_path)._cascade(
            strategy_id, BuilderResult(outcome="proved")
        )

        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status == "proved"  # P1 compat: still proved
        trust_raw = db.execute(
            "SELECT trust_set FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert trust_raw is None  # trust_set null on lenient fallback


# ---------------------------------------------------------------------------
# 15. Step 2: cancellation
# ---------------------------------------------------------------------------


class TestCancellationStep2:
    def test_step2_cancel_called_on_proved(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Builder proved → _cancel_running_for_goal called with goal_id."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("placeholder", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": str(strategy_id)}

        with patch.object(reactor, "_cancel_running_for_goal") as mock_cancel:
            reactor._run_step2_cancellation(task, BuilderResult(outcome="proved"))

        mock_cancel.assert_called_once_with(str(goal_id))

    def test_step2_no_cancel_on_exhausted(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Builder exhausted → _cancel_running_for_goal NOT called."""
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": "1"}

        with patch.object(reactor, "_cancel_running_for_goal") as mock_cancel:
            reactor._run_step2_cancellation(task, BuilderResult(outcome="exhausted"))

        mock_cancel.assert_not_called()


# ---------------------------------------------------------------------------
# 16. Control signal: pause / resume / shutdown
# ---------------------------------------------------------------------------


class TestControlSignal:
    def test_pause_sets_paused_flag(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """control_signal pause → reactor._paused = True."""
        reactor = _make_reactor(db, tmp_path)
        assert not reactor._paused
        reactor._handle_control_signal("pause")
        assert reactor._paused

    def test_resume_clears_paused_flag(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """control_signal resume → reactor._paused = False."""
        reactor = _make_reactor(db, tmp_path)
        reactor._paused = True
        reactor._handle_control_signal("resume")
        assert not reactor._paused

    def test_shutdown_sets_shutdown_flag(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """control_signal shutdown → reactor._shutdown_flag = True."""
        reactor = _make_reactor(db, tmp_path)
        reactor._handle_control_signal("shutdown")
        assert reactor._shutdown_flag


# ---------------------------------------------------------------------------
# 17. Hook placeholder no-ops (step 1 / step 5)
# ---------------------------------------------------------------------------


class TestThreadFatalRouting:
    def test_thread_unknown_kind_emits_fatal_event_to_queue(
        self, tmp_path: Path
    ) -> None:
        """R3 HIGH-1: FatalError from _execute_task_with_conn → ('fatal', ...) on _event_queue.

        Without this routing the daemon never halts — _execute_task_with_conn
        raises FatalError for unsupported kinds, but R1 silently re-classified
        it as BuilderResult(exhausted) and only wrote a DB event row, which
        _handle_fatal_event never sees.
        """
        db_path = tmp_path / "test.db"
        reactor = Reactor(str(db_path), ReactorConfig(base_dir=str(tmp_path)))
        reactor.startup()
        task = {"id": 1, "kind": "Refuter", "target_id": "1", "payload": None}
        pid = "test-pid-1"
        reactor._running[pid] = (task["target_id"], task["kind"])

        # Run thread body directly (FatalError path)
        reactor._run_pipeline_thread(pid, task)

        events = []
        while not reactor._event_queue.empty():
            events.append(reactor._event_queue.get_nowait())

        fatal_events = [e for e in events if e[0] == "fatal"]
        assert len(fatal_events) >= 1
        assert "Refuter" in fatal_events[0][1]
        # FatalError path: pipeline_finished must NOT be emitted
        assert not any(e[0] == "pipeline_finished" for e in events)

    def test_thread_internal_exception_emits_fatal_and_pipeline_finished(
        self, tmp_path: Path
    ) -> None:
        """R3 HIGH-1: non-FatalError Exception → ('fatal', ...) + pipeline_finished with typed result."""
        db_path = tmp_path / "test.db"
        reactor = Reactor(str(db_path), ReactorConfig(base_dir=str(tmp_path)))
        reactor.startup()
        task = {"id": 1, "kind": "Backward", "target_id": "1", "payload": None}
        pid = "test-pid-2"
        reactor._running[pid] = (task["target_id"], task["kind"])

        with patch.object(
            reactor,
            "_execute_task_with_conn",
            side_effect=ValueError("boom"),
        ):
            reactor._run_pipeline_thread(pid, task)

        events = []
        while not reactor._event_queue.empty():
            events.append(reactor._event_queue.get_nowait())

        assert any(e[0] == "fatal" and "boom" in e[1] for e in events)
        # pipeline_finished should be emitted with typed BackwardResult
        finished = [e for e in events if e[0] == "pipeline_finished"]
        assert len(finished) == 1
        assert finished[0][2].outcome == "exhausted"
        assert isinstance(finished[0][2], BackwardResult)


class TestAcceptRuleReject:
    def test_accept_rule_reject_writes_dead_attempts_and_emits_pause(
        self,
        db: sqlite3.Connection,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R3 HIGH-2: accept rule reject → dead_attempts INSERT + pause control_signal.

        spec architecture.md line 480 + acceptance #7: rejected trust_set must
        leave dead_attempts row + emit pause for human review (not just an
        info-level cascade event).
        """
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "Classical.choice")
        problems_dir = tmp_path / "Problems" / "example"
        problems_dir.mkdir(parents=True)
        (problems_dir / "META.md").write_text(
            "---\nproblem_name: example\naxioms:\n  - propext\n---\n",
            encoding="utf-8",
        )
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("placeholder", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # Pre-insert a Builder pipeline row so dead_attempts.pipeline_id FK resolves.
        with db:
            db.execute(
                "INSERT INTO pipelines (id, kind, runtime, target_id, target_kind, "
                "status, started_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("pid-test-rej", "Builder", "atomic", str(strategy_id),
                 "Strategy", "running", "2026-01-01T00:00:00+00:00"),
            )

        config = ReactorConfig(base_dir=str(tmp_path))
        reactor = Reactor(str(tmp_path / "test.db"), config)
        reactor.conn = db
        reactor._cascade(strategy_id, BuilderResult(outcome="proved"))

        # Goal NOT proved
        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status != "proved"

        # dead_attempts row written with rejected axiom name in summary
        row = db.execute(
            "SELECT reason_summary, target_kind, pipeline_kind, outcome "
            "FROM dead_attempts WHERE target_id = ?",
            (str(goal_id),),
        ).fetchone()
        assert row is not None
        assert "Classical.choice" in row[0]
        assert row[1] == "Goal"
        assert row[2] == "Builder"
        assert row[3] == "trust_set_rejected"

        # pause control_signal emitted to in-memory queue
        events: list = []
        while not reactor._event_queue.empty():
            events.append(reactor._event_queue.get_nowait())
        assert ("control_signal", "pause") in events


class TestBFSCommitStateFilter:
    def test_bfs_skips_pending_commit_state_goal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """R3 MED-2: BFS Backward enqueue must filter commit_state='live'."""
        lean = tmp_path / "pend.lean"
        lean.write_text("placeholder", "utf-8")
        now = "2026-01-01T00:00:00+00:00"
        with db:
            db.execute(
                "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
                "commit_state, depth, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("ex", "pend_g", str(lean), "root", "theorem", "open", "pending",
                 0, now, now),
            )

        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_backward()

        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0

    def test_bfs_skips_pending_commit_state_strategy(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """R3 MED-2: BFS Builder enqueue must filter strategies.commit_state='live'."""
        goal_id = _insert_open_goal(db, tmp_path, slug="pend_g_for_strat")
        # Insert pending strategy (commit_state='pending')
        lean = tmp_path / "pend_s.lean"
        lean.write_text("placeholder", "utf-8")
        now = "2026-01-01T00:00:00+00:00"
        with db:
            db.execute(
                "INSERT INTO strategies (goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (goal_id, str(lean), "proposed", "pending", now),
            )

        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_builder()

        # No Builder enqueued for the pending strategy
        count = db.execute(
            "SELECT count(*) FROM queue WHERE kind = 'Builder'"
        ).fetchone()[0]
        assert count == 0


class TestHookPlaceholders:
    def test_step1_stale_filter_emits_event_for_orphan_target(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25: _run_step1_stale_filter detects strategy_id with no live row
        and emits a cascade event with rule='stale_filter'. Reserved hook
        for P4 cascade cancellation handling.
        """
        import json as _json
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": "9999"}  # no strategy 9999
        reactor._run_step1_stale_filter(task, BuilderResult(outcome="exhausted"))
        rows = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade'"
        ).fetchall()
        rules = [_json.loads(r[0]).get("rule") for r in rows]
        assert "stale_filter" in rules

    def test_step5_strategist_trigger_is_noop(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_run_step5_strategist_trigger does nothing; no exception raised."""
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": "1"}
        reactor._run_step5_strategist_trigger(task, BuilderResult(outcome="proved"))
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 19. C17 R3 — IPC poll + scheduler register/unregister fail-shut
# ---------------------------------------------------------------------------


class TestDbControlSignalPoll:
    """C17 R3 MED-2: IPC path tests for asterism stop → daemon."""

    def test_poll_picks_up_cli_control_signal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """events row {action,source=cli} → _event_queue gets ('control_signal', action)."""
        reactor = _make_reactor(db, tmp_path)
        reactor._last_seen_ctrl_id = 0
        with db:
            db.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                ("control_signal",
                 json.dumps({"action": "shutdown", "source": "cli"}),
                 "2026-01-01T00:00:00+00:00"),
            )
        reactor._poll_db_control_signals()
        assert reactor._event_queue.get_nowait() == ("control_signal", "shutdown")

    def test_poll_filters_non_cli_source(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """events row without source='cli' → not forwarded (avoids feedback loop)."""
        reactor = _make_reactor(db, tmp_path)
        reactor._last_seen_ctrl_id = 0
        with db:
            db.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                ("control_signal",
                 json.dumps({"action": "shutdown", "source": "internal"}),
                 "2026-01-01T00:00:00+00:00"),
            )
        reactor._poll_db_control_signals()
        assert reactor._event_queue.empty()

    def test_poll_skips_pre_startup_events(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """events row with id <= _last_seen_ctrl_id → skipped (don't process old signals)."""
        with db:
            db.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                ("control_signal",
                 json.dumps({"action": "shutdown", "source": "cli"}),
                 "2026-01-01T00:00:00+00:00"),
            )
            old_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        reactor = _make_reactor(db, tmp_path)
        reactor._last_seen_ctrl_id = old_id  # snapshot at startup excludes this row
        reactor._poll_db_control_signals()
        assert reactor._event_queue.empty()

    def test_poll_sql_error_emits_fatal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C17 R3 HIGH-2: sqlite3.Error during poll → ('fatal', ...) emitted, not silent.

        Without this, asterism stop signals can be silently dropped — user sees
        no feedback that daemon failed to receive.
        """
        reactor = _make_reactor(db, tmp_path)
        reactor._last_seen_ctrl_id = 0
        reactor.conn = MagicMock()
        reactor.conn.execute.side_effect = sqlite3.Error("simulated DB fail")
        reactor._poll_db_control_signals()
        kind, msg = reactor._event_queue.get_nowait()
        assert kind == "fatal"
        assert "control_signal poll" in msg


class TestSchedulerRegistration:
    """C17 R3 HIGH-3 + MED-1: register/unregister must not silent-swallow."""

    def test_register_sql_error_emits_fatal_and_raises(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C17 R3 HIGH-3: INSERT into schedulers fail → fatal + FatalError raised.

        Silent-swallow would let daemon run as zombie that asterism stop can't reach.
        """
        reactor = _make_reactor(db, tmp_path)
        reactor.conn = MagicMock()
        reactor.conn.__enter__ = MagicMock(return_value=reactor.conn)
        reactor.conn.__exit__ = MagicMock(return_value=False)
        reactor.conn.execute.side_effect = sqlite3.Error("simulated INSERT fail")
        with pytest.raises(FatalError):
            reactor._register_scheduler()
        kind, msg = reactor._event_queue.get_nowait()
        assert kind == "fatal"
        assert "_register_scheduler" in msg

    def test_unregister_sql_error_emits_fatal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C17 R3 MED-1: DELETE fail → fatal emitted (best-effort, no raise on shutdown)."""
        reactor = _make_reactor(db, tmp_path)
        reactor._scheduler_id = 999  # pretend registered
        reactor.conn = MagicMock()
        reactor.conn.__enter__ = MagicMock(return_value=reactor.conn)
        reactor.conn.__exit__ = MagicMock(return_value=False)
        reactor.conn.execute.side_effect = sqlite3.Error("simulated DELETE fail")
        reactor._unregister_scheduler()
        kind, msg = reactor._event_queue.get_nowait()
        assert kind == "fatal"
        assert "_unregister_scheduler" in msg
