"""Unit tests for Tooling.scheduler.Reactor.

Covered cases:
  1. startup: recover_scan triggered; DB schema created
  2. queue pop: task returned + row deleted; None when empty; priority/FIFO order
  3. dispatch: Builder spawned with correct strategy_id; unknown kind raises FatalError
  4. cascade proved: goal status=proved, answer_data set, cascade event emitted
  5. cascade exhausted: goal status unchanged, no cascade event
  6. fatal halt: cascade SQL error → fatal event emitted + FatalError raised
  7. run loop: FatalError → sys.exit(1); empty queue → sys.exit(0)

lake / Builder fully mocked; no real subprocess.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import ANY, patch

import pytest

from Tooling.commit import CommitWriter
from Tooling.db.connect import init_schema
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
    reactor = Reactor.__new__(Reactor)
    reactor.db_path = tmp_path / "test.db"
    reactor.config = ReactorConfig(base_dir=str(tmp_path))
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
# 3. dispatch
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
        reactor = _make_reactor(db, tmp_path)
        task = {"id": 1, "kind": "Backward", "target_id": "1", "payload": None}
        with pytest.raises(FatalError):
            reactor._dispatch(task)


# ---------------------------------------------------------------------------
# 4. cascade: proved
# ---------------------------------------------------------------------------


class TestCascadeProved:
    def test_goal_status_set_proved(self, db: sqlite3.Connection, tmp_path: Path) -> None:
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

    def test_answer_data_written(self, db: sqlite3.Connection, tmp_path: Path) -> None:
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

    def test_cascade_event_emitted(self, db: sqlite3.Connection, tmp_path: Path) -> None:
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
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """SQL error in _update_goal_proved → fatal event written to events table."""
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
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """SQL error in cascade → FatalError is raised (not swallowed)."""
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
