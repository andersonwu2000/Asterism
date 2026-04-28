"""Unit tests for Tooling/locks.py (P6 C40)."""
from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.locks import library_lock


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    conn = connect(p)
    init_schema(conn)
    conn.close()
    return p


class TestLibraryLockBasic:
    def test_lock_commits_on_normal_exit(self, db_path):
        conn = connect(db_path)
        try:
            with library_lock(conn):
                conn.execute(
                    "INSERT INTO events (kind, payload, ts) "
                    "VALUES ('cascade', '{}', datetime('now'))"
                )
            row = conn.execute("SELECT count(*) FROM events").fetchone()[0]
            assert row == 1
        finally:
            conn.close()

    def test_lock_rolls_back_on_exception(self, db_path):
        conn = connect(db_path)
        try:
            with pytest.raises(RuntimeError, match="boom"):
                with library_lock(conn):
                    conn.execute(
                        "INSERT INTO events (kind, payload, ts) "
                        "VALUES ('cascade', '{}', datetime('now'))"
                    )
                    raise RuntimeError("boom")
            row = conn.execute("SELECT count(*) FROM events").fetchone()[0]
            assert row == 0  # rolled back
        finally:
            conn.close()

    def test_invalid_mode_raises(self, db_path):
        conn = connect(db_path)
        try:
            with pytest.raises(ValueError, match="DEFERRED.*IMMEDIATE.*EXCLUSIVE"):
                with library_lock(conn, mode="bogus"):
                    pass
        finally:
            conn.close()


class TestLibraryLockContention:
    def test_second_connection_blocks_then_acquires(self, db_path):
        """spike-022 D-22-1 verification: second IMMEDIATE acquire on
        the same DB blocks until the first commits, then succeeds."""
        conn1 = connect(db_path)
        try:
            results: list = []

            def writer2():
                # SQLite connection objects can only be used in the
                # thread that created them — open conn2 inside writer2.
                conn2 = sqlite3.connect(str(db_path), timeout=5.0)
                try:
                    with library_lock(conn2):
                        conn2.execute(
                            "INSERT INTO events (kind, payload, ts) "
                            "VALUES ('cascade', '{\"by\":\"conn2\"}', "
                            "datetime('now'))"
                        )
                    results.append("conn2_done")
                except sqlite3.OperationalError as exc:
                    results.append(f"conn2_err: {exc}")
                finally:
                    conn2.close()

            with library_lock(conn1):
                conn1.execute(
                    "INSERT INTO events (kind, payload, ts) "
                    "VALUES ('cascade', '{\"by\":\"conn1\"}', "
                    "datetime('now'))"
                )
                t = threading.Thread(target=writer2)
                t.start()
                # Give conn2 time to attempt + block on the lock
                time.sleep(0.2)
                # conn1 still holds — conn2 should not have completed
                assert results == []
            # After conn1 commits, conn2 should be able to acquire
            t.join(timeout=10)
            assert results == ["conn2_done"]
            cnt = conn1.execute("SELECT count(*) FROM events").fetchone()[0]
            assert cnt == 2
        finally:
            conn1.close()

    def test_quick_timeout_raises_database_locked(self, db_path):
        """If the second connection has timeout=0, it gets
        sqlite3.OperationalError("database is locked") immediately
        instead of blocking — the failure mode operators should
        retry on."""
        conn1 = connect(db_path)
        conn2 = sqlite3.connect(str(db_path), timeout=0.0)
        try:
            with library_lock(conn1):
                with pytest.raises(sqlite3.OperationalError,
                                    match="locked"):
                    with library_lock(conn2):
                        pass
        finally:
            conn1.close()
            conn2.close()
