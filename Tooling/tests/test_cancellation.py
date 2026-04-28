"""Unit tests for Tooling/cancellation.py white-list (P4 C31)."""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.cancellation import (
    CancellationVerdict,
    cancel_for_verdict,
    select_pipelines_to_cancel,
)
from Tooling.db.connect import connect, init_schema


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    yield conn
    conn.close()


def _insert_pipeline(
    conn,
    *,
    pid: str,
    kind: str,
    target_id: str,
    target_kind: str = "Goal",
    status: str = "running",
    runtime: str = "atomic",
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (pid, kind, runtime, target_id, target_kind, status),
        )


# ---------------------------------------------------------------------------
# Verdict validation
# ---------------------------------------------------------------------------

class TestVerdictValidation:
    def test_unknown_kind_raises(self, db):
        with pytest.raises(ValueError, match="unknown CancellationVerdict.kind"):
            select_pipelines_to_cancel(db, CancellationVerdict(kind="bogus"))

    def test_goal_proved_requires_goal_id(self, db):
        with pytest.raises(ValueError, match="goal_proved.*goal_id"):
            select_pipelines_to_cancel(db, CancellationVerdict(kind="goal_proved"))

    def test_twin_refuted_requires_both_ids(self, db):
        with pytest.raises(ValueError, match="twin_refuted.*goal_id.*twin_id"):
            select_pipelines_to_cancel(
                db, CancellationVerdict(kind="twin_refuted", goal_id=1)
            )

    def test_strategy_dead_requires_strategy_id(self, db):
        with pytest.raises(ValueError, match="strategy_dead.*strategy_id"):
            select_pipelines_to_cancel(
                db, CancellationVerdict(kind="strategy_dead")
            )

    def test_counterexample_silver_raises_deferred(self, db):
        """Counterexample is deferred per task.md ## 延後 cycles; verdict
        should raise NotImplementedError if anyone tries to use it now."""
        with pytest.raises(NotImplementedError, match="Counterexample"):
            select_pipelines_to_cancel(
                db, CancellationVerdict(
                    kind="counterexample_silver", goal_id=1)
            )


# ---------------------------------------------------------------------------
# Condition 1: goal_proved → cancel any kind on G
# ---------------------------------------------------------------------------

class TestCond1GoalProved:
    def test_selects_running_pipelines_on_goal(self, db):
        _insert_pipeline(db, pid="p1", kind="Backward", target_id="42")
        _insert_pipeline(db, pid="p2", kind="Refuter", target_id="42")
        _insert_pipeline(db, pid="p3", kind="Builder", target_id="99")  # other goal
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=42)
        )
        ids = {r["id"] for r in result}
        assert ids == {"p1", "p2"}

    def test_skips_finished_pipelines(self, db):
        _insert_pipeline(db, pid="r1", kind="Backward",
                         target_id="42", status="running")
        _insert_pipeline(db, pid="d1", kind="Builder",
                         target_id="42", status="succeeded")
        _insert_pipeline(db, pid="d2", kind="Backward",
                         target_id="42", status="failed")
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=42)
        )
        assert {r["id"] for r in result} == {"r1"}

    def test_no_running_returns_empty(self, db):
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=999)
        )
        assert result == []


# ---------------------------------------------------------------------------
# Condition 2: twin_refuted → cancel both G + ¬G
# ---------------------------------------------------------------------------

class TestCond2TwinRefuted:
    def test_cancels_both_sides(self, db):
        _insert_pipeline(db, pid="g_back", kind="Backward", target_id="10")
        _insert_pipeline(db, pid="g_ref", kind="Refuter", target_id="10")
        _insert_pipeline(db, pid="ng_back", kind="Backward", target_id="11")
        _insert_pipeline(db, pid="ng_b", kind="Builder", target_id="11")
        _insert_pipeline(db, pid="other", kind="Builder", target_id="42")  # other goal
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(
                kind="twin_refuted", goal_id=10, twin_id=11)
        )
        ids = {r["id"] for r in result}
        assert ids == {"g_back", "g_ref", "ng_back", "ng_b"}


# ---------------------------------------------------------------------------
# Condition 4: strategy_dead → cancel Builder/Backward on strategy
# ---------------------------------------------------------------------------

class TestCond4StrategyDead:
    def test_cancels_builder_backward_on_strategy(self, db):
        _insert_pipeline(db, pid="b", kind="Builder",
                         target_id="50", target_kind="Strategy")
        _insert_pipeline(db, pid="bw", kind="Backward",
                         target_id="50", target_kind="Strategy")
        # Refuter on a Strategy (hypothetical) should NOT be cancelled
        # under cond 4 (only Builder/Backward in cond 4 white-list).
        _insert_pipeline(db, pid="r", kind="Refuter",
                         target_id="50", target_kind="Strategy")
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="strategy_dead", strategy_id=50)
        )
        ids = {r["id"] for r in result}
        assert ids == {"b", "bw"}

    def test_other_strategies_unaffected(self, db):
        """Cond 4 is same-Strategy scope, NOT same-Goal."""
        _insert_pipeline(db, pid="b1", kind="Builder",
                         target_id="50", target_kind="Strategy")
        _insert_pipeline(db, pid="b2", kind="Builder",
                         target_id="60", target_kind="Strategy")  # other strat
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="strategy_dead", strategy_id=50)
        )
        assert {r["id"] for r in result} == {"b1"}


# ---------------------------------------------------------------------------
# cancel_for_verdict integration (event emission)
# ---------------------------------------------------------------------------

class TestCancelForVerdictEvent:
    def test_emit_event_called_with_audit_payload(self, db):
        _insert_pipeline(db, pid="x", kind="Backward", target_id="7")
        captured: list[tuple[str, dict]] = []

        def fake_emit(kind, payload):
            captured.append((kind, payload))

        n = cancel_for_verdict(
            db,
            CancellationVerdict(kind="goal_proved", goal_id=7),
            emit_event=fake_emit,
        )
        assert n == 1
        assert len(captured) == 1
        assert captured[0][0] == "cascade"
        payload = captured[0][1]
        assert payload["rule"] == "cancellation:goal_proved"
        assert payload["matched_pipeline_ids"] == ["x"]
        assert payload["verdict"]["goal_id"] == 7

    def test_no_emit_when_callback_none(self, db):
        _insert_pipeline(db, pid="x", kind="Backward", target_id="7")
        # Should not raise even with no emit callback
        n = cancel_for_verdict(
            db,
            CancellationVerdict(kind="goal_proved", goal_id=7),
            emit_event=None,
        )
        assert n == 1

    def test_returns_zero_when_no_match(self, db):
        captured: list = []
        n = cancel_for_verdict(
            db,
            CancellationVerdict(kind="goal_proved", goal_id=999),
            emit_event=lambda k, p: captured.append((k, p)),
        )
        assert n == 0
        # Still emits the audit event (matched_pipeline_ids = [])
        assert len(captured) == 1
        assert captured[0][1]["matched_pipeline_ids"] == []
