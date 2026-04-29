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
    kind: str = "theorem",
) -> int:
    """Insert a minimal open goal (default kind=theorem); return goal_id."""
    lean = tmp_path / f"{slug}.lean"
    lean.write_text("placeholder", "utf-8")
    now = "2026-01-01T00:00:00+00:00"
    with conn:
        conn.execute(
            "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
            "commit_state, depth, created_at, updated_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (problem, slug, str(lean), "root", kind, "open", "live",
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
        """Unknown kind: FatalError raised AND fatal event emitted (R2 #3).

        Note (R3 round 2 audit2 NEW-HIGH-A fix): Refuter / Forward /
        Generalizer / Strategist are now supported in _dispatch. Use a
        truly bogus kind to exercise the FatalError path.
        """
        reactor = _make_reactor(db, tmp_path)
        task = {"id": 1, "kind": "Bogus", "target_id": "1", "payload": None}
        with pytest.raises(FatalError):
            reactor._dispatch(task)

        event = db.execute(
            "SELECT kind, payload FROM events WHERE kind = 'fatal'"
        ).fetchone()
        assert event is not None
        payload = json.loads(event[1])
        assert "Bogus" in payload["error"]


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

    def test_cascade_builder_mirrors_strategy_failure_to_goal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: Builder failures must surface as Goal-scoped
        dead_attempts so Backward.failure_replay sees them.

        Builder._record_dead_attempts writes target_kind='Strategy'.
        Backward.failure_replay queries target_kind='Goal'. Without the
        cascade mirror, retry Backward never learns what Builder tried +
        why it failed → tends to repeat the flawed approach.
        """
        from Tooling.pipelines.builder import BuilderResult

        goal_id = _insert_open_goal(db, tmp_path, slug="mirror_g")
        strat_id = _insert_strategy(db, tmp_path, goal_id, slug="mirror_s")
        # Insert prior Strategy-scoped Builder dead_attempts (what Builder
        # itself wrote during its run).
        db.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, outcome, "
            "started_at, finished_at) VALUES "
            "('pipe-mirror-1', 'Builder', 'atomic', ?, 'Strategy', 'failed', "
            "'exhausted', '2026-04-29T05:00:00+00:00', "
            "'2026-04-29T05:01:00+00:00')",
            (str(strat_id),),
        )
        db.execute(
            "INSERT INTO dead_attempts "
            "(target_id, target_kind, pipeline_id, pipeline_kind, "
            " outcome, reason_summary, ts) "
            "VALUES (?, 'Strategy', 'pipe-mirror-1', 'Builder', "
            " 'exhausted', 'tactic <inline-proof>: Tactic.unsolvedGoals', "
            " '2026-04-29T05:01:00+00:00')",
            (str(strat_id),),
        )
        db.commit()

        reactor = _make_reactor(db, tmp_path)
        reactor._cascade_builder(strat_id, BuilderResult(outcome="exhausted"))

        # Verify a NEW Goal-scoped dead_attempt now exists.
        rows = db.execute(
            "SELECT pipeline_kind, outcome, reason_summary FROM dead_attempts "
            "WHERE target_id = ? AND target_kind = 'Goal'",
            (str(goal_id),),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Builder"
        assert rows[0][1] == "exhausted"
        # Reason summary must mention both the strategy id (so Backward can
        # locate the offending attempt) and the underlying error kind.
        assert f"strategy {strat_id}" in rows[0][2]
        assert "unsolvedGoals" in rows[0][2]

    def test_mark_strategy_dead_renames_file_keeps_forensic(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: dead strategy file is renamed to .lean.attempted
        rather than deleted. The proof body that was tried + rejected by
        Builder remains on disk for human inspection — without this
        change, every dead-strategy attempt leaves no forensic record
        once cascade fires.
        """
        goal_id = _insert_open_goal(db, tmp_path, slug="forensic_g",
                                     problem="forensic_p")
        # Insert a strategy with a real on-disk file containing a fake proof.
        strat_dir = tmp_path / "Problems" / "forensic_p" / "Goals" / f"{goal_id}_forensic_g"
        strat_dir.mkdir(parents=True)
        strategy_lean_rel = (
            f"Problems/forensic_p/Goals/{goal_id}_forensic_g/_strategy_xyz.lean"
        )
        strategy_full = tmp_path / strategy_lean_rel
        strategy_full.write_text(
            "theorem forensic_g : True := by trivial\n",
            encoding="utf-8",
        )
        # Distinct goal lean_path so _mark_strategy_dead doesn't think
        # they are the same file (rename guard).
        goal_lean_rel = f"Problems/forensic_p/Goals/{goal_id}_forensic_g/forensic_g.lean"
        (tmp_path / goal_lean_rel).write_text(
            "theorem forensic_g : True := by sorry\n", encoding="utf-8",
        )
        db.execute(
            "UPDATE goals SET lean_path = ? WHERE id = ?",
            (goal_lean_rel, goal_id),
        )
        with db:
            db.execute(
                "INSERT INTO strategies "
                "(goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?, ?, 'proposed', 'live', ?)",
                (goal_id, strategy_lean_rel, "2026-01-01T00:00:00+00:00"),
            )
        strat_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        reactor = _make_reactor(db, tmp_path)
        reactor._mark_strategy_dead(strat_id)

        # Original file is gone (renamed away).
        assert not strategy_full.exists()
        # Renamed sibling preserves the proof body for forensic inspection.
        attempted = strategy_full.with_suffix(strategy_full.suffix + ".attempted")
        assert attempted.exists()
        body = attempted.read_text("utf-8")
        assert "by trivial" in body, (
            "renamed dead strategy must still contain the original proof body"
        )
        # Strategy row is now dead.
        status = db.execute(
            "SELECT status FROM strategies WHERE id = ?", (strat_id,),
        ).fetchone()[0]
        assert status == "dead"

    def test_dup_dispatch_dropped_at_submit_time(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: duplicate (target_id, kind) tasks may end up in
        queue from multiple sources (BFS, Strategist demux, --once).
        _submit_task must drop a task whose sibling pipeline is already
        running, otherwise daemon spawns two threads racing on the same
        artifacts.
        """
        # Pre-seed a 'running' Backward pipeline on goal 42.
        db.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, started_at) "
            "VALUES ('pipe-running-bw', 'Backward', 'atomic', '42', 'Goal', "
            "'running', ?)",
            ("2026-04-29T05:00:00+00:00",),
        )
        db.commit()

        reactor = _make_reactor(db, tmp_path)
        # Claim that the running pipeline is also tracked in _running so
        # _submit_task's first check (in-memory) catches it. We test the
        # DB-side check too below.
        # Simulate a queue task aimed at goal 42.
        task = {"id": 999, "kind": "Backward", "target_id": "42",
                "payload": None}
        reactor._pool = MagicMock()
        reactor._submit_task(task)

        # Pool should NOT have been asked to submit anything.
        assert reactor._pool.submit.call_count == 0
        # Diagnostic event recorded.
        events = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        import json as _json
        rule = _json.loads(events[0])["rule"]
        assert rule == "dup_dispatch_dropped"

    def test_subgoal_shelve_propagates_to_proposed_strategy(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: when ANY sub-goal of a 'proposed' strategy is
        shelved/refuted, the strategy can never succeed (Builder needs
        ALL sub-goals proved). _run_structural_refill must mark such
        strategies dead so the cascade-up + parent-goal-shelve chain
        can run; otherwise zombie 'proposed' strategies block BFS
        Backward retry on the parent goal forever.
        """
        # Goal G with strategy S; S has sub-goals A (open) + B (shelved).
        goal_id = _insert_open_goal(db, tmp_path, slug="G")
        strat_id = _insert_strategy(db, tmp_path, goal_id, slug="S",
                                     status="proposed")
        sg_a = _insert_open_goal(db, tmp_path, slug="A_open")
        sg_b = _insert_open_goal(db, tmp_path, slug="B_shelved")
        # Mark B shelved.
        db.execute("UPDATE goals SET status='shelved' WHERE id=?", (sg_b,))
        _link_subgoal(db, strat_id, sg_a, position=0)
        _link_subgoal(db, strat_id, sg_b, position=1)
        db.commit()

        reactor = _make_reactor(db, tmp_path)
        reactor._propagate_subgoal_shelve_to_strategy()

        # Strategy S now dead.
        status = db.execute(
            "SELECT status FROM strategies WHERE id = ?", (strat_id,),
        ).fetchone()[0]
        assert status == "dead"

        # P7 演習 fix #11: goal stays 'open' (not shelved) until Backward
        # is blocked_pipelines for the goal. Cascade no longer shelves
        # immediately on all-strategies-dead — it gives Backward retry
        # the chance to produce more strategies. Use block_pipeline
        # explicitly to drive the goal to shelved here.
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        block_pipeline(db, goal_id, "Backward")
        # Re-run propagation; _mark_strategy_dead's shelve check now sees
        # all-dead AND blocked → shelves.
        reactor._mark_strategy_dead(strat_id)
        g_status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,),
        ).fetchone()[0]
        assert g_status == "shelved"

        # Diagnostic event for the propagation.
        events = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade' "
            "ORDER BY id DESC"
        ).fetchall()
        rules = []
        import json as _json
        for (p,) in events:
            try:
                rules.append(_json.loads(p).get("rule"))
            except Exception:
                pass
        assert "strategy_dead_subgoal_terminal" in rules

    def test_propagation_skips_strategy_with_all_open_subgoals(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Counterpart: when sub-goals are all open (or proved), strategy
        stays 'proposed' — the propagation only fires on terminal-not-
        proved sub-goals.
        """
        goal_id = _insert_open_goal(db, tmp_path, slug="G_ok")
        strat_id = _insert_strategy(db, tmp_path, goal_id, slug="S_ok",
                                     status="proposed")
        sg_a = _insert_open_goal(db, tmp_path, slug="A_ok")
        sg_b = _insert_open_goal(db, tmp_path, slug="B_ok")
        _link_subgoal(db, strat_id, sg_a, position=0)
        _link_subgoal(db, strat_id, sg_b, position=1)
        db.commit()

        reactor = _make_reactor(db, tmp_path)
        reactor._propagate_subgoal_shelve_to_strategy()

        status = db.execute(
            "SELECT status FROM strategies WHERE id = ?", (strat_id,),
        ).fetchone()[0]
        assert status == "proposed"

    def test_startup_sweeps_zombie_pipelines(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: prior daemon crash leaves pipelines.status='running'
        with no live worker thread. Without sweeping, the new daemon's
        `_is_already_dispatched` DB-side check treats them as in-flight,
        permanently blocking BFS from re-attacking the goal."""
        # Pre-seed 2 zombie running pipelines + 1 live finished one.
        for pid, kind, target_id, status, finished in [
            ("zombie-1", "Backward", "1", "running", None),
            ("zombie-2", "Builder", "2", "running", None),
            ("alive-1", "Backward", "3", "succeeded",
             "2026-04-29T05:01:00+00:00"),
        ]:
            db.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "started_at, finished_at) VALUES "
                "(?, ?, 'atomic', ?, 'Goal', ?, ?, ?)",
                (pid, kind, target_id, status,
                 "2026-04-29T05:00:00+00:00", finished),
            )
        db.commit()

        # Build a Reactor with conn injected — bypass real startup
        # (which would re-init DB) but invoke the sweep directly.
        reactor = Reactor(
            str(tmp_path / "test.db"),
            ReactorConfig(base_dir=str(tmp_path)),
        )
        reactor.conn = db
        reactor._sweep_zombie_pipelines()

        # All running rows now failed/cancelled.
        running_after = db.execute(
            "SELECT COUNT(*) FROM pipelines WHERE status = 'running'"
        ).fetchone()[0]
        assert running_after == 0
        # The originally-finished pipeline untouched.
        alive = db.execute(
            "SELECT status, outcome FROM pipelines WHERE id = 'alive-1'"
        ).fetchone()
        assert alive == ("succeeded", None)
        # Zombies marked cancelled.
        zombies = db.execute(
            "SELECT id, status, outcome FROM pipelines "
            "WHERE id IN ('zombie-1', 'zombie-2') ORDER BY id"
        ).fetchall()
        assert all(s == "failed" and o == "cancelled"
                   for (_, s, o) in zombies)
        # Diagnostic event emitted with count.
        events = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        import json as _json
        ev = _json.loads(events[0])
        assert ev["rule"] == "zombie_pipelines_swept"
        assert ev["count"] == 2

    def test_is_already_dispatched_checks_db_running(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """The DB-side branch of _is_already_dispatched: even when both
        in-memory _running and queue are empty, a DB pipeline with
        status='running' for this (target, kind) means work is in flight."""
        db.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, started_at) "
            "VALUES ('pipe-bw-99', 'Backward', 'atomic', '99', 'Goal', "
            "'running', ?)",
            ("2026-04-29T05:00:00+00:00",),
        )
        db.commit()
        reactor = _make_reactor(db, tmp_path)
        assert reactor._is_already_dispatched("99", "Backward") is True
        # Different target_id → not dispatched.
        assert reactor._is_already_dispatched("100", "Backward") is False
        # Different kind on same target → not dispatched.
        assert reactor._is_already_dispatched("99", "Builder") is False

    def test_bfs_skips_backward_when_proposed_strategy_exists(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: Backward retry pile-up race.

        Goal stays 'open' between Backward.commit_leaf (writes 'proposed'
        strategy) and cascade running (which marks goal proved/shelved
        based on Builder outcome). In that 30s gap, BFS would re-enqueue
        another Backward on the same goal, ending up with a second
        strategy competing with the first. Builder is in flight; no point
        in proposing a different proof until cascade resolves the first
        attempt.

        Skip Backward if the goal has any 'proposed' or 'succeeded'
        strategy (i.e. anything not 'dead'). Cascade eventually marks
        them dead → next BFS tick proceeds.
        """
        goal_id = _insert_open_goal(db, tmp_path, slug="proposed_g")
        # Insert a 'proposed' strategy (not dead) — Builder hasn't run yet.
        _insert_strategy(db, tmp_path, goal_id, slug="prop_strat",
                         status="proposed")

        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_backward()

        rows = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Backward' AND target_id=?",
            (str(goal_id),),
        ).fetchone()
        assert rows[0] == 0, (
            "BFS must skip Backward enqueue when goal has a non-dead "
            "strategy in flight; otherwise duplicate strategies pile up "
            "in the cascade-lag gap."
        )

    def test_bfs_enqueues_backward_when_only_dead_strategies(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Counterpart to the above: when all existing strategies on a
        goal are 'dead', Backward IS allowed to retry with feedback.
        """
        goal_id = _insert_open_goal(db, tmp_path, slug="retry_g")
        _insert_strategy(db, tmp_path, goal_id, slug="dead_strat",
                         status="dead")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_backward()
        rows = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Backward' AND target_id=?",
            (str(goal_id),),
        ).fetchone()
        assert rows[0] == 1

    def test_bfs_skips_builder_after_one_attempt_already_ran(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7演習 fix: BFS Builder retry pile-up race.

        After ONE Builder pipeline has run on a strategy (regardless of
        outcome), BFS must NOT enqueue another Builder for that strategy.
        Even if the strategy's status is still 'proposed' (cascade hasn't
        marked it dead yet), the second BFS tick sees one finished Builder
        attempt and skips. This is the logic-level fix for the race where
        BFS ticks (30s) faster than cascade can mark a strategy dead.
        """
        goal_id = _insert_open_goal(db, tmp_path, slug="rerun_g")
        strat_id = _insert_strategy(db, tmp_path, goal_id, slug="rerun_s")
        # Insert a finished Builder pipeline for this strategy
        # (simulating the just-finished, cascade-pending state).
        db.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, outcome, "
            "started_at, finished_at) VALUES "
            "(?, 'Builder', 'atomic', ?, 'Strategy', 'failed', 'exhausted', "
            "?, ?)",
            ("pipe-prior-builder", str(strat_id),
             "2026-04-29T05:00:00+00:00", "2026-04-29T05:01:00+00:00"),
        )
        db.commit()

        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_builder()

        # No new Builder queued.
        rows = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Builder' AND target_id=?",
            (str(strat_id),),
        ).fetchone()
        assert rows[0] == 0, (
            "BFS must skip Builder enqueue when a prior Builder pipeline "
            "exists; this prevents the cascade-lag race that piles up "
            "redundant Builder runs on the same strategy."
        )

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

    def test_bfs_enqueues_backward_for_open_conjecture(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P4 C31: kind='conjecture' goals also get Backward enqueued
        (was theorem-only in P3)."""
        goal_id = _insert_open_goal(
            db, tmp_path, slug="conj1", kind="conjecture")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_backward()
        row = db.execute(
            "SELECT target_id FROM queue WHERE kind='Backward'"
        ).fetchone()
        assert row is not None
        assert row[0] == str(goal_id)

    def test_bfs_enqueues_refuter_for_open_conjecture(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P4 C31: kind='conjecture' goals also get Refuter enqueued
        (three-line attack per architecture.md §6 structural refill).
        Counterexample line deferred per task.md ## 延後 cycles."""
        goal_id = _insert_open_goal(
            db, tmp_path, slug="conj2", kind="conjecture")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_refuter_for_conjecture()
        row = db.execute(
            "SELECT target_id FROM queue WHERE kind='Refuter'"
        ).fetchone()
        assert row is not None
        assert row[0] == str(goal_id)

    def test_bfs_no_refuter_for_theorem(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Theorem goals only get Backward (Refuter is conjecture-only)."""
        _insert_open_goal(db, tmp_path, slug="thm_only", kind="theorem")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_refuter_for_conjecture()
        count = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Refuter'"
        ).fetchone()[0]
        assert count == 0

    def test_bfs_skips_refuter_when_blocked(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Refuter blocked_pipelines filter."""
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        goal_id = _insert_open_goal(
            db, tmp_path, slug="conj_blocked", kind="conjecture")
        block_pipeline(db, goal_id, "Refuter")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_refuter_for_conjecture()
        count = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Refuter'"
        ).fetchone()[0]
        assert count == 0

    def test_bfs_no_dup_refuter(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Refuter dispatch is idempotent across BFS ticks."""
        goal_id = _insert_open_goal(
            db, tmp_path, slug="conj_dup", kind="conjecture")
        reactor = _make_reactor(db, tmp_path)
        reactor._bfs_enqueue_refuter_for_conjecture()
        reactor._bfs_enqueue_refuter_for_conjecture()
        count = db.execute(
            "SELECT count(*) FROM queue WHERE kind='Refuter' AND target_id=?",
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
        """When all strategies are dead AND Backward is blocked, goal →
        shelved + cascade event.

        P7 演習 fix #11: shelve only when Backward truly blocked
        (i.e. retry budget exhausted). Without the block, goal stays
        open to allow Backward to write more strategies.
        """
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("placeholder", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # Pre-block Backward so the deferred-shelve condition fires.
        from Tooling.subsystems.blocked_pipelines import block_pipeline
        block_pipeline(db, goal_id, "Backward")

        _make_reactor(db, tmp_path)._mark_strategy_dead(strategy_id)

        status = db.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()[0]
        assert status == "shelved"

        # P4 C31: _mark_strategy_dead now emits two cascade events —
        # one for cond 4 cancellation, one for the "all_strategies_dead→
        # shelved" rule. Match on any event having the shelved rule.
        events = db.execute(
            "SELECT payload FROM events WHERE kind='cascade'"
        ).fetchall()
        assert any(
            "all_strategies_dead" in json.loads(payload).get("rule", "")
            for (payload,) in events
        )

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
        """P4 C31: Builder proved → cancel_for_verdict called with
        goal_proved verdict on goal_id (replaces P3 _cancel_running_for_goal)."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("placeholder", "utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", "utf-8")
        goal_id, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": str(strategy_id)}

        with patch("Tooling.cancellation.cancel_for_verdict") as mock_cancel:
            reactor._run_step2_cancellation(task, BuilderResult(outcome="proved"))

        assert mock_cancel.call_count == 1
        called_args, called_kwargs = mock_cancel.call_args
        # First positional: conn; second: verdict
        verdict = called_args[1]
        assert verdict.kind == "goal_proved"
        assert verdict.goal_id == goal_id

    def test_step2_no_cancel_on_exhausted(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Builder exhausted → cancel_for_verdict NOT called."""
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": "1"}

        with patch("Tooling.cancellation.cancel_for_verdict") as mock_cancel:
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
        # Use a truly bogus kind — Refuter / Forward / Generalizer are now
        # supported in _execute_task_with_conn (R3 round 2 audit2 NEW-HIGH-A).
        task = {"id": 1, "kind": "Bogus", "target_id": "1", "payload": None}
        pid = "test-pid-1"
        reactor._running[pid] = (task["target_id"], task["kind"])

        # Run thread body directly (FatalError path)
        reactor._run_pipeline_thread(pid, task)

        events = []
        while not reactor._event_queue.empty():
            events.append(reactor._event_queue.get_nowait())

        fatal_events = [e for e in events if e[0] == "fatal"]
        assert len(fatal_events) >= 1
        assert "Bogus" in fatal_events[0][1]
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


class TestMakeFallbackChain:
    """P5 C36 R3: pin _make_fallback_chain composition + provider order.

    Spec phase5_construction.md ## In line 68: P5 single chain
    [claude, gemini, codex]. Caught by C36 R2 audit HIGH-1 — the original
    C36 R1 commit message described the wire-up but only codex.py +
    test_provider_codex.py landed in the commit; scheduler.py edit was
    in working tree but never staged. This test pins the wired chain so
    the gap is caught directly if it regresses.
    """

    def test_chain_has_three_providers(self, db, tmp_path):
        from Tooling.agent.providers.claude import ClaudeProvider
        from Tooling.agent.providers.gemini import GeminiProvider
        from Tooling.agent.providers.codex import CodexProvider
        reactor = _make_reactor(db, tmp_path)
        chain = reactor._make_fallback_chain()
        assert len(chain.providers) == 3
        assert isinstance(chain.providers[0], ClaudeProvider)
        assert isinstance(chain.providers[1], GeminiProvider)
        assert isinstance(chain.providers[2], CodexProvider)

    def test_chain_order_claude_gemini_codex(self, db, tmp_path):
        """Spec line 68: chain[0]=claude (leader), chain[1]=gemini,
        chain[2]=codex (last retry). Order pinned because order
        determines which provider absorbs which retry budget."""
        reactor = _make_reactor(db, tmp_path)
        chain = reactor._make_fallback_chain()
        names = [p.name for p in chain.providers]
        assert names == ["claude", "gemini", "codex"]

    def test_validate_scope_uses_provider_check_scope(self, db, tmp_path):
        """validate_scope is callable (model-independent git status backstop
        per spike-004). C36 R1 wired ClaudeProvider.check_scope as the
        chain's validate_scope; any provider's check_scope would be
        equivalent — the assertion is just "non-None and callable"."""
        reactor = _make_reactor(db, tmp_path)
        chain = reactor._make_fallback_chain()
        assert chain._validate_scope is not None
        assert callable(chain._validate_scope)


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
        is_stale = reactor._run_step1_stale_filter(
            task, BuilderResult(outcome="exhausted")
        )
        assert is_stale is True
        rows = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade'"
        ).fetchall()
        rules = [_json.loads(r[0]).get("rule") for r in rows]
        assert "stale_filter" in rules

    def test_step1_returns_false_for_live_target(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Non-stale event flows through to subsequent steps."""
        gid = _insert_open_goal(db, tmp_path, slug="live_g")
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Backward", "target_id": str(gid)}
        is_stale = reactor._run_step1_stale_filter(
            task, BackwardResult(outcome="exhausted")
        )
        assert is_stale is False

    def test_step1_drops_proved_goal_event(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25 R3 HIGH-1+2 (acceptance #9 gate): event for already-proved goal
        is dropped — caller skips downstream cascade.
        """
        gid = _insert_open_goal(db, tmp_path, slug="proved_g")
        with db:
            db.execute(
                "UPDATE goals SET status='proved' WHERE id=?", (gid,),
            )
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Backward", "target_id": str(gid)}
        is_stale = reactor._run_step1_stale_filter(
            task, BackwardResult(outcome="exhausted")
        )
        assert is_stale is True

    def test_step1_drops_dead_strategy_event(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25 R3 HIGH-1+2: event for already-dead strategy is dropped."""
        gid = _insert_open_goal(db, tmp_path, slug="g_for_dead_s")
        sid = _insert_strategy(db, tmp_path, gid, slug="dead_s")
        with db:
            db.execute(
                "UPDATE strategies SET status='dead' WHERE id=?", (sid,),
            )
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": str(sid)}
        is_stale = reactor._run_step1_stale_filter(
            task, BuilderResult(outcome="exhausted")
        )
        assert is_stale is True

    def test_step1_drops_refuter_on_terminal_goal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P4 C31 (covering C30 R2 LOW-1): step1 stale filter extends to
        Refuter target_kind. A Refuter pipeline result for a Goal that
        flipped to refuted/proved/shelved before the result arrived
        should be dropped (cascade does not re-act)."""
        import json as _json
        gid = _insert_open_goal(db, tmp_path, slug="conj_terminal",
                                kind="conjecture")
        with db:
            db.execute(
                "UPDATE goals SET status='refuted' WHERE id=?", (gid,),
            )
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Refuter", "target_id": str(gid)}
        from Tooling.pipelines.refuter import RefuterResult
        is_stale = reactor._run_step1_stale_filter(
            task, RefuterResult(outcome="exhausted")
        )
        assert is_stale is True
        rows = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade'"
        ).fetchall()
        rules = [_json.loads(r[0]).get("rule") for r in rows]
        assert "stale_filter" in rules

    def test_step1_refuter_passes_through_for_open_goal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P4 C31: Refuter result on still-open Goal flows through."""
        gid = _insert_open_goal(db, tmp_path, slug="conj_open",
                                kind="conjecture")
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Refuter", "target_id": str(gid)}
        from Tooling.pipelines.refuter import RefuterResult
        is_stale = reactor._run_step1_stale_filter(
            task, RefuterResult(outcome="success")
        )
        assert is_stale is False

    def test_step1_handles_malformed_target_id(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25 R3 MED-2: malformed payload doesn't crash dispatch — treated as stale."""
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Backward", "target_id": "N/A"}
        is_stale = reactor._run_step1_stale_filter(
            task, BackwardResult(outcome="exhausted")
        )
        assert is_stale is True

    def test_handle_pipeline_finished_skips_cascade_for_stale(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C25 R3 HIGH-1 (acceptance #9 字面): stale event → no downstream
        cascade, no orphan dead_attempts written."""
        gid = _insert_open_goal(db, tmp_path, slug="stale_proved")
        with db:
            db.execute(
                "UPDATE goals SET status='proved' WHERE id=?", (gid,),
            )
        reactor = _make_reactor(db, tmp_path)
        # Pre-insert a Backward pipeline so cascade WOULD have something to write
        with db:
            db.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, started_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ("pipe-stale", "Backward", "atomic", str(gid), "Goal",
                 "succeeded", "2026-01-01T00:00:00+00:00"),
            )
        task = {"kind": "Backward", "target_id": str(gid)}
        reactor._handle_pipeline_finished(task, BackwardResult(outcome="exhausted"))
        # No dead_attempts row written (cascade skipped)
        count = db.execute(
            "SELECT COUNT(*) FROM dead_attempts WHERE target_id=? AND pipeline_kind='Backward'",
            (str(gid),),
        ).fetchone()[0]
        assert count == 0

    def test_step5_strategist_trigger_does_nothing_without_problems(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Step 5 trigger is no-op when no live Goal exists in any Problem
        (active_problems=[]). C54 R1 + R3 round 2 wiring."""
        reactor = _make_reactor(db, tmp_path)
        task = {"kind": "Builder", "target_id": "1"}
        reactor._run_step5_strategist_trigger(task, BuilderResult(outcome="proved"))
        # No queue row, no events.
        assert db.execute("SELECT count(*) FROM queue").fetchone()[0] == 0

    def test_active_problems_excludes_no_open_goals(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: a Problem whose goals are all shelved/proved/refuted
        must NOT appear in _list_active_problems — Strategist would have
        nothing to coordinate, and the resulting queued task hits stale
        filter on every spawn cycle."""
        # 'wilson_x' has only shelved goals; 'wilson_y' has 1 open goal.
        for slug, status in [("g_shelved_a", "shelved"), ("g_shelved_b", "shelved")]:
            db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, origin, kind, status, commit_state, "
                "created_at, updated_at) VALUES "
                "('wilson_x', ?, ?, 'root', 'theorem', ?, 'live', ?, ?)",
                (slug, f"x/{slug}.lean", status,
                 "2026-04-29T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
            )
        db.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES "
            "('wilson_y', 'g_open', 'y/g.lean', 'root', 'theorem', 'open', "
            "'live', ?, ?)",
            ("2026-04-29T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
        )
        db.commit()

        reactor = _make_reactor(db, tmp_path)
        active = reactor._list_active_problems()
        assert active == ["wilson_y"]
        assert "wilson_x" not in active

    def test_stale_filter_strategist_target_id_format(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """P7 演習 fix: Strategist target_id is `_problem:<name>` string,
        not int. step1 stale filter must NOT report it as
        malformed_target_id; instead it should validate the prefix and
        check whether the Problem has any open goals.
        """
        # Problem with one open goal — Strategist task should NOT be stale.
        db.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES "
            "('p_active', 'g1', 'p/g1.lean', 'root', 'theorem', 'open', "
            "'live', ?, ?)",
            ("2026-04-29T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
        )
        # Problem with no open goals — Strategist task SHOULD be stale.
        db.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES "
            "('p_dormant', 'g2', 'p/g2.lean', 'root', 'theorem', 'shelved', "
            "'live', ?, ?)",
            ("2026-04-29T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
        )
        db.commit()

        reactor = _make_reactor(db, tmp_path)

        # Active Problem → not stale.
        active_task = {"id": 1, "kind": "Strategist",
                       "target_id": "_problem:p_active", "payload": None}
        assert reactor._run_step1_stale_filter(active_task, None) is False

        # Dormant Problem → stale with strategist_no_open_goals reason.
        dormant_task = {"id": 2, "kind": "Strategist",
                        "target_id": "_problem:p_dormant", "payload": None}
        assert reactor._run_step1_stale_filter(dormant_task, None) is True

        # Malformed target_id (no _problem: prefix) → stale with
        # strategist_malformed_target_id reason (different from the generic
        # int-cast malformed_target_id).
        bad_task = {"id": 3, "kind": "Strategist",
                    "target_id": "999", "payload": None}
        assert reactor._run_step1_stale_filter(bad_task, None) is True
        events = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        import json as _json
        assert _json.loads(events[0])["reason"] == "strategist_malformed_target_id"

    def test_step5_strategist_trigger_disabled_env(
        self, db: sqlite3.Connection, tmp_path: Path, monkeypatch
    ) -> None:
        """STRATEGIST_DISABLED=1 short-circuits the trigger even when a
        Strategist task would otherwise be enqueued (R3 round 2 audit2 MED-2)."""
        monkeypatch.setenv("STRATEGIST_DISABLED", "1")
        # Insert a live Goal so active_problems is non-empty.
        db.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES "
            "('p', 'g_root', 'p/g.lean', 'root', 'theorem', 'open', 'live', "
            "?, ?)",
            ("2026-04-29T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
        )
        db.commit()
        reactor = _make_reactor(db, tmp_path)
        reactor._run_step5_strategist_trigger(
            {"kind": "Builder", "target_id": "1"}, BuilderResult(outcome="proved")
        )
        # Disabled → no Strategist enqueued.
        assert db.execute(
            "SELECT count(*) FROM queue WHERE kind='Strategist'"
        ).fetchone()[0] == 0

    def test_warn_dropped_payload_keys_emits_event(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """R3 round 3 regression (audit3 batch 2 M_R2-2 followup): when a
        Strategist demux propagates payload keys (provider/budget/range/
        mutation_operators) that the spawn path doesn't yet honor,
        _warn_dropped_payload_keys must emit a 'payload_override_unconsumed'
        cascade event so the silent feature drop leaves a trail.
        """
        reactor = _make_reactor(db, tmp_path)
        # Direct method call — model key is consumed (no event), the others
        # are dropped (event expected).
        reactor._warn_dropped_payload_keys("Backward", {
            "model": "opus",       # consumed
            "provider": "gemini",  # dropped
            "budget": {"wall_clock_sec": 28800},  # dropped
        })

        events = db.execute(
            "SELECT payload FROM events WHERE kind = 'cascade'"
        ).fetchall()
        rules = [json.loads(p[0]) for p in events if p[0]]
        unconsumed = [r for r in rules
                      if r.get("rule") == "payload_override_unconsumed"]
        assert len(unconsumed) == 1
        assert unconsumed[0]["kind"] == "Backward"
        assert sorted(unconsumed[0]["dropped_keys"]) == ["budget", "provider"]
        # 'model' is consumed → must NOT appear in dropped_keys.
        assert "model" not in unconsumed[0]["dropped_keys"]

    def test_warn_dropped_payload_keys_silent_for_only_consumed(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When payload contains only `model`, no event should be emitted."""
        reactor = _make_reactor(db, tmp_path)
        reactor._warn_dropped_payload_keys("Backward", {"model": "opus"})
        rows = db.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'cascade'"
        ).fetchone()
        assert rows[0] == 0

    def test_step5_strategist_trigger_enqueues_after_K_finishes(
        self, db: sqlite3.Connection, tmp_path: Path, monkeypatch
    ) -> None:
        """R3 round 2 audit2 MED-2: when K_strategist non-Strategist pipelines
        have finished, step 5 enqueues exactly one Strategist task with
        priority=100 + target_id='_problem:<name>'.
        """
        monkeypatch.setenv("K_STRATEGIST", "2")  # tiny K for fast test
        # Insert live Goal under problem 'p'.
        db.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES "
            "('p', 'g_root', 'p/g.lean', 'root', 'theorem', 'open', 'live', "
            "?, ?)",
            ("2026-04-29T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
        )
        # Insert 2 finished non-Strategist pipelines (>= K_STRATEGIST=2).
        for i, ts in enumerate(
            ["2026-04-29T01:00:00+00:00", "2026-04-29T01:01:00+00:00"]
        ):
            db.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "started_at, finished_at) VALUES "
                "(?, 'Backward', 'atomic', '1', 'Goal', 'succeeded', ?, ?)",
                (f"pipe-pre-{i}", ts, ts),
            )
        db.commit()

        reactor = _make_reactor(db, tmp_path)
        reactor._run_step5_strategist_trigger(
            {"kind": "Builder", "target_id": "1"}, BuilderResult(outcome="proved")
        )

        rows = db.execute(
            "SELECT kind, target_id, priority FROM queue "
            "WHERE kind = 'Strategist'"
        ).fetchall()
        assert len(rows) == 1
        kind, target_id, priority = rows[0]
        assert kind == "Strategist"
        assert target_id == "_problem:p"
        assert priority == 100


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


class TestSchedulerLiveness:
    """P6 C40: pre-INSERT liveness check rejects dual instances."""

    def test_first_register_succeeds(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Empty schedulers table → register succeeds."""
        reactor = _make_reactor(db, tmp_path)
        reactor._register_scheduler()
        rows = db.execute("SELECT count(*) FROM schedulers").fetchone()
        assert rows[0] == 1
        assert reactor._scheduler_id is not None

    def test_second_register_with_live_row_raises(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Pre-existing row with last_heartbeat within TTL → FatalError."""
        from datetime import datetime, timezone
        recent = datetime.now(timezone.utc).isoformat()
        with db:
            db.execute(
                "INSERT INTO schedulers (host, pid, started_at, last_heartbeat) "
                "VALUES (?, ?, ?, ?)",
                ("other_host", 12345, recent, recent),
            )
        reactor = _make_reactor(db, tmp_path)
        with pytest.raises(FatalError, match="scheduler already running"):
            reactor._register_scheduler()
        # Fatal event emitted
        kind, msg = reactor._event_queue.get_nowait()
        assert kind == "fatal"
        assert "scheduler already running" in msg
        assert "force-clear" in msg

    def test_register_ignores_stale_row(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Pre-existing row with last_heartbeat older than TTL → register
        succeeds. Stale row is NOT auto-deleted (operator runs
        `asterism scheduler force-clear`)."""
        from datetime import datetime, timedelta, timezone
        stale = (
            datetime.now(timezone.utc) - timedelta(seconds=300)
        ).isoformat()
        with db:
            db.execute(
                "INSERT INTO schedulers (host, pid, started_at, last_heartbeat) "
                "VALUES (?, ?, ?, ?)",
                ("dead_host", 999, stale, stale),
            )
        reactor = _make_reactor(db, tmp_path)
        reactor._register_scheduler()
        # Two rows now: stale (preserved) + new (live)
        rows = db.execute("SELECT count(*) FROM schedulers").fetchone()
        assert rows[0] == 2

    def test_heartbeat_updates_last_heartbeat(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """_heartbeat() updates last_heartbeat for the registered row."""
        reactor = _make_reactor(db, tmp_path)
        reactor._register_scheduler()
        original_hb = db.execute(
            "SELECT last_heartbeat FROM schedulers WHERE id = ?",
            (reactor._scheduler_id,),
        ).fetchone()[0]
        # Sleep enough that ISO timestamps differ; reactor uses
        # datetime.now() with microsecond precision so even ~1ms suffices
        import time
        time.sleep(0.01)
        reactor._heartbeat()
        new_hb = db.execute(
            "SELECT last_heartbeat FROM schedulers WHERE id = ?",
            (reactor._scheduler_id,),
        ).fetchone()[0]
        assert new_hb > original_hb

    def test_heartbeat_no_op_when_not_registered(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """If _scheduler_id is None (e.g. heartbeat called before
        register), _heartbeat is a no-op — no exception."""
        reactor = _make_reactor(db, tmp_path)
        assert reactor._scheduler_id is None
        reactor._heartbeat()  # should not raise

    def test_heartbeat_sql_error_writes_fatal_event_no_raise(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """C40 R3 LOW-1 / HIGH-2: _heartbeat SQL UPDATE fail writes a
        fatal event row to events table via _emit_fatal but does NOT
        raise and does NOT enqueue ('fatal', ...) which would shut down
        the daemon. Daemon retries on next tick."""
        reactor = _make_reactor(db, tmp_path)
        reactor._register_scheduler()
        # Replace conn with one that raises on UPDATE but lets
        # _emit_fatal's INSERT INTO events succeed.
        real_conn = reactor.conn

        class _FailUpdateConn:
            def execute(self, sql, *args, **kwargs):
                if sql.startswith("UPDATE schedulers"):
                    raise sqlite3.Error("simulated UPDATE fail")
                return real_conn.execute(sql, *args, **kwargs)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        reactor.conn = _FailUpdateConn()
        # Should not raise
        reactor._heartbeat()
        # _event_queue stays empty (no fatal enqueue)
        assert reactor._event_queue.empty()
        # events table got a fatal row via _emit_fatal
        events = real_conn.execute(
            "SELECT kind, payload FROM events WHERE kind = 'fatal'"
        ).fetchall()
        assert len(events) >= 1
        assert any("_heartbeat update fail" in p for _, p in events)

    def test_liveness_query_sql_error_emits_fatal(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """SELECT live schedulers fail → fatal emitted + FatalError."""
        reactor = _make_reactor(db, tmp_path)
        reactor.conn = MagicMock()
        reactor.conn.execute.side_effect = sqlite3.Error("simulated SELECT fail")
        with pytest.raises(FatalError):
            reactor._register_scheduler()
        kind, msg = reactor._event_queue.get_nowait()
        assert kind == "fatal"
        assert "_register_scheduler" in msg
