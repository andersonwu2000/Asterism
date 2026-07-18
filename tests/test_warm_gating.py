"""NL-first startup (2026-07-18): while the gateway warms in the
background, only NL queue kinds (Strategist, Scholar) dispatch; Lean
kinds stay queued WITHOUT losing their queue position (no lease, no
discard). Guards: pop_queue's exclude_kinds filter and the
LEAN_QUEUE_KINDS partition against the queue-kind enum.
"""
from pathlib import Path

import pytest

from Tooling.core import dispatcher
from Tooling.state import db


# The queue table's CHECK enum (state/db.py SCHEMA). A new queue kind
# must pick a side of the partition — this pin forces the choice.
_QUEUE_KIND_ENUM = {"Builder", "Backward", "Verify", "Strategist",
                    "Forward", "Librarian", "Scholar"}
_NL_KINDS = {"Strategist", "Scholar"}


def test_lean_kind_partition_pinned():
    lean = set(dispatcher.LEAN_QUEUE_KINDS)
    assert lean | _NL_KINDS == _QUEUE_KIND_ENUM
    assert lean & _NL_KINDS == set()


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at,"
              " bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def _enqueue(c, kind: str, priority: int, target: str) -> None:
    c.execute(
        "INSERT INTO queue (kind, target_id, target_kind, priority,"
        " problem, created_at) VALUES (?,?, 'Problem', ?, 'p', ?)",
        (kind, target, priority, db.now()))
    c.commit()


def test_pop_queue_exclude_kinds_skips_but_keeps_rows(conn):
    # Forward outranks Strategist by priority; the exclusion must
    # yield the Strategist anyway and leave the Forward unleased.
    _enqueue(conn, "Forward", 9, "p")
    _enqueue(conn, "Strategist", 1, "p")

    row = db.pop_queue(conn,
                       exclude_kinds=dispatcher.LEAN_QUEUE_KINDS)
    assert row is not None and row["kind"] == "Strategist"

    # The Forward row is untouched: still claimable once the filter
    # lifts (gateway ready), and popped first by priority. (pop_queue
    # returns the pre-claim snapshot, so read the lease from the DB.)
    row2 = db.pop_queue(conn)
    assert row2 is not None and row2["kind"] == "Forward"
    assert conn.execute(
        "SELECT owner_pid FROM queue WHERE id = ?", (row2["id"],)
    ).fetchone()[0] is not None


def test_pop_queue_exclude_kinds_respects_scope(conn):
    conn.execute("INSERT INTO problems (name, manifest_path, created_at,"
                 " bootstrap_done) VALUES ('q','',?,1)", (db.now(),))
    conn.commit()
    _enqueue(conn, "Strategist", 5, "p")
    conn.execute(
        "INSERT INTO queue (kind, target_id, target_kind, priority,"
        " problem, created_at) VALUES ('Strategist','q','Problem',9,"
        " 'q', ?)", (db.now(),))
    conn.commit()

    row = db.pop_queue(conn, scope="p",
                       exclude_kinds=dispatcher.LEAN_QUEUE_KINDS)
    assert row is not None and row["problem"] == "p"


def test_pop_queue_all_excluded_returns_none(conn):
    _enqueue(conn, "Builder", 5, "p")
    assert db.pop_queue(
        conn, exclude_kinds=dispatcher.LEAN_QUEUE_KINDS) is None
    # Nothing was leased in passing.
    assert conn.execute(
        "SELECT COUNT(*) FROM queue WHERE owner_pid IS NOT NULL"
    ).fetchone()[0] == 0
