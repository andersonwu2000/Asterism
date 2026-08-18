"""`goal_events` — every goal status transition, append-only (v36).

Built for the Timeline the frontend is assembling, but the reason it is
a table and not a derived view is that `goals.updated_at` cannot answer
"when did this goal move": attempts+1, `is_deliverable` and
`integrity_verified` all bump it, measured p90 18 minutes and worst case
43 minutes away from the transition it would be read as.
"""
import sqlite3

import pytest

from Tooling.state import db, transitions


@pytest.fixture
def conn(tmp_path, monkeypatch):
    # chdir FIRST: `db.connect()` resolves DB_PATH against the cwd, so a
    # fixture that skips this opens the operator's live asterism.db and
    # migrates it (learned the hard way while writing these tests).
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES ('p', ?)", (db.now(),))
    c.commit()
    return c


def _goal(conn, slug="g", status="open"):
    return db.insert_goal(
        conn, problem="p", slug=slug, lean_path=f"p/proofs/L_{slug}.lean",
        statement="1 = 1", origin="forward", status=status)


def _events(conn, goal_id):
    return list(conn.execute(
        "SELECT from_status, to_status, event, reason, at FROM goal_events"
        " WHERE goal_id = ? ORDER BY id", (goal_id,)))


def test_a_transition_records_both_ends_and_its_label(conn):
    gid = _goal(conn)
    transitions.apply_goal_transition(
        conn, gid, "attempting", event="dispatch", reason="")
    rows = _events(conn, gid)
    assert len(rows) == 1
    assert rows[0]["from_status"] == "open"
    assert rows[0]["to_status"] == "attempting"
    assert rows[0]["event"] == "dispatch"


def test_the_log_is_append_only_across_a_goals_whole_life(conn):
    gid = _goal(conn)
    transitions.apply_goal_transition(conn, gid, "attempting", event="a")
    transitions.apply_goal_transition(conn, gid, "open", event="b")
    transitions.apply_goal_transition(conn, gid, "attempting", event="c")
    assert [(r["from_status"], r["to_status"]) for r in _events(conn, gid)] == [
        ("open", "attempting"), ("attempting", "open"),
        ("open", "attempting")]


def test_the_write_sink_logs_even_when_the_validator_is_bypassed(conn):
    """The hook sits on `update_goal_status`, not on
    `apply_goal_transition`, because `amend.py` writes straight to the
    sink: it flips a rewritten root back to 'frozen' from whatever state
    it was in, and only open→frozen is a legal edge, so it cannot be
    routed through the validator. Hooking the validator would have
    dropped exactly the operator's own transitions."""
    gid = _goal(conn, status="attempting")
    db.update_goal_status(conn, gid, "frozen", event="operator_amend",
                          reason="root statement rewritten")
    rows = _events(conn, gid)
    assert len(rows) == 1
    assert (rows[0]["from_status"], rows[0]["to_status"]) == (
        "attempting", "frozen")
    assert rows[0]["event"] == "operator_amend"


def test_the_event_time_is_the_transition_not_updated_at(conn):
    """`at` is stamped in the same call as the UPDATE, so the two agree
    for THIS write — the point being that later unrelated bumps to
    `updated_at` (attempts, is_deliverable) move that column and leave
    the event's own timestamp alone."""
    gid = _goal(conn)
    transitions.apply_goal_transition(conn, gid, "attempting", event="x")
    at = _events(conn, gid)[0]["at"]
    assert conn.execute(
        "SELECT updated_at FROM goals WHERE id = ?", (gid,),
    ).fetchone()["updated_at"] == at

    db.increment_goal_attempts(conn, gid)
    later = conn.execute(
        "SELECT updated_at FROM goals WHERE id = ?", (gid,),
    ).fetchone()["updated_at"]
    assert _events(conn, gid)[0]["at"] == at       # the event did not move
    assert later >= at                             # the column did


def test_reset_takes_the_events_with_the_goals(conn):
    """`asterism reset` drops the problem's goals by id. Without the
    cascade the events would outlive them and read as this run's history
    — the cross-run leak #167 records for `.groups/`."""
    gid = _goal(conn)
    transitions.apply_goal_transition(conn, gid, "attempting", event="x")
    assert _events(conn, gid)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM goals WHERE id = ?", (gid,))
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) c FROM goal_events").fetchone()["c"] == 0


def test_a_caller_without_a_label_still_gets_a_row(conn):
    """`event` is forensic sugar; the transition itself is the record.
    A caller with nothing to say must not cost the timeline an entry."""
    gid = _goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    rows = _events(conn, gid)
    assert len(rows) == 1 and rows[0]["event"] == "" and rows[0]["reason"] == ""
