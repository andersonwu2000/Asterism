"""Unit tests for Tooling.subsystems.search (P3 C20)."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.subsystems.search import (
    SearchResult,
    get_recorded_calls,
    reset_recorded_calls,
    search,
)


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "asterism.db")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _reset_recorded() -> None:
    reset_recorded_calls()
    yield
    reset_recorded_calls()


def _insert_goal(
    conn: sqlite3.Connection,
    *,
    slug: str,
    lean_path: str,
    status: str = "open",
    commit_state: str = "live",
) -> int:
    conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, "
        "commit_state, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("ex", slug, lean_path, "root", "theorem", status,
         commit_state, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestArgValidation:
    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown scope"):
            search("q", scope="bogus", kind="find_lemmas")

    def test_invalid_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown kind"):
            search("q", scope="mathlib", kind="bogus")

    def test_local_goals_requires_conn(self) -> None:
        with pytest.raises(ValueError, match="local_goals scope requires conn"):
            search("q", scope="local_goals", kind="find_lemmas", conn=None)


# ---------------------------------------------------------------------------
# SEARCH_MOCK env hook
# ---------------------------------------------------------------------------


class TestSearchMock:
    def test_record_calls_captures_args(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_MOCK", "record_calls")
        r1 = search("foo", scope="mathlib", kind="find_lemmas")
        r2 = search("bar", scope="library", kind="find_pattern")
        assert r1.results == []
        assert r2.results == []
        recorded = get_recorded_calls()
        assert len(recorded) == 2
        assert recorded[0] == {"query": "foo", "scope": "mathlib", "kind": "find_lemmas"}
        assert recorded[1] == {"query": "bar", "scope": "library", "kind": "find_pattern"}

    def test_force_miss_returns_empty(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_MOCK", "force_miss")
        r = search("foo", scope="mathlib", kind="find_lemmas")
        assert r.results == []
        assert r.from_cache is False

    def test_force_hit_returns_synthetic_entry(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_MOCK", "force_hit")
        r = search("foo", scope="mathlib", kind="find_lemmas")
        assert len(r.results) == 1
        assert r.results[0]["name"] == "_mock_hit"

    def test_unknown_mock_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_MOCK", "bogus")
        with pytest.raises(ValueError, match="unknown SEARCH_MOCK value"):
            search("foo", scope="mathlib", kind="find_lemmas")


# ---------------------------------------------------------------------------
# mathlib / library scope (subprocess)
# ---------------------------------------------------------------------------


class TestMathlibScope:
    def test_subprocess_called_with_args(self, tmp_path) -> None:
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"results": [{"name": "Nat.add_comm",
                                                "type": "...", "score": 0.9}]})
        fake.stderr = ""
        with patch(
            "Tooling.subsystems.search.subprocess.run", return_value=fake
        ) as mock_run:
            r = search("Nat.add", scope="mathlib", kind="find_lemmas",
                       lake_cwd=tmp_path)
        assert r.results[0]["name"] == "Nat.add_comm"
        cmd = mock_run.call_args.args[0]
        assert "--scope" in cmd and "mathlib" in cmd
        assert "--query" in cmd and "Nat.add" in cmd

    def test_no_json_output_raises(self, tmp_path) -> None:
        """Silent-failure red line: opaque rc != 0 + no JSON → raise."""
        fake = MagicMock()
        fake.returncode = 1
        fake.stdout = "lake build failed"
        fake.stderr = "import not found"
        with patch("Tooling.subsystems.search.subprocess.run", return_value=fake):
            with pytest.raises(RuntimeError, match="no JSON output"):
                search("q", scope="mathlib", kind="find_lemmas",
                       lake_cwd=tmp_path)

    def test_results_not_a_list_raises(self, tmp_path) -> None:
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"results": "not a list"})
        fake.stderr = ""
        with patch("Tooling.subsystems.search.subprocess.run", return_value=fake):
            with pytest.raises(RuntimeError, match="not a list"):
                search("q", scope="mathlib", kind="find_lemmas",
                       lake_cwd=tmp_path)

    def test_subprocess_timeout_raises(self, tmp_path) -> None:
        with patch(
            "Tooling.subsystems.search.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="lake", timeout=30.0),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                search("q", scope="mathlib", kind="find_lemmas",
                       lake_cwd=tmp_path)


class TestLibraryScope:
    """P6.x patch 28: library scope is DB-backed (proved siblings)."""

    def test_requires_conn(self) -> None:
        with pytest.raises(ValueError, match="library scope requires conn"):
            search("q", scope="library", kind="find_lemmas")

    def test_empty_problem_scope_returns_empty(self, db) -> None:
        _insert_goal(db, slug="add_zero", lean_path="path/g1.lean",
                     status="proved")
        r = search("q", scope="library", kind="find_lemmas",
                   conn=db, problem_scope="")
        assert r.results == []

    def test_returns_proved_siblings(self, db) -> None:
        # All inserted under problem='ex' by _insert_goal helper.
        _insert_goal(db, slug="open_g", lean_path="path/o.lean",
                     status="open")
        _insert_goal(db, slug="proved_g", lean_path="path/p.lean",
                     status="proved")
        # Patch in 'question' so we can verify it surfaces as 'type'.
        db.execute("UPDATE goals SET question = ? WHERE slug = ?",
                   ("∀ n : ℕ, 0 + n = n", "proved_g"))
        db.commit()
        r = search("ignored", scope="library", kind="find_lemmas",
                   conn=db, problem_scope="ex")
        names = [row["name"] for row in r.results]
        assert names == ["proved_g"]
        assert r.results[0]["type"] == "∀ n : ℕ, 0 + n = n"

    def test_skips_pending_commit_state(self, db) -> None:
        _insert_goal(db, slug="proved_pending", lean_path="path/p.lean",
                     status="proved", commit_state="pending")
        _insert_goal(db, slug="proved_live", lean_path="path/l.lean",
                     status="proved", commit_state="live")
        r = search("q", scope="library", kind="find_lemmas",
                   conn=db, problem_scope="ex")
        slugs = [row["name"] for row in r.results]
        assert "proved_pending" not in slugs
        assert "proved_live" in slugs

    def test_no_subprocess_invoked(self, db) -> None:
        with patch(
            "Tooling.subsystems.search.subprocess.run"
        ) as mock_run:
            search("q", scope="library", kind="find_lemmas",
                   conn=db, problem_scope="ex")
        assert mock_run.call_count == 0


# ---------------------------------------------------------------------------
# local_goals scope (direct SQL)
# ---------------------------------------------------------------------------


class TestLocalGoalsScope:
    def test_returns_matching_goals(self, db, tmp_path) -> None:
        g1 = _insert_goal(db, slug="add_zero", lean_path="path/g1.lean")
        g2 = _insert_goal(db, slug="mul_comm", lean_path="path/g2.lean")
        r = search("add", scope="local_goals", kind="find_subgoals", conn=db)
        ids = [row["id"] for row in r.results]
        assert g1 in ids
        assert g2 not in ids

    def test_skips_non_live_commit_state(self, db) -> None:
        _insert_goal(db, slug="pending_g", lean_path="path/p.lean",
                     commit_state="pending")
        _insert_goal(db, slug="live_g",    lean_path="path/l.lean",
                     commit_state="live")
        r = search("g", scope="local_goals", kind="find_subgoals", conn=db)
        slugs = [row["slug"] for row in r.results]
        assert "pending_g" not in slugs
        assert "live_g" in slugs

    def test_no_subprocess_invoked(self, db) -> None:
        with patch(
            "Tooling.subsystems.search.subprocess.run"
        ) as mock_run:
            search("anything", scope="local_goals", kind="find_subgoals",
                   conn=db)
        assert mock_run.call_count == 0


# ---------------------------------------------------------------------------
# Cache integration
# ---------------------------------------------------------------------------


class TestCacheIntegration:
    def test_cache_hit_skips_subprocess(self, db, tmp_path) -> None:
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"results": [{"name": "X", "type": "T",
                                                "score": 0.5}]})
        fake.stderr = ""
        with patch(
            "Tooling.subsystems.search.subprocess.run", return_value=fake
        ) as mock_run:
            r1 = search("q", scope="mathlib", kind="find_lemmas",
                        conn=db, lake_cwd=tmp_path)
        assert r1.from_cache is False
        assert mock_run.call_count == 1

        with patch(
            "Tooling.subsystems.search.subprocess.run", return_value=fake
        ) as mock_run2:
            r2 = search("q", scope="mathlib", kind="find_lemmas",
                        conn=db, lake_cwd=tmp_path)
        assert r2.from_cache is True
        assert r2.results[0]["name"] == "X"
        assert mock_run2.call_count == 0

    def test_cache_ttl_expired_refetches(self, db, tmp_path) -> None:
        """Pre-write expired cache row → re-fetch via subprocess."""
        # Manually insert an already-expired row.
        expired = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        from Tooling.subsystems.search import _cache_key
        key = _cache_key("q", "mathlib", "find_lemmas")
        with db:
            db.execute(
                "INSERT INTO search_cache "
                "(query_hash, scope, mode, results, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, "mathlib", "find_lemmas",
                 json.dumps([{"name": "stale"}]), expired),
            )

        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"results": [{"name": "fresh", "type": "T",
                                                "score": 0.5}]})
        fake.stderr = ""
        with patch(
            "Tooling.subsystems.search.subprocess.run", return_value=fake
        ) as mock_run:
            r = search("q", scope="mathlib", kind="find_lemmas",
                       conn=db, lake_cwd=tmp_path)
        assert r.results[0]["name"] == "fresh"
        assert r.from_cache is False
        assert mock_run.call_count == 1

    def test_local_goals_results_cached(self, db) -> None:
        _insert_goal(db, slug="cacheme", lean_path="path/c.lean")
        r1 = search("cache", scope="local_goals", kind="find_subgoals", conn=db)
        assert r1.from_cache is False
        r2 = search("cache", scope="local_goals", kind="find_subgoals", conn=db)
        assert r2.from_cache is True
        assert r2.results == r1.results


# ---------------------------------------------------------------------------
# Skipped: real lake-env integration
# ---------------------------------------------------------------------------


class TestRealLakeIntegration:
    @pytest.mark.skip(reason="manual gate: requires real lake env (search.lean stub)")
    def test_real_search_lean_returns_empty_results(self) -> None:
        pass
