"""Tests for Tooling/strategist/inventory.py (P7 C49).

Covers:
  - per_goal: shape, age calc, bad_goal_count, child_strategy_outcomes
    decoded from json_group_object.
  - per_subtree: recursive CTE rooted at origin='root', depth grouping.
  - top_n_bad_goals_global: ranks by COUNT(dead_attempts), respects limit,
    excludes goals with no bad attempts.
  - cross-Problem isolation: per_goal + per_subtree filter by problem.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.strategist.inventory import collect


_NOW = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


def _insert_goal(
    conn: sqlite3.Connection,
    *,
    problem: str = "p",
    slug: str,
    origin: str = "root",
    depth: int = 0,
    status: str = "open",
    commit_state: str = "live",
    status_changed_at: str | None = None,
) -> int:
    if status_changed_at is None:
        status_changed_at = _NOW.isoformat()
    cur = conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, commit_state, "
        "created_at, updated_at, depth, status_changed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"Problems/{problem}/{slug}.lean", origin,
         "theorem", status, commit_state,
         _NOW.isoformat(), _NOW.isoformat(),
         depth, status_changed_at),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


_STRATEGY_COUNTER = {"n": 0}


def _insert_strategy(
    conn: sqlite3.Connection,
    *,
    goal_id: int,
    status: str = "succeeded",
    commit_state: str = "live",
) -> int:
    _STRATEGY_COUNTER["n"] += 1
    n = _STRATEGY_COUNTER["n"]
    cur = conn.execute(
        "INSERT INTO strategies "
        "(goal_id, lean_path, status, commit_state, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (goal_id, f"strategies/g{goal_id}_s{n:04d}.lean",
         status, commit_state, _NOW.isoformat()),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _insert_strategy_subgoal(
    conn: sqlite3.Connection, *, strategy_id: int, subgoal_id: int, position: int = 0
) -> None:
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
        "VALUES (?, ?, ?)",
        (strategy_id, subgoal_id, position),
    )
    conn.commit()


_PIPELINE_COUNTER = {"n": 0}


def _insert_pipeline(conn: sqlite3.Connection, target_id: int) -> str:
    """Inventory tests don't care about pipeline content — just FK."""
    _PIPELINE_COUNTER["n"] += 1
    pid = f"pipe-test-{_PIPELINE_COUNTER['n']:04d}"
    conn.execute(
        "INSERT INTO pipelines "
        "(id, kind, runtime, target_id, target_kind, status, started_at) "
        "VALUES (?, 'Backward', 'atomic', ?, 'Goal', 'failed', ?)",
        (pid, str(target_id), _NOW.isoformat()),
    )
    conn.commit()
    return pid


def _insert_dead_attempt(
    conn: sqlite3.Connection, *, target_id: int, target_kind: str = "Goal",
    reason_summary: str = "bad sub-Goal: missing binder",
    pipeline_kind: str = "Backward",
) -> None:
    pid = _insert_pipeline(conn, target_id)
    conn.execute(
        "INSERT INTO dead_attempts "
        "(target_id, target_kind, pipeline_id, pipeline_kind, "
        " outcome, reason_summary, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(target_id), target_kind, pid, pipeline_kind,
         "exhausted", reason_summary, _NOW.isoformat()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# meta block
# ---------------------------------------------------------------------------

class TestMeta:
    def test_includes_problem_and_timestamp(self, db):
        out = collect(db, "p", now=_NOW)
        assert out["meta"]["problem"] == "p"
        assert out["meta"]["generated_at"] == _NOW.isoformat()
        assert out["meta"]["top_n_limit"] == 10

    def test_top_n_override(self, db):
        out = collect(db, "p", top_n=3, now=_NOW)
        assert out["meta"]["top_n_limit"] == 3


# ---------------------------------------------------------------------------
# per_goal
# ---------------------------------------------------------------------------

class TestPerGoal:
    def test_empty_problem_returns_empty(self, db):
        out = collect(db, "no_such_problem", now=_NOW)
        assert out["per_goal"] == []

    def test_lists_live_goals_in_problem(self, db):
        _insert_goal(db, problem="p", slug="g1")
        _insert_goal(db, problem="p", slug="g2", depth=1)
        _insert_goal(db, problem="other", slug="oth")
        out = collect(db, "p", now=_NOW)
        slugs = [g["slug"] for g in out["per_goal"]]
        assert slugs == ["g1", "g2"]

    def test_skips_pending_commit_state(self, db):
        _insert_goal(db, problem="p", slug="live_g")
        _insert_goal(db, problem="p", slug="pending_g", commit_state="pending")
        out = collect(db, "p", now=_NOW)
        slugs = [g["slug"] for g in out["per_goal"]]
        assert "live_g" in slugs
        assert "pending_g" not in slugs

    def test_attempting_age_min_calculated(self, db):
        ten_min_ago = (_NOW - timedelta(minutes=10)).isoformat()
        _insert_goal(db, problem="p", slug="g_aging",
                     status_changed_at=ten_min_ago)
        out = collect(db, "p", now=_NOW)
        assert out["per_goal"][0]["attempting_age_min"] == pytest.approx(10.0, abs=0.01)

    def test_bad_goal_count_filters_by_reason(self, db):
        gid = _insert_goal(db, problem="p", slug="g_bg")
        _insert_dead_attempt(db, target_id=gid,
                             reason_summary="bad sub-Goal: type mismatch")
        _insert_dead_attempt(db, target_id=gid,
                             reason_summary="bad sub-Goal: missing binder h")
        # An attempt with a non-bad-sub-Goal reason should NOT count.
        _insert_dead_attempt(db, target_id=gid,
                             reason_summary="lake build timeout")
        out = collect(db, "p", now=_NOW)
        assert out["per_goal"][0]["bad_goal_count"] == 2

    def test_child_strategy_outcomes_aggregate(self, db):
        gid = _insert_goal(db, problem="p", slug="g_parent")
        _insert_strategy(db, goal_id=gid, status="succeeded")
        _insert_strategy(db, goal_id=gid, status="dead")
        _insert_strategy(db, goal_id=gid, status="dead")
        _insert_strategy(db, goal_id=gid, status="proposed")
        out = collect(db, "p", now=_NOW)
        outcomes = out["per_goal"][0]["child_strategy_outcomes"]
        assert outcomes == {"succeeded": 1, "dead": 2, "proposed": 1}

    def test_no_strategies_yields_empty_outcomes(self, db):
        _insert_goal(db, problem="p", slug="g_lonely")
        out = collect(db, "p", now=_NOW)
        assert out["per_goal"][0]["child_strategy_outcomes"] == {}


# ---------------------------------------------------------------------------
# per_subtree
# ---------------------------------------------------------------------------

class TestPerSubtree:
    def test_root_only(self, db):
        rid = _insert_goal(db, problem="p", slug="root_g", depth=0)
        out = collect(db, "p", now=_NOW)
        assert out["per_subtree"] == [
            {"root_id": rid, "depth": 0, "goal_count": 1},
        ]

    def test_two_level_subtree(self, db):
        # root → strategy → 2 subgoals at depth 1
        rid = _insert_goal(db, problem="p", slug="root_g", depth=0)
        sid = _insert_strategy(db, goal_id=rid)
        s1 = _insert_goal(db, problem="p", slug="s1", origin="backward", depth=1)
        s2 = _insert_goal(db, problem="p", slug="s2", origin="backward", depth=1)
        _insert_strategy_subgoal(db, strategy_id=sid, subgoal_id=s1, position=0)
        _insert_strategy_subgoal(db, strategy_id=sid, subgoal_id=s2, position=1)
        out = collect(db, "p", now=_NOW)
        assert out["per_subtree"] == [
            {"root_id": rid, "depth": 0, "goal_count": 1},
            {"root_id": rid, "depth": 1, "goal_count": 2},
        ]

    def test_excludes_dead_strategy_branches(self, db):
        rid = _insert_goal(db, problem="p", slug="root_g", depth=0)
        sid = _insert_strategy(db, goal_id=rid, commit_state="pending")
        s1 = _insert_goal(db, problem="p", slug="s1", origin="backward", depth=1)
        _insert_strategy_subgoal(db, strategy_id=sid, subgoal_id=s1)
        out = collect(db, "p", now=_NOW)
        # Dead strategy excluded — only the root remains.
        assert out["per_subtree"] == [
            {"root_id": rid, "depth": 0, "goal_count": 1},
        ]


# ---------------------------------------------------------------------------
# top_n_bad_goals_global
# ---------------------------------------------------------------------------

class TestTopNGlobal:
    def test_excludes_zero_bad_goal_count(self, db):
        _insert_goal(db, problem="p", slug="clean_g")
        out = collect(db, "p", now=_NOW)
        assert out["top_n_bad_goals_global"] == []

    def test_orders_by_count_desc(self, db):
        g_a = _insert_goal(db, problem="p", slug="a")
        g_b = _insert_goal(db, problem="p", slug="b")
        for _ in range(3):
            _insert_dead_attempt(db, target_id=g_a)
        for _ in range(7):
            _insert_dead_attempt(db, target_id=g_b)
        out = collect(db, "p", now=_NOW)
        ranked = out["top_n_bad_goals_global"]
        assert [r["slug"] for r in ranked] == ["b", "a"]
        assert ranked[0]["bad_goal_count"] == 7
        assert ranked[1]["bad_goal_count"] == 3

    def test_includes_other_problems(self, db):
        """Top-N is GLOBAL — caller's problem is in meta only, not a filter."""
        g_p = _insert_goal(db, problem="p", slug="g_p")
        g_q = _insert_goal(db, problem="q", slug="g_q")
        _insert_dead_attempt(db, target_id=g_p)
        _insert_dead_attempt(db, target_id=g_q)
        out = collect(db, "p", now=_NOW)
        problems = {r["problem"] for r in out["top_n_bad_goals_global"]}
        assert problems == {"p", "q"}

    def test_respects_limit(self, db):
        for i in range(5):
            gid = _insert_goal(db, problem="p", slug=f"g_{i}")
            _insert_dead_attempt(db, target_id=gid)
        out = collect(db, "p", top_n=2, now=_NOW)
        assert len(out["top_n_bad_goals_global"]) == 2
