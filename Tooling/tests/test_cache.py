"""Unit + integration tests for Tooling.subsystems.cache (P3 C21)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from Tooling.commit import CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.subsystems.cache import invalidate_for_goals_write


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "asterism.db")
    init_schema(conn)
    yield conn
    conn.close()


def _seed_cache_row(
    conn: sqlite3.Connection,
    *,
    query_hash: str,
    scope: str,
    mode: str,
    results: list | None = None,
    ttl_secs: float = 3600.0,
) -> None:
    expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_secs)).isoformat()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_cache "
            "(query_hash, scope, mode, results, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (query_hash, scope, mode, json.dumps(results or []), expires),
        )


def _row_count(conn: sqlite3.Connection, *, scope_like: str | None = None,
               mode: str | None = None) -> int:
    where, params = [], []
    if scope_like is not None:
        where.append("scope LIKE ?")
        params.append(scope_like)
    if mode is not None:
        where.append("mode = ?")
        params.append(mode)
    sql = "SELECT COUNT(*) FROM search_cache"
    if where:
        sql += " WHERE " + " AND ".join(where)
    return conn.execute(sql, params).fetchone()[0]


# ---------------------------------------------------------------------------
# Direct invalidate function unit tests
# ---------------------------------------------------------------------------


class TestInvalidateUnit:
    def test_kills_local_goals_rows(self, db) -> None:
        _seed_cache_row(db, query_hash="h1", scope="local_goals", mode="find_lemmas")
        _seed_cache_row(db, query_hash="h2", scope="mathlib", mode="find_lemmas")
        _seed_cache_row(db, query_hash="h3", scope="dedupe", mode="dedupe")
        deleted = invalidate_for_goals_write(db)
        # 1 local_goals + 1 dedupe = 2 deleted; mathlib stays
        assert deleted == 2
        assert _row_count(db, scope_like="%local_goals%") == 0
        assert _row_count(db, mode="dedupe") == 0
        assert _row_count(db, scope_like="mathlib") == 1

    def test_kills_dedupe_rows_regardless_of_scope(self, db) -> None:
        """Spec §2.3: dedupe filter is `WHERE mode='dedupe'` (cross-Problem)."""
        _seed_cache_row(db, query_hash="h1", scope="any_scope_value",
                        mode="dedupe")
        _seed_cache_row(db, query_hash="h2", scope="mathlib", mode="dedupe")
        invalidate_for_goals_write(db)
        assert _row_count(db, mode="dedupe") == 0

    def test_no_match_leaves_rows_intact(self, db) -> None:
        _seed_cache_row(db, query_hash="h1", scope="mathlib", mode="find_lemmas")
        _seed_cache_row(db, query_hash="h2", scope="library", mode="find_pattern")
        deleted = invalidate_for_goals_write(db)
        assert deleted == 0
        assert _row_count(db) == 2

    def test_problem_arg_currently_unused(self, db) -> None:
        """`problem` parameter is reserved for P6 problem_scope filter; for P3
        it's unused but accepted in the signature."""
        _seed_cache_row(db, query_hash="h1", scope="local_goals", mode="x")
        # Both calls behave the same (P1 spec gap).
        invalidate_for_goals_write(db, problem="ex")
        assert _row_count(db) == 0

    def test_empty_table_returns_zero(self, db) -> None:
        assert invalidate_for_goals_write(db) == 0


# ---------------------------------------------------------------------------
# CommitWriter integration: finalize('goals', ...) triggers invalidation
# ---------------------------------------------------------------------------


class TestCommitWriterHook:
    def test_finalize_goals_invalidates_cache(self, db) -> None:
        _seed_cache_row(db, query_hash="h1", scope="local_goals", mode="find_lemmas")
        _seed_cache_row(db, query_hash="h2", scope="dedupe", mode="dedupe")

        writer = CommitWriter(db)
        gid = writer.begin("goals", "insert", {
            "problem": "ex", "slug": "g", "lean_path": "p.lean",
            "origin": "root", "kind": "theorem", "status": "open",
        })
        writer.finalize("goals", gid, {})

        assert _row_count(db, scope_like="%local_goals%") == 0
        assert _row_count(db, mode="dedupe") == 0

    def test_finalize_strategies_does_not_invalidate(self, db) -> None:
        """Cache invalidation only fires for goals (impl §2.3); other tables
        don't trigger it."""
        _seed_cache_row(db, query_hash="h1", scope="local_goals", mode="find_lemmas")

        writer = CommitWriter(db)
        gid = writer.begin("goals", "insert", {
            "problem": "ex", "slug": "g", "lean_path": "p.lean",
            "origin": "root", "kind": "theorem", "status": "open",
        })
        writer.finalize("goals", gid, {})  # this DOES invalidate
        # Re-seed to test strategies finalize alone
        _seed_cache_row(db, query_hash="h2", scope="local_goals", mode="x")

        sid = writer.begin("strategies", "insert", {
            "goal_id": gid, "lean_path": "s.lean", "status": "proposed",
        })
        writer.finalize("strategies", sid, {})

        # h2 still there (strategies finalize did NOT invalidate)
        assert _row_count(db, scope_like="%local_goals%") == 1


# ---------------------------------------------------------------------------
# Scheduler integration: 3 direct UPDATE sites trigger invalidation
# ---------------------------------------------------------------------------


def _insert_goal(conn, *, slug, status="open", depth=0, problem="ex"):
    conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, depth, "
        "commit_state, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"path/{slug}.lean", "root", "theorem", status,
         depth, "live", _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestSchedulerInvalidationHooks:
    """Three scheduler.py UPDATE sites must invalidate cache:
      - _update_goal_proved (line ~864)
      - _run_structural_refill D_max shelve (line ~568)
      - _cascade_strategy_dead all-dead shelve (line ~407)
    """

    def test_update_goal_proved_invalidates(self, db, tmp_path) -> None:
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="g_proved")
        _seed_cache_row(db, query_hash="h1", scope="local_goals", mode="x")
        _seed_cache_row(db, query_hash="h2", scope="dedupe", mode="dedupe")

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        reactor._update_goal_proved(gid, '{"type":"classical"}', '[]')

        assert _row_count(db, scope_like="%local_goals%") == 0
        assert _row_count(db, mode="dedupe") == 0

    def test_d_max_shelve_invalidates(self, db, tmp_path) -> None:
        """Structural refill D_max=12 path."""
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="g_deep", depth=12)
        _seed_cache_row(db, query_hash="h1", scope="local_goals", mode="x")

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        reactor._run_structural_refill()

        # depth=12 → shelved + cache killed
        status = db.execute("SELECT status FROM goals WHERE id=?", (gid,)).fetchone()[0]
        assert status == "shelved"
        assert _row_count(db, scope_like="%local_goals%") == 0

    def test_all_strategies_dead_shelve_invalidates(self, db, tmp_path) -> None:
        """_cascade Strategy dead → all-dead → shelve goal path."""
        from Tooling.pipelines.builder import BuilderResult
        from Tooling.scheduler import Reactor, ReactorConfig

        gid = _insert_goal(db, slug="g_alldead")
        with db:
            db.execute(
                "INSERT INTO strategies "
                "(goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?,?,?,?,?)",
                (gid, "path/s.lean", "proposed", "live", _NOW),
            )
            sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        _seed_cache_row(db, query_hash="h1", scope="local_goals", mode="x")
        _seed_cache_row(db, query_hash="h2", scope="dedupe", mode="dedupe")

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        # Builder exhausted → strategy marked dead → all-dead → goal shelved
        # (the shelve UPDATE is what triggers cache invalidation)
        reactor._cascade_builder(sid, BuilderResult(outcome="exhausted"))

        status = db.execute(
            "SELECT status FROM goals WHERE id=?", (gid,)
        ).fetchone()[0]
        assert status == "shelved"
        assert _row_count(db, scope_like="%local_goals%") == 0
        assert _row_count(db, mode="dedupe") == 0
