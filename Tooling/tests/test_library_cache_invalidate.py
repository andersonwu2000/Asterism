"""Tests for invalidate_for_library_write (P6 C43)."""
from __future__ import annotations

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.subsystems.cache import invalidate_for_library_write


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    conn = connect(p)
    init_schema(conn)
    conn.close()
    return p


@pytest.fixture
def db(db_path):
    conn = connect(db_path)
    yield conn
    conn.close()


def _seed(conn, *, query_hash: str, scope: str, mode: str = "find_lemmas") -> None:
    with conn:
        conn.execute(
            "INSERT INTO search_cache (query_hash, scope, mode, results, "
            "expires_at) VALUES (?, ?, ?, '[]', '2099-01-01')",
            (query_hash, scope, mode),
        )


class TestInvalidateForLibraryWrite:
    def test_deletes_library_scope_rows(self, db):
        _seed(db, query_hash="q1", scope="library_theorems")
        _seed(db, query_hash="q2", scope="mathlib_library_v2")
        deleted = invalidate_for_library_write(db)
        assert deleted == 2
        remaining = db.execute(
            "SELECT count(*) FROM search_cache"
        ).fetchone()[0]
        assert remaining == 0

    def test_preserves_non_library_scopes(self, db):
        """impl §2.3: library invalidation MUST NOT affect local_goals
        / dedupe / inventory / mathlib (non-library) scopes."""
        _seed(db, query_hash="q_lib", scope="library_theorems")
        _seed(db, query_hash="q_local", scope="local_goals")
        _seed(db, query_hash="q_dedupe", scope="dedupe", mode="dedupe")
        _seed(db, query_hash="q_inv", scope="inventory")
        deleted = invalidate_for_library_write(db)
        assert deleted == 1
        rows = db.execute(
            "SELECT query_hash FROM search_cache ORDER BY query_hash"
        ).fetchall()
        names = [r[0] for r in rows]
        assert names == ["q_dedupe", "q_inv", "q_local"]

    def test_empty_cache_returns_zero(self, db):
        deleted = invalidate_for_library_write(db)
        assert deleted == 0

    def test_partial_match_substring(self, db):
        """LIKE '%library%' matches any scope containing the substring."""
        _seed(db, query_hash="q1", scope="library")
        _seed(db, query_hash="q2", scope="library_constructions")
        _seed(db, query_hash="q3", scope="my_library_view")
        _seed(db, query_hash="q4", scope="lib")  # no 'library' substring
        deleted = invalidate_for_library_write(db)
        assert deleted == 3
