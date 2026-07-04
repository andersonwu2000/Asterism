"""v17 queue contract — scope + lease + payload (arch-review task #3).

The pre-v17 queue relied on "one dispatcher at a time" as an unenforced
discipline: recovery cleared the WHOLE table (#74), pop took the global
max regardless of scope, and cross-process in-flight state was invisible
(each daemon's in-memory `running` set only). These tests pin the
mechanized replacements.
"""
from __future__ import annotations

import os
import sqlite3

from Tooling.state import db, recovery


def _mem() -> sqlite3.Connection:
    conn = db.connect(":memory:")
    db.init_schema(conn)
    return conn


def _seed(conn, *problems):
    for p in problems:
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at,"
            " bootstrap_done) VALUES (?, 'm', ?, 1)", (p, db.now()))
    conn.commit()


# ---------------------------------------------------------------------
# lease claim
# ---------------------------------------------------------------------

def test_pop_claims_not_deletes_and_second_popper_gets_disjoint_row():
    """Two concurrent poppers (distinct lease owners) never receive the
    same row — the cross-process double-dispatch guard. Rows survive the
    pop (lease, not delete)."""
    conn = _mem()
    _seed(conn, "p")
    db.enqueue(conn, kind="Builder", target_id="1", problem="p", priority=5)
    db.enqueue(conn, kind="Builder", target_id="2", problem="p", priority=1)
    a = db.pop_queue(conn, lease_owner=111)
    b = db.pop_queue(conn, lease_owner=222)
    assert a["target_id"] == "1" and b["target_id"] == "2"   # priority order
    assert db.pop_queue(conn, lease_owner=333) is None       # all claimed
    assert db.queue_size(conn) == 2                          # nothing deleted


def test_leased_rows_still_count_as_in_queue():
    """Reminder #1: a claimed-but-unfinished row must still read as
    'in queue' for every enqueue-side dedup, or refill re-enqueues a
    duplicate while it runs."""
    conn = _mem()
    _seed(conn, "p")
    db.enqueue(conn, kind="Strategist", target_id="p", problem="p",
               target_kind="Problem")
    db.pop_queue(conn)                                       # claim it
    assert db.is_in_queue(conn, target_id="p", kind="Strategist")
    assert db.queue_contains(conn, kind="Strategist", target_id="p")
    assert db.queue_count(conn, target_id="p", kind="Strategist") == 1


def test_complete_queue_row_releases_for_good():
    conn = _mem()
    _seed(conn, "p")
    db.enqueue(conn, kind="Builder", target_id="1", problem="p")
    row = db.pop_queue(conn)
    db.complete_queue_row(conn, int(row["id"]))
    assert db.queue_size(conn) == 0
    assert not db.is_in_queue(conn, target_id="1", kind="Builder")


def test_release_expired_leases_dead_pid_or_ttl():
    """Reclaim condition is 'owner dead OR lease older than TTL' — the
    TTL half guards against Windows PID reuse (a recycled PID reads as
    alive)."""
    conn = _mem()
    _seed(conn, "p")
    for t in ("1", "2", "3"):
        db.enqueue(conn, kind="Builder", target_id=t, problem="p")
    r1 = db.pop_queue(conn, lease_owner=101)   # will be "dead"
    r2 = db.pop_queue(conn, lease_owner=102)   # alive, fresh — kept
    r3 = db.pop_queue(conn, lease_owner=103)   # "alive" but TTL-expired
    conn.execute("UPDATE queue SET leased_at = '2000-01-01T00:00:00'"
                 " WHERE id = ?", (r3["id"],))
    conn.commit()
    alive = {102: True, 103: True, 101: False}
    n = db.release_expired_leases(
        conn, ttl_sec=3600.0, pid_alive=lambda pid: alive.get(pid, False))
    assert n == 2
    owners = {r["target_id"]: r["owner_pid"] for r in conn.execute(
        "SELECT target_id, owner_pid FROM queue")}
    assert owners[str(r1["target_id"])] is None      # dead → released
    assert owners[str(r2["target_id"])] == 102       # alive+fresh → kept
    assert owners[str(r3["target_id"])] is None      # TTL → released
    # released rows are claimable again
    assert db.pop_queue(conn, lease_owner=999) is not None


# ---------------------------------------------------------------------
# scope
# ---------------------------------------------------------------------

def test_scoped_pop_only_claims_own_problem():
    conn = _mem()
    _seed(conn, "mine", "theirs")
    db.enqueue(conn, kind="Builder", target_id="1", problem="theirs",
               priority=99)
    db.enqueue(conn, kind="Builder", target_id="2", problem="mine")
    row = db.pop_queue(conn, scope="mine")
    assert row["target_id"] == "2"                   # not the higher-prio one
    assert db.pop_queue(conn, scope="mine") is None  # mine drained
    # theirs untouched and still claimable
    assert db.pop_queue(conn, scope="theirs")["target_id"] == "1"


def test_unscoped_and_scoped_concurrency_no_double_dispatch():
    """Reminder #2: an unscoped daemon pops the whole table — it MAY take
    another scope's row, but the lease makes that visible: the scoped
    daemon can no longer claim it (no double dispatch, not worse than
    single-daemon semantics)."""
    conn = _mem()
    _seed(conn, "s")
    db.enqueue(conn, kind="Builder", target_id="1", problem="s")
    grabbed = db.pop_queue(conn, scope=None, lease_owner=1)   # unscoped
    assert grabbed is not None
    assert db.pop_queue(conn, scope="s", lease_owner=2) is None
    # and the scoped daemon's dedup still sees it queued
    assert db.is_in_queue(conn, target_id="1", kind="Builder")


def test_flush_queue_kind_scoped_and_spares_leased():
    conn = _mem()
    _seed(conn, "a", "b")
    db.enqueue(conn, kind="Backward", target_id="1", problem="a")
    db.enqueue(conn, kind="Backward", target_id="2", problem="a")
    db.enqueue(conn, kind="Backward", target_id="3", problem="b")
    db.pop_queue(conn, scope="a")                    # lease one of a's
    n = db.flush_queue_kind(conn, kind="Backward", scope="a")
    assert n == 1                                    # only a's UNLEASED row
    remaining = {r["target_id"] for r in conn.execute(
        "SELECT target_id FROM queue")}
    assert remaining == {"1", "3"}                   # leased + other scope


# ---------------------------------------------------------------------
# startup recovery (#74)
# ---------------------------------------------------------------------

def test_recovery_scoped_clear_spares_other_scope_and_live_leases(
        monkeypatch):
    """#74's structural fix: daemon A's startup clears ITS scope's rows
    (unleased + dead-owner leased) and leaves (a) other scopes' backlog
    and (b) rows leased by a LIVE concurrent dispatcher."""
    conn = _mem()
    _seed(conn, "mine", "theirs")
    db.enqueue(conn, kind="Builder", target_id="1", problem="mine")
    db.enqueue(conn, kind="Builder", target_id="2", problem="theirs")
    db.enqueue(conn, kind="Builder", target_id="3", problem="mine")
    db.enqueue(conn, kind="Builder", target_id="4", problem="mine")
    # row 3: leased by a DEAD pid; row 4: leased by a LIVE one
    conn.execute("UPDATE queue SET owner_pid=101, leased_at=? "
                 "WHERE target_id='3'", (db.now(),))
    conn.execute("UPDATE queue SET owner_pid=102, leased_at=? "
                 "WHERE target_id='4'", (db.now(),))
    conn.commit()
    from Tooling.agent import sandbox
    monkeypatch.setattr(sandbox, "_pid_alive",
                        lambda pid: pid == 102)
    recovery.recover_at_startup(conn, scope="mine")
    remaining = {r["target_id"] for r in conn.execute(
        "SELECT target_id FROM queue")}
    # 1 (mine, unleased) cleared; 3 (mine, dead lease) cleared;
    # 2 (theirs) spared; 4 (mine, LIVE lease) spared.
    assert remaining == {"2", "4"}


def test_recovery_unscoped_still_spares_live_leases(monkeypatch):
    conn = _mem()
    _seed(conn, "p")
    db.enqueue(conn, kind="Builder", target_id="1", problem="p")
    db.enqueue(conn, kind="Builder", target_id="2", problem="p")
    conn.execute("UPDATE queue SET owner_pid=?, leased_at=? "
                 "WHERE target_id='2'", (os.getpid(), db.now()))
    conn.commit()
    from Tooling.agent import sandbox
    monkeypatch.setattr(sandbox, "_pid_alive", lambda pid: True)
    recovery.recover_at_startup(conn, scope=None)
    remaining = [r["target_id"] for r in conn.execute(
        "SELECT target_id FROM queue")]
    assert remaining == ["2"]


# ---------------------------------------------------------------------
# payload (librarian per-file units)
# ---------------------------------------------------------------------

def test_payload_rides_json_and_contains_discriminates():
    conn = _mem()
    _seed(conn, "p")
    db.enqueue(conn, kind="Librarian", target_id="p", problem="p",
               target_kind="Problem", payload={"file": "Library/P/a.lean"})
    # per-file dedup sees exactly its unit
    assert db.queue_contains(conn, kind="Librarian", target_id="p",
                             payload_file="Library/P/a.lean")
    assert not db.queue_contains(conn, kind="Librarian", target_id="p",
                                 payload_file="Library/P/b.lean")
    # the serial-phase dedup must NOT mistake a per-file unit for its
    # own plain row (same target_id since v17)
    assert not db.queue_contains(conn, kind="Librarian", target_id="p",
                                 no_payload=True)
    db.enqueue(conn, kind="Librarian", target_id="p", problem="p",
               target_kind="Problem")
    assert db.queue_contains(conn, kind="Librarian", target_id="p",
                             no_payload=True)
