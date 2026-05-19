"""Phase 2 — dispatcher T0/T1 triggers + bfs_refill detached/pending
review handling + awaiting_human gate + queue.decision_id plumbing.

Covers Step 3 acceptance. T2 (cascade enqueue on agent_shelved) is
covered in `tests/test_phase2_cascade.py`.
"""
from __future__ import annotations

import sqlite3
import time as _time
from pathlib import Path

import pytest

from Tooling.core.dispatcher import (
    bfs_refill,
    strategist_triggers,
)
from Tooling.state import db


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    return c


def _insert_problem(conn: sqlite3.Connection, *, name: str,
                    bootstrap_done: int = 0,
                    last_strategist_at: str | None = None) -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done, last_strategist_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now(),
         bootstrap_done, last_strategist_at),
    )
    conn.commit()


def _insert_root(conn: sqlite3.Connection, problem: str,
                 *, status: str = "open") -> int:
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " integrity_verified, detached, created_at, updated_at)"
        " VALUES (?, 'main', ?, 'T', 'theorem', 'root', ?,"
        " 0, 0, 'Backward', 0, 0, ?, ?)",
        (problem, f"Problems/{problem}/Root.lean", status,
         db.now(), db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _insert_sub(conn: sqlite3.Connection, problem: str, slug: str,
                *, status: str = "open", detached: int = 0) -> int:
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " integrity_verified, detached, created_at, updated_at)"
        " VALUES (?, ?, ?, 'T', 'theorem', 'backward', ?, 1, 0, 'Builder',"
        " 0, ?, ?, ?)",
        (problem, slug, f"Problems/{problem}/proofs/L_{slug}.lean",
         status, detached, db.now(), db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------
# T0 trigger
# ---------------------------------------------------------------------

def test_t0_enqueues_strategist_for_bootstrap_done_zero(
    conn: sqlite3.Connection,
) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=0)
    root = _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT kind, target_id FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert int(q[0]["target_id"]) == root


def test_t0_skips_bootstrapped_problems(conn: sqlite3.Connection) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=db.now())  # T1 also skipped fresh
    _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t0_skips_proved_root(conn: sqlite3.Connection) -> None:
    """T0 must not enqueue Strategist for a problem whose root is
    already proved/shelved/disproved, even when bootstrap_done=0.
    Regression: Phase-2-activated workspaces inherit pre-Phase-2
    proved problems with bootstrap_done=0; without the root-status
    gate, every fresh daemon start would burn one Strategist spawn
    per such problem on Noop decisions.
    """
    for terminal in ("proved", "shelved", "disproved"):
        _insert_problem(conn, name=f"p_{terminal}", bootstrap_done=0)
        _insert_root(conn, f"p_{terminal}", status=terminal)

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t0_dedups_inflight_strategist(conn: sqlite3.Connection) -> None:
    """T0 won't enqueue a second Strategist if one is already running
    (in-memory running set) or already in queue."""
    _insert_problem(conn, name="alpha", bootstrap_done=0)
    root = _insert_root(conn, "alpha")
    # Simulate already in queue
    db.enqueue(conn, kind="Strategist", target_id=str(root),
               target_kind="Goal", priority=10)

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1  # not 2


def test_t0_skips_problem_with_inflight_inject_batch(
    conn: sqlite3.Connection,
) -> None:
    """T0 must not enqueue Strategist while a Forward Inject batch
    started by the previous Strategist run is still resolving (any
    strategist_decisions row with batch_id set and outcome NULL). The
    cascade-side `inject_batch_done` trigger fires Strategist when the
    last outcome lands; T0 firing in the meantime burns spawns on Noop
    decisions ("waiting for Forward"). Mirrors the principle that a
    normal goal isn't re-dispatched while its current attempt is in
    flight.
    """
    _insert_problem(conn, name="alpha")
    root = _insert_root(conn, "alpha", status="frozen")
    # Simulate a prior Strategist Inject(briefs=[...]) commit: one or
    # more strategist_decisions rows with batch_id non-NULL and outcome
    # still NULL (Forward not terminal yet).
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id,"
        " outcome, created_at, updated_at)"
        " VALUES (?, 0, 'first_launch', 'Inject', '## brief\n...',"
        " '{\"pipeline\": \"Forward\"}', 'batchXYZ', NULL, ?, ?)",
        ("alpha", db.now(), db.now()),
    )
    conn.commit()

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0
    # Sanity: once the batch outcome lands, T0 must re-enqueue.
    conn.execute(
        "UPDATE strategist_decisions SET outcome='success'"
        " WHERE batch_id='batchXYZ'"
    )
    conn.commit()
    strategist_triggers(conn, running=set())
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1
    assert root  # silence unused warning


# ---------------------------------------------------------------------
# T1 trigger
# ---------------------------------------------------------------------

def test_t1_enqueues_when_last_strategist_at_is_stale(
    conn: sqlite3.Connection,
) -> None:
    """Problem with last_strategist_at older than interval_min enqueues
    Strategist via T1."""
    # Set last_strategist_at to ~2 hours ago
    stale_ts = "2026-01-01T00:00:00+00:00"
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=stale_ts)
    root = _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert int(q[0]["target_id"]) == root


def test_t1_skips_when_last_strategist_at_is_recent(
    conn: sqlite3.Connection,
) -> None:
    recent_ts = db.now()
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=recent_ts)
    _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t1_treats_null_last_strategist_as_eligible(
    conn: sqlite3.Connection,
) -> None:
    """Bootstrapped problem with NULL last_strategist_at (e.g. Strategist
    committed Noop but the runtime is fresh) is immediately eligible
    for T1."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=None)
    _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1


def test_t1_skips_terminal_root(conn: sqlite3.Connection) -> None:
    """If root is already proved/shelved/disproved, no point running
    Strategist (nothing to direct)."""
    stale_ts = "2026-01-01T00:00:00+00:00"
    for prob, root_status in [
        ("alpha", "proved"),
        ("beta", "shelved"),
        ("gamma", "disproved"),
    ]:
        _insert_problem(conn, name=prob, bootstrap_done=1,
                        last_strategist_at=stale_ts)
        _insert_root(conn, prob, status=root_status)

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


# ---------------------------------------------------------------------
# awaiting_human gate
# ---------------------------------------------------------------------

def test_awaiting_human_gates_t0(conn: sqlite3.Connection) -> None:
    """A problem with an outstanding RequestUserAmend doesn't fire T0."""
    _insert_problem(conn, name="alpha", bootstrap_done=0)
    _insert_root(conn, "alpha")
    # Simulate an awaiting_human strategist_decisions row
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at)"
        " VALUES ('alpha', 1, 'first_launch', 'RequestUserAmend',"
        " '{}', 'awaiting_human', ?, ?)", (db.now(), db.now()),
    )
    conn.commit()

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_awaiting_human_gates_bfs_refill(conn: sqlite3.Connection) -> None:
    """bfs_refill skips goals whose problem has awaiting_human."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=db.now())
    root = _insert_root(conn, "alpha")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at)"
        " VALUES ('alpha', 1, 'routine', 'RequestUserAmend',"
        " '{}', 'awaiting_human', ?, ?)", (db.now(), db.now()),
    )
    conn.commit()

    bfs_refill(conn, running=set())

    # Backward/Builder for root should NOT be enqueued while awaiting_human
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue"
        " WHERE kind IN ('Builder','Backward')"
    ).fetchone()
    assert q["n"] == 0


# ---------------------------------------------------------------------
# bfs_refill: detached / pending_review
# ---------------------------------------------------------------------

def test_bfs_refill_skips_pending_strategist_review(
    conn: sqlite3.Connection,
) -> None:
    """open_goals filters by status='open'. pending_strategist_review
    is excluded → bfs_refill doesn't dispatch on it."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=db.now())
    _insert_root(conn, "alpha")
    _insert_sub(conn, "alpha", "sub_pending",
                status="pending_strategist_review")
    # Link via a strategy so it would be in the alive tree
    # (otherwise open_goals wouldn't see it anyway)
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (1, '', '', 'proposed', '', 'test', ?)", (db.now(),))
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, 2, 0)", (sid,))
    conn.commit()

    bfs_refill(conn, running=set())

    # Sub-goal (id=2) shouldn't be in the queue
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE target_id='2'"
    ).fetchone()
    assert q["n"] == 0
    # Root (id=1) is open + has live strategy → eligible
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE target_id='1'"
    ).fetchone()
    assert q["n"] == 1


def test_bfs_refill_includes_detached_goals(conn: sqlite3.Connection) -> None:
    """A goal with detached=1 + status='open' is dispatchable even
    when its parent strategy chain is dead. open_goals' recursive CTE
    seeds detached=1 rows as alive."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=db.now())
    root = _insert_root(conn, "alpha")
    # Sub-goal under a dead strategy, detached=1, status=open
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'dead', '', 'test', ?)", (root, db.now()))
    sid = int(cur.lastrowid)
    sub = _insert_sub(conn, "alpha", "sub_detached", status="open",
                      detached=1)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, sub))
    conn.commit()

    bfs_refill(conn, running=set())

    # detached=1 sub-goal SHOULD be enqueued despite dead parent strategy
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE target_id = ?",
        (str(sub),),
    ).fetchone()
    assert q["n"] == 1


def test_bfs_refill_excludes_undetached_orphan(
    conn: sqlite3.Connection,
) -> None:
    """A sub-goal under a dead strategy WITHOUT detached=1 is still an
    orphan — excluded from BFS as pre-Phase 2."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=db.now())
    root = _insert_root(conn, "alpha")
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'dead', '', 'test', ?)", (root, db.now()))
    sid = int(cur.lastrowid)
    sub = _insert_sub(conn, "alpha", "sub_orphan", status="open",
                      detached=0)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, sub))
    conn.commit()

    bfs_refill(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE target_id = ?",
        (str(sub),),
    ).fetchone()
    assert q["n"] == 0


# ---------------------------------------------------------------------
# DB helper checks (problem-level Strategist state)
# ---------------------------------------------------------------------

def test_set_problem_bootstrap_done(conn: sqlite3.Connection) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=0)

    db.set_problem_bootstrap_done(conn, "alpha")
    row = conn.execute(
        "SELECT bootstrap_done FROM problems WHERE name='alpha'"
    ).fetchone()
    assert row["bootstrap_done"] == 1


def test_set_problem_strategist_directive(conn: sqlite3.Connection) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=1)

    db.set_problem_strategist_directive(conn, "alpha", "Prefer L_x.")
    row = conn.execute(
        "SELECT strategist_directive FROM problems WHERE name='alpha'"
    ).fetchone()
    assert row["strategist_directive"] == "Prefer L_x."

    # Empty string clears it
    db.set_problem_strategist_directive(conn, "alpha", "")
    row = conn.execute(
        "SELECT strategist_directive FROM problems WHERE name='alpha'"
    ).fetchone()
    assert row["strategist_directive"] is None


def test_set_goal_detached(conn: sqlite3.Connection) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    gid = _insert_root(conn, "alpha")
    assert db.get_goal(conn, gid)["detached"] == 0

    db.set_goal_detached(conn, gid, True)
    assert db.get_goal(conn, gid)["detached"] == 1

    db.set_goal_detached(conn, gid, False)
    assert db.get_goal(conn, gid)["detached"] == 0
