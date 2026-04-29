"""Tests for Tooling/strategist/round_robin.py (P7 C51)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.strategist.round_robin import (
    consume,
    is_strategist_running,
    select_next,
)


_BASE = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


_PIPE_COUNTER = {"n": 0}


def _insert_pipeline(
    conn: sqlite3.Connection,
    *,
    kind: str = "Backward",
    status: str = "succeeded",
    finished: bool = True,
) -> int:
    _PIPE_COUNTER["n"] += 1
    n = _PIPE_COUNTER["n"]
    # Each pipeline gets a unique finished_at so the marker-based counter
    # in round_robin advances correctly across consume() calls.
    ts = (_BASE + timedelta(seconds=n)).isoformat()
    pid = f"pipe-{n:04d}"
    finished_at = ts if finished else None
    conn.execute(
        "INSERT INTO pipelines "
        "(id, kind, runtime, target_id, target_kind, status, started_at, "
        "finished_at) VALUES (?, ?, 'atomic', '1', 'Goal', ?, ?, ?)",
        (pid, kind, status, ts, finished_at),
    )
    conn.commit()
    return n


# ---------------------------------------------------------------------------
# Empty / cooldown gates
# ---------------------------------------------------------------------------


class TestGuards:
    def test_no_problems_returns_none(self, db):
        assert select_next(db, [], K=1) is None

    def test_under_K_returns_none(self, db):
        for _ in range(3):
            _insert_pipeline(db)
        assert select_next(db, ["a", "b"], K=8) is None

    def test_cooldown_predicate_blocks(self, db):
        # Plenty of finished events, but cooldown is active.
        for _ in range(20):
            _insert_pipeline(db)
        assert select_next(
            db, ["a", "b"], K=8, cooldown_active=lambda: True
        ) is None

    def test_default_cooldown_uses_running_strategist(self, db):
        for _ in range(20):
            _insert_pipeline(db)
        # Insert a running Strategist row → built-in cooldown.
        _insert_pipeline(db, kind="Strategist", status="running",
                         finished=False)
        assert is_strategist_running(db) is True
        assert select_next(db, ["a", "b"], K=8) is None


# ---------------------------------------------------------------------------
# Strict round-robin
# ---------------------------------------------------------------------------


class TestRotation:
    def test_first_call_picks_first_problem(self, db):
        for _ in range(8):
            _insert_pipeline(db)
        assert select_next(db, ["alpha", "beta", "gamma"], K=8) == "alpha"

    def test_consume_advances_to_next(self, db):
        for _ in range(8):
            _insert_pipeline(db)
        assert select_next(db, ["a", "b", "c"], K=8) == "a"
        consume(db, "a")
        for _ in range(8):
            _insert_pipeline(db)
        assert select_next(db, ["a", "b", "c"], K=8) == "b"
        consume(db, "b")
        for _ in range(8):
            _insert_pipeline(db)
        assert select_next(db, ["a", "b", "c"], K=8) == "c"
        consume(db, "c")
        for _ in range(8):
            _insert_pipeline(db)
        assert select_next(db, ["a", "b", "c"], K=8) == "a"  # wrap

    def test_strategist_self_finished_does_not_count(self, db):
        for _ in range(7):
            _insert_pipeline(db)
        # A Strategist commit row should NOT bump the counter.
        for _ in range(50):
            _insert_pipeline(db, kind="Strategist")
        assert select_next(db, ["a", "b"], K=8) is None  # still under K

    def test_consume_resets_counter(self, db):
        for _ in range(8):
            _insert_pipeline(db)
        assert select_next(db, ["a", "b"], K=8) == "a"
        consume(db, "a")
        # Counter reset; below K again.
        assert select_next(db, ["a", "b"], K=8) is None

    def test_unknown_last_problem_falls_back_to_first(self, db):
        for _ in range(8):
            _insert_pipeline(db)
        consume(db, "removed_problem")
        for _ in range(8):
            _insert_pipeline(db)
        assert select_next(db, ["alpha", "beta"], K=8) == "alpha"


# ---------------------------------------------------------------------------
# K configuration
# ---------------------------------------------------------------------------


class TestKConfig:
    def test_explicit_K_threshold(self, db):
        for _ in range(2):
            _insert_pipeline(db)
        assert select_next(db, ["a"], K=2) == "a"
        # K=3 would still return None.
        consume(db, "a")
        for _ in range(2):
            _insert_pipeline(db)
        assert select_next(db, ["a"], K=3) is None
