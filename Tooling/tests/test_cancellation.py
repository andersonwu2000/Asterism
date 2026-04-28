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
    target_kind: str | None = None,
    status: str = "running",
    runtime: str = "atomic",
) -> None:
    """Insert a pipelines row.

    `target_kind` defaults to the production shape per pipeline kind:
      Builder    → 'Strategy'
      Backward / Refuter / Counterexample / ConstructionSearch → 'Goal'
    Tests that need the production-shape semantics should pass kind only;
    pass target_kind explicitly to override (e.g. for negative tests).
    """
    if target_kind is None:
        target_kind = "Strategy" if kind == "Builder" else "Goal"
    with conn:
        conn.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (pid, kind, runtime, target_id, target_kind, status),
        )


def _insert_strategy(conn, *, sid: int, goal_id: int) -> None:
    """Insert a minimal strategies row (P3+ shape: target_kind='Strategy'
    is what Builder pipelines reference)."""
    with conn:
        conn.execute(
            "INSERT INTO strategies "
            "(id, goal_id, lean_path, status, commit_state, created_at) "
            "VALUES (?, ?, ?, 'in_progress', 'live', datetime('now'))",
            (sid, goal_id, f"strat_{sid}.lean"),
        )


def _insert_goal_minimal(conn, *, gid: int, slug: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO goals "
            "(id, problem, slug, lean_path, origin, kind, status, "
            "commit_state, created_at, updated_at) "
            "VALUES (?, 'P', ?, ?, 'root', 'theorem', 'open', 'live', "
            "datetime('now'), datetime('now'))",
            (gid, slug, f"{slug}.lean"),
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
    def test_selects_goal_targeted_pipelines(self, db):
        """Cond 1: Backward/Refuter/Counterexample on G are cancelled
        (target_kind='Goal' production shape)."""
        _insert_goal_minimal(db, gid=42, slug="g")
        _insert_pipeline(db, pid="p1", kind="Backward", target_id="42")
        _insert_pipeline(db, pid="p2", kind="Refuter", target_id="42")
        # Other goal — NOT cancelled
        _insert_goal_minimal(db, gid=99, slug="other")
        _insert_pipeline(db, pid="p3", kind="Backward", target_id="99")
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=42)
        )
        ids = {r["id"] for r in result}
        assert ids == {"p1", "p2"}

    def test_selects_builder_via_strategy_join(self, db):
        """C31 R3 MED-1: spec L429 字面要求 Builder pipelines also be
        cancelled. Builder's target_kind='Strategy' so selection must
        join through strategies table to find Strategy rows whose
        goal_id matches the verdict goal."""
        _insert_goal_minimal(db, gid=10, slug="g_with_strats")
        _insert_strategy(db, sid=100, goal_id=10)
        _insert_strategy(db, sid=101, goal_id=10)
        _insert_pipeline(db, pid="b1", kind="Builder", target_id="100")
        _insert_pipeline(db, pid="b2", kind="Builder", target_id="101")
        # Also a Backward on the same Goal (target_kind='Goal')
        _insert_pipeline(db, pid="bw", kind="Backward", target_id="10")
        # Other goal's Builder
        _insert_goal_minimal(db, gid=20, slug="other_g")
        _insert_strategy(db, sid=200, goal_id=20)
        _insert_pipeline(db, pid="b_other", kind="Builder", target_id="200")
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=10)
        )
        ids = {r["id"] for r in result}
        assert ids == {"bw", "b1", "b2"}

    def test_skips_finished_pipelines(self, db):
        _insert_goal_minimal(db, gid=42, slug="g_fin")
        _insert_strategy(db, sid=420, goal_id=42)
        _insert_pipeline(db, pid="r1", kind="Backward",
                         target_id="42", status="running")
        _insert_pipeline(db, pid="d1", kind="Builder",
                         target_id="420", status="succeeded")
        _insert_pipeline(db, pid="d2", kind="Backward",
                         target_id="42", status="failed")
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=42)
        )
        assert {r["id"] for r in result} == {"r1"}

    def test_excludes_non_whitelist_kinds(self, db):
        """C31 R3 MED-2: spec L435 保守原則 — Forward/Generalizer/Strategist
        not in cond 1 white-list."""
        _insert_goal_minimal(db, gid=42, slug="g_fc")
        _insert_pipeline(db, pid="bw", kind="Backward", target_id="42")
        _insert_pipeline(db, pid="fwd", kind="Forward", target_id="42")
        _insert_pipeline(db, pid="gen", kind="Generalizer", target_id="42")
        # Strategist target_kind='Goal' is hypothetical, but we test the
        # current production target_kind value to lock the white-list filter.
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=42)
        )
        ids = {r["id"] for r in result}
        # Only Backward (Goal-targeted, in cond 1 white-list)
        assert ids == {"bw"}

    def test_no_running_returns_empty(self, db):
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="goal_proved", goal_id=999)
        )
        assert result == []


# ---------------------------------------------------------------------------
# Condition 2: twin_refuted → cancel both G + ¬G
# ---------------------------------------------------------------------------

class TestCond2TwinRefuted:
    def test_cancels_both_sides_production_shape(self, db):
        """C31 R3 MED-1: cond 2 cancels Goal-targeted pipelines on G + ¬G
        AND Builder pipelines for any strategy of G + ¬G."""
        _insert_goal_minimal(db, gid=10, slug="g")
        _insert_goal_minimal(db, gid=11, slug="ng")
        _insert_strategy(db, sid=110, goal_id=11)  # ¬G's strategy
        _insert_pipeline(db, pid="g_back", kind="Backward", target_id="10")
        _insert_pipeline(db, pid="g_ref", kind="Refuter", target_id="10")
        _insert_pipeline(db, pid="ng_back", kind="Backward", target_id="11")
        _insert_pipeline(db, pid="ng_b", kind="Builder", target_id="110")
        _insert_goal_minimal(db, gid=42, slug="other")
        _insert_strategy(db, sid=420, goal_id=42)
        _insert_pipeline(db, pid="other", kind="Builder", target_id="420")
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
    def test_cancels_builder_on_strategy(self, db):
        """C31 R3 MED-3: cond 4 cancels Builder pipelines targeting the
        dead Strategy. Backward (target_kind='Goal') is NOT in cond 4
        white-list — its post-hoc drop is handled by step1_stale_filter
        when the parent Goal eventually shelves."""
        _insert_pipeline(db, pid="b", kind="Builder", target_id="50")
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="strategy_dead", strategy_id=50)
        )
        ids = {r["id"] for r in result}
        assert ids == {"b"}

    def test_backward_not_cancelled_by_strategy_dead(self, db):
        """Backward.target_kind='Goal' so cond 4 SQL never matches it
        directly. step1_stale_filter handles the cleanup post-shelve."""
        _insert_pipeline(db, pid="bw", kind="Backward", target_id="42")
        result = select_pipelines_to_cancel(
            db, CancellationVerdict(kind="strategy_dead", strategy_id=50)
        )
        # Even with no strategy match, cond 4 returns empty list (Backward
        # on Goal not in cond 4 SQL space).
        assert result == []

    def test_other_strategies_unaffected(self, db):
        """Cond 4 is same-Strategy scope, NOT same-Goal."""
        _insert_pipeline(db, pid="b1", kind="Builder", target_id="50")
        _insert_pipeline(db, pid="b2", kind="Builder", target_id="60")
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
