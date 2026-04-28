"""Unit tests for Tooling.stages.{failure_replay,find_lemmas,find_subgoals} (P3 C22)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.stages.failure_replay import DEFAULT_K_DIGEST, failure_replay
from Tooling.stages.find_lemmas import find_lemmas
from Tooling.stages.find_subgoals import find_subgoals


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "asterism.db")
    init_schema(conn)
    yield conn
    conn.close()


def _ensure_pipeline_row(conn: sqlite3.Connection, pid: str = "pipeline-x") -> str:
    """Insert a dummy pipelines row to satisfy FK from dead_attempts.pipeline_id.

    INSERT OR IGNORE makes this idempotent within a single conn.
    """
    conn.execute(
        "INSERT OR IGNORE INTO pipelines "
        "(id, kind, runtime, target_id, target_kind, status, started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (pid, "Backward", "atomic", "0", "Goal", "succeeded", _NOW),
    )
    conn.commit()
    return pid


def _insert_dead_attempt(
    conn: sqlite3.Connection,
    *,
    target_id: str,
    target_kind: str,
    reason: str,
    outcome: str = "exhausted",
    pipeline_kind: str = "Backward",
    ts: str = _NOW,
) -> int:
    pid = _ensure_pipeline_row(conn)
    conn.execute(
        "INSERT INTO dead_attempts "
        "(target_id, target_kind, pipeline_id, pipeline_kind, "
        "outcome, reason_summary, ts) "
        "VALUES (?,?,?,?,?,?,?)",
        (target_id, target_kind, pid, pipeline_kind,
         outcome, reason, ts),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_goal(
    conn: sqlite3.Connection,
    *,
    slug: str,
    problem: str = "ex",
    commit_state: str = "live",
) -> int:
    conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, "
        "commit_state, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"path/{slug}.lean", "root", "theorem", "open",
         commit_state, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ---------------------------------------------------------------------------
# failure_replay
# ---------------------------------------------------------------------------


class TestFailureReplay:
    def test_empty_dead_attempts_returns_empty(self, db) -> None:
        assert failure_replay(db, 42, "Goal") == []

    def test_returns_matching_target(self, db) -> None:
        _insert_dead_attempt(db, target_id="42", target_kind="Goal",
                             reason="agent JSON parse fail")
        _insert_dead_attempt(db, target_id="99", target_kind="Goal",
                             reason="other goal")
        rows = failure_replay(db, 42, "Goal")
        assert len(rows) == 1
        assert rows[0]["reason"] == "agent JSON parse fail"

    def test_target_kind_filter(self, db) -> None:
        """Goal vs Strategy must not cross-pollute (same target_id by accident)."""
        _insert_dead_attempt(db, target_id="5", target_kind="Goal",
                             reason="goal-side")
        _insert_dead_attempt(db, target_id="5", target_kind="Strategy",
                             reason="strategy-side")
        goal_rows = failure_replay(db, 5, "Goal")
        strat_rows = failure_replay(db, 5, "Strategy")
        assert len(goal_rows) == 1
        assert goal_rows[0]["reason"] == "goal-side"
        assert len(strat_rows) == 1
        assert strat_rows[0]["reason"] == "strategy-side"

    def test_k_digest_caps_results(self, db) -> None:
        for i in range(10):
            _insert_dead_attempt(
                db, target_id="7", target_kind="Goal",
                reason=f"reason {i}",
                ts=f"2026-01-01T00:00:{i:02d}+00:00",
            )
        # Default cap = 5
        rows = failure_replay(db, 7, "Goal")
        assert len(rows) == DEFAULT_K_DIGEST == 5
        # Custom cap
        rows = failure_replay(db, 7, "Goal", k_digest=3)
        assert len(rows) == 3

    def test_orders_newest_first(self, db) -> None:
        _insert_dead_attempt(
            db, target_id="3", target_kind="Goal",
            reason="old", ts="2026-01-01T00:00:00+00:00",
        )
        _insert_dead_attempt(
            db, target_id="3", target_kind="Goal",
            reason="newest", ts="2026-01-01T00:00:10+00:00",
        )
        _insert_dead_attempt(
            db, target_id="3", target_kind="Goal",
            reason="middle", ts="2026-01-01T00:00:05+00:00",
        )
        rows = failure_replay(db, 3, "Goal")
        assert [r["reason"] for r in rows] == ["newest", "middle", "old"]

    def test_invalid_target_kind_raises(self, db) -> None:
        with pytest.raises(ValueError, match="unknown target_kind"):
            failure_replay(db, 1, "Bogus")


# ---------------------------------------------------------------------------
# find_lemmas
# ---------------------------------------------------------------------------


class TestFindLemmas:
    def test_search_mock_force_miss(self, db, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_MOCK", "force_miss")
        result = find_lemmas(db, {"slug": "g_test", "question": "True"})
        assert result == []

    def test_search_mock_force_hit_returns_synthetic(self, db, monkeypatch) -> None:
        """force_hit returns synthetic entry per scope; merged across mathlib + library."""
        monkeypatch.setenv("SEARCH_MOCK", "force_hit")
        result = find_lemmas(db, {"slug": "g_test"})
        assert len(result) == 2  # one from mathlib + one from library
        assert all(r.get("name") == "_mock_hit" for r in result)

    def test_empty_query_returns_empty(self, db) -> None:
        """No slug + no question → empty query → return [] without subprocess."""
        result = find_lemmas(db, {"slug": ""})
        assert result == []


# ---------------------------------------------------------------------------
# find_subgoals
# ---------------------------------------------------------------------------


class TestFindSubgoals:
    def test_empty_goals_table_returns_empty(self, db) -> None:
        assert find_subgoals(db, {"slug": "anything", "problem": "ex"}) == []

    def test_returns_matching_local_goals(self, db) -> None:
        _insert_goal(db, slug="add_zero")
        _insert_goal(db, slug="mul_comm")
        result = find_subgoals(db, {"slug": "add", "problem": "ex"})
        slugs = [r["slug"] for r in result]
        assert "add_zero" in slugs
        assert "mul_comm" not in slugs

    def test_skips_pending_commit_state(self, db) -> None:
        _insert_goal(db, slug="pending_match", commit_state="pending")
        _insert_goal(db, slug="live_match",    commit_state="live")
        result = find_subgoals(db, {"slug": "match", "problem": "ex"})
        slugs = [r["slug"] for r in result]
        assert "pending_match" not in slugs
        assert "live_match" in slugs

    def test_empty_query_returns_empty(self, db) -> None:
        assert find_subgoals(db, {"slug": "", "problem": "ex"}) == []

    def test_excludes_self(self, db) -> None:
        """C22 R3 HIGH-3: parent goal must not appear in its own sub-goal list."""
        gid = _insert_goal(db, slug="parent_g")
        result = find_subgoals(db, {"id": gid, "slug": "parent_g", "problem": "ex"})
        ids = [r["id"] for r in result]
        assert gid not in ids

    @pytest.mark.xfail(
        reason="P6 schema gap: search_cache lacks problem_scope column; "
               "_search_local_goals does not filter by problem (state.md:46 caveat)",
        strict=True,
    )
    def test_does_not_leak_across_problems(self, db) -> None:
        """C22 R3 LOW-1: cross-Problem isolation via SQL filter — currently leaks."""
        _insert_goal(db, slug="match_a", problem="A")
        _insert_goal(db, slug="match_b", problem="B")
        result = find_subgoals(db, {"slug": "match", "problem": "A"})
        # Expect only Problem A row to come back
        problems = {r.get("slug")[-1] for r in result}  # 'a' or 'b'
        assert problems == {"a"}, f"cross-Problem leak: {result}"


# ---------------------------------------------------------------------------
# Additional find_lemmas tests (C22 R3 LOW-1)
# ---------------------------------------------------------------------------


class TestFindLemmasExtra:
    def test_query_construction_handles_none_question(
        self, db, monkeypatch
    ) -> None:
        """goal['question'] is None (most P2 goals) → query is just slug."""
        monkeypatch.setenv("SEARCH_MOCK", "record_calls")
        from Tooling.subsystems.search import (
            get_recorded_calls,
            reset_recorded_calls,
        )
        reset_recorded_calls()
        find_lemmas(db, {"slug": "g_test", "question": None})
        calls = get_recorded_calls()
        assert all(call["query"] == "g_test" for call in calls)

    def test_query_construction_appends_question(
        self, db, monkeypatch
    ) -> None:
        monkeypatch.setenv("SEARCH_MOCK", "record_calls")
        from Tooling.subsystems.search import (
            get_recorded_calls,
            reset_recorded_calls,
        )
        reset_recorded_calls()
        find_lemmas(db, {"slug": "g_test", "question": "True"})
        calls = get_recorded_calls()
        assert all(call["query"] == "g_test True" for call in calls)

    def test_mathlib_results_appear_before_library(
        self, db, monkeypatch
    ) -> None:
        """find_lemmas docstring says mathlib first then library; verify ordering."""
        # Use side_effect with a counter so the two scopes return distinct results
        from Tooling.subsystems import search as search_mod
        original = search_mod.search

        def fake(query, scope, kind, **kwargs):
            from Tooling.subsystems.search import SearchResult
            if scope == "mathlib":
                return SearchResult(results=[{"name": "M_first"}])
            if scope == "library":
                return SearchResult(results=[{"name": "L_second"}])
            return original(query, scope=scope, kind=kind, **kwargs)

        monkeypatch.setattr(search_mod, "search", fake)
        # Re-import find_lemmas to pick up patched search (it imports at module load)
        import importlib
        import Tooling.stages.find_lemmas as fl
        importlib.reload(fl)
        try:
            results = fl.find_lemmas(db, {"slug": "g"})
            names = [r["name"] for r in results]
            assert names == ["M_first", "L_second"]
        finally:
            importlib.reload(fl)  # restore real search reference
