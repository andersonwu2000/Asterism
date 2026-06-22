"""Tests for the centralised state-transition gateway (Tooling/state/transitions.py).

Covers the registry's internal consistency and the checked-mutator contract
(legal edge writes, idempotent self-edges, strict-mode rejection, lenient-mode
logging, unknown-state guard, missing-row no-op). The schema<->canonical-enum
binding lives in test_transitions_binding (#11 P4); here we only assert that the
canonical state sets cover every registry endpoint and round-trip through the
DB CHECK constraint.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, transitions


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    """In-memory DB with schema + a seeded 'p' problem (so goals' FK to
    problems(name) is satisfied). Mirrors test_phase2_cascade.py's fixture."""
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


# --------------------------------------------------------------------------- #
# Local insert helpers (mirror test_phase2_cascade.py conventions)
# --------------------------------------------------------------------------- #

def _insert_goal(conn: sqlite3.Connection, *, status: str = "open",
                 slug: str = "g") -> int:
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement, kind, origin,"
        " status, depth, attempts, entry_kind, integrity_verified, detached,"
        " created_at, updated_at)"
        " VALUES ('p', ?, ?, 'T', 'theorem', 'backward', ?, 0, 0, 'Builder',"
        " 0, 0, ?, ?)",
        (slug, f"Problems/p/proofs/L_{slug}.lean", status, db.now(), db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _insert_strategy(conn: sqlite3.Connection, *, goal_id: int,
                     status: str = "proposed") -> int:
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, '', '', ?, '', 'test', ?)",
        (goal_id, status, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _gstatus(conn: sqlite3.Connection, gid: int) -> str:
    return str(conn.execute(
        "SELECT status FROM goals WHERE id = ?", (gid,)).fetchone()["status"])


def _sstatus(conn: sqlite3.Connection, sid: int) -> str:
    return str(conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sid,)).fetchone()["status"])


# --------------------------------------------------------------------------- #
# Registry well-formedness
# --------------------------------------------------------------------------- #

def test_goal_edges_endpoints_are_canonical_states():
    for frm, to in transitions.GOAL_EDGES:
        assert frm in transitions.GOAL_STATES, f"bad goal from-state {frm!r}"
        assert to in transitions.GOAL_STATES, f"bad goal to-state {to!r}"


def test_strategy_edges_endpoints_are_canonical_states():
    for frm, to in transitions.STRATEGY_EDGES:
        assert frm in transitions.STRATEGY_STATES, f"bad from-state {frm!r}"
        assert to in transitions.STRATEGY_STATES, f"bad to-state {to!r}"


def test_registry_has_no_self_edges():
    # Self-edges (from == to) are *implicitly* allowed by the mutator; listing
    # them in the registry would be dead weight and mask intent.
    assert not any(f == t for f, t in transitions.GOAL_EDGES)
    assert not any(f == t for f, t in transitions.STRATEGY_EDGES)


def test_canonical_states_round_trip_through_db_check(conn: sqlite3.Connection):
    # Every canonical state must be accepted by the goals.status /
    # strategies.status CHECK constraint (a cheap binding sanity check; the
    # exhaustive schema<->canonical equality is P4's job).
    for i, st in enumerate(sorted(transitions.GOAL_STATES)):
        _insert_goal(conn, status=st, slug=f"g{i}")
    g = _insert_goal(conn, status="open", slug="anchor")
    for st in sorted(transitions.STRATEGY_STATES):
        _insert_strategy(conn, goal_id=g, status=st)


# --------------------------------------------------------------------------- #
# Checked mutator — goal
# --------------------------------------------------------------------------- #

def test_apply_goal_transition_legal_edge_writes(conn: sqlite3.Connection):
    g = _insert_goal(conn, status="open")
    transitions.apply_goal_transition(conn, g, "attempting", event="t")
    assert _gstatus(conn, g) == "attempting"


def test_apply_goal_transition_idempotent_self_edge_allowed(
        conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch):
    # A self-edge is permitted even in strict mode and even though it is not in
    # the registry (re-asserting the same status must never raise).
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")
    g = _insert_goal(conn, status="proved")
    transitions.apply_goal_transition(conn, g, "proved", event="t")
    assert _gstatus(conn, g) == "proved"


def test_apply_goal_transition_illegal_edge_strict_raises(
        conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")
    g = _insert_goal(conn, status="dead")
    with pytest.raises(transitions.IllegalTransition):
        transitions.apply_goal_transition(conn, g, "attempting", event="t")
    # Strict mode raised BEFORE the write — status unchanged.
    assert _gstatus(conn, g) == "dead"


def test_apply_goal_transition_illegal_edge_lenient_logs_and_writes(
        conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture):
    monkeypatch.delenv("ASTERISM_STRICT_TRANSITIONS", raising=False)
    g = _insert_goal(conn, status="dead")
    transitions.apply_goal_transition(conn, g, "attempting", event="probe")
    out = capsys.readouterr().out
    assert "[transition-violation]" in out
    assert "probe" in out
    # Lenient mode performs the write (loud log, no daemon crash).
    assert _gstatus(conn, g) == "attempting"


def test_apply_goal_transition_unknown_state_asserts(conn: sqlite3.Connection):
    g = _insert_goal(conn, status="open")
    with pytest.raises(AssertionError):
        transitions.apply_goal_transition(conn, g, "bogus", event="t")


def test_apply_goal_transition_missing_row_noop(
        conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")
    # No row id 9999 — must not raise (no from-state to validate).
    transitions.apply_goal_transition(conn, 9999, "proved", event="t")


# --------------------------------------------------------------------------- #
# Checked mutator — strategy
# --------------------------------------------------------------------------- #

def test_apply_strategy_transition_legal_edge_writes(conn: sqlite3.Connection):
    g = _insert_goal(conn, status="attempting")
    s = _insert_strategy(conn, goal_id=g, status="proposed")
    transitions.apply_strategy_transition(conn, s, "succeeded", event="t")
    assert _sstatus(conn, s) == "succeeded"


def test_apply_strategy_transition_illegal_edge_strict_raises(
        conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")
    g = _insert_goal(conn, status="open")
    s = _insert_strategy(conn, goal_id=g, status="dead")
    with pytest.raises(transitions.IllegalTransition):
        # dead -> proposed is not a declared strategy edge.
        transitions.apply_strategy_transition(conn, s, "proposed", event="t")
    assert _sstatus(conn, s) == "dead"
