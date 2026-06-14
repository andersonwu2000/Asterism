"""Phase 2 — dispatcher T0/T1 triggers + bfs_refill detached/pending
review handling + awaiting_human gate + queue.decision_id plumbing.

Covers Step 3 acceptance. T2 (cascade enqueue on agent_shelved) is
covered in `tests/test_phase2_cascade.py`.
"""
from __future__ import annotations

import json
import sqlite3
import time as _time
from pathlib import Path

import pytest

from Tooling.core.dispatcher import (
    _derive_strategist_trigger,
    bfs_refill,
    reconcile_stuck_states,
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
                    last_strategist_at: str | None = None,
                    last_routine_at: str | None = None) -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done, last_strategist_at, last_routine_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now(),
         bootstrap_done, last_strategist_at, last_routine_at),
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
                    last_routine_at=db.now())  # T1 also skipped fresh
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

def test_t1_enqueues_when_last_routine_at_is_stale(
    conn: sqlite3.Connection,
) -> None:
    """Problem with last_routine_at older than interval_min enqueues
    Strategist via T1."""
    stale_ts = "2026-01-01T00:00:00+00:00"
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=stale_ts)
    root = _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert int(q[0]["target_id"]) == root


def test_t1_skips_when_last_routine_at_is_recent(
    conn: sqlite3.Connection,
) -> None:
    recent_ts = db.now()
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=recent_ts)
    _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()["n"] == 0


def test_t1_not_reset_by_event_driven_last_strategist_at(
    conn: sqlite3.Connection,
) -> None:
    """The core of (a): an event-driven commit bumps last_strategist_at but
    NOT last_routine_at, so a routine that's overdue still fires — its cadence
    is not reset by pending_review / inject_batch_done activity."""
    stale_routine = "2026-01-01T00:00:00+00:00"
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=db.now(),       # just had an event wake
                    last_routine_at=stale_routine)     # but routine is overdue
    root = _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'").fetchall()
    assert [int(r["target_id"]) for r in q] == [root]


def test_t1_excludes_paused_time_via_daemon_start_baseline(
    conn: sqlite3.Connection,
) -> None:
    """Running-time cadence: a long-overdue routine does NOT fire immediately
    on restart — the daemon-start baseline excludes paused/down time, so it
    waits interval_min of running time."""
    stale_routine = "2026-01-01T00:00:00+00:00"   # ancient (a long pause ago)
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=stale_routine)
    _insert_root(conn, "alpha")

    # daemon just started → baseline is ~now → not yet interval_min elapsed
    strategist_triggers(conn, running=set(), interval_min=60.0,
                        daemon_start_iso=db.now())
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()["n"] == 0

    # an ancient daemon start (running long enough) → fires
    conn.execute("DELETE FROM queue")
    conn.commit()
    strategist_triggers(conn, running=set(), interval_min=60.0,
                        daemon_start_iso="2026-01-01T00:00:00+00:00")
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()["n"] == 1


def test_t1_not_suppressed_by_inflight_inject_batch(
    conn: sqlite3.Connection,
) -> None:
    """The routine audit is independent of batch resolution — unlike T0/T4,
    an unacknowledged Inject batch does NOT suppress T1. (Part of (a): the
    routine clock was being starved both by the shared timestamp reset and by
    near-continuous batch suppression.)"""
    stale_routine = "2026-01-01T00:00:00+00:00"
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=stale_routine)
    root = _insert_root(conn, "alpha")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id, outcome,"
        " created_at, updated_at) VALUES ('alpha', 0, 'first_launch',"
        " 'Inject', '## b', '{\"pipeline\":\"Forward\"}', 'b1', NULL, ?, ?)",
        (db.now(), db.now()),
    )
    conn.commit()

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'").fetchall()
    assert [int(r["target_id"]) for r in q] == [root]   # fired despite batch


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


def test_dispatchable_open_goals_excludes_awaiting_human(
    conn: sqlite3.Connection,
) -> None:
    """`dispatchable_open_goals` drops goals whose problem is paused on an
    unresolved RequestUserAmend. The dispatcher's idle-exit uses it (not
    raw `open_goals`) so a scoped daemon whose only in-scope problem is
    paused EXITS instead of livelocking — 2026-06-12 P12 was paused on a
    Defs amend, but the unscoped `open_goals` saw an unrelated problem's
    open goal and never exited."""
    _insert_problem(conn, name="paused", bootstrap_done=1)
    _insert_root(conn, "paused", status="open")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at)"
        " VALUES ('paused', 1, 'first_launch', 'RequestUserAmend',"
        " '{}', 'awaiting_human', ?, ?)", (db.now(), db.now()),
    )
    _insert_problem(conn, name="live", bootstrap_done=1)
    live_root = _insert_root(conn, "live", status="open")
    conn.commit()

    # Pre-fix livelock signal: unscoped open_goals sees BOTH problems.
    assert len(db.open_goals(conn)) == 2
    # Dispatchable excludes the paused problem entirely.
    assert [int(g["id"]) for g in db.dispatchable_open_goals(conn)] == [live_root]
    # Scoped to the paused problem → nothing dispatchable → daemon exits.
    assert db.dispatchable_open_goals(conn, scope="paused") == []
    # Scoped to the live problem → its open goal is dispatchable.
    assert [int(g["id"])
            for g in db.dispatchable_open_goals(conn, scope="live")] == [live_root]


def test_scoped_problem_names_filters_by_scope(
    conn: sqlite3.Connection,
) -> None:
    """`scoped_problem_names` returns only problems (with goals) matching
    the LIKE scope, sorted. Backs the dispatcher's scoped periodic
    TREE.md refresh so a `--scope` run stops churning every problem's
    tree each tick (the WinError 5 noise, 2026-06-12)."""
    for name in ("Geometry.stokes_x", "Geometry.stokes_y", "Minif2f.algebra_1"):
        _insert_problem(conn, name=name)
        _insert_root(conn, name)

    assert db.scoped_problem_names(conn, "Geometry.stokes_x") == ["Geometry.stokes_x"]
    assert db.scoped_problem_names(conn, "Geometry.%") == [
        "Geometry.stokes_x", "Geometry.stokes_y"]
    assert db.scoped_problem_names(conn, "Minif2f.%") == ["Minif2f.algebra_1"]
    # A scope matching nothing → empty (daemon then writes no tree).
    assert db.scoped_problem_names(conn, "Topology.%") == []


def test_strategies_goal_id_indexed(conn: sqlite3.Connection) -> None:
    """idx_strategies_goal_id backs tree.render's `_walk_goal` and
    db.open_goals' strategies-by-goal_id filter. Without it the (10k-row)
    strategies table is full-scanned per goal — measured 8.6s for one
    periodic tree-write across 281 problems (2026-06-12), down to 0.17s
    with the index. Guards the perf fix against schema regressions."""
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_strategies_goal_id" in names
    assert "idx_dead_attempts_target" in names
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT id FROM strategies WHERE goal_id=?",
        (1,),
    ).fetchall()
    assert any("idx_strategies_goal_id" in str(tuple(r)) for r in plan), plan


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


# ---------------------------------------------------------------------
# B-2 — T4 structural-stall trigger
# ---------------------------------------------------------------------

def test_t4_stall_enqueues_when_no_open_goals_and_no_inflight(
    conn: sqlite3.Connection,
) -> None:
    """T4 fires when root not terminal AND no open goal AND no
    in-flight Backward/Builder/Forward. Polar 2026-05-23 deadlock
    pattern (parent strategy with shelved sub-goal, no automatic
    Reopen trigger) — Strategist must intervene; without T4 the
    routine T1 wall-clock wait is up to 60 min, often Noop'd."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha", status="attempting")
    # The only other goal is also non-open (mimics polar pattern:
    # attempting goal whose only strategy is stuck on shelved sub-goal).
    other = db.insert_goal(
        conn, problem="alpha", slug="stuck",
        lean_path="Problems/alpha/proofs/L_stuck.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, other, "attempting")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1


def test_t4_stall_skipped_when_dispatchable_open_goal_exists(
    conn: sqlite3.Connection,
) -> None:
    """If a DISPATCHABLE (alive-reachable) open goal exists, BFS will
    dispatch it — no stall, T4 must not fire. The open goal is reachable
    here: a sub-goal of a 'proposed' strategy on the root. (last_routine_at
    recent excludes T1 routine firing for this isolation test.)"""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    root_id = _insert_root(conn, "alpha", status="attempting")
    open_id = db.insert_goal(
        conn, problem="alpha", slug="open_one",
        lean_path="Problems/alpha/proofs/L_open_one.lean",
        statement="T", origin="backward",
    )
    # Make it reachable from root via a live strategy (default status
    # 'open' already).
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'proposed', '', 'test', ?)",
        (root_id, db.now()))
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, open_id))
    conn.commit()

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t4_stall_fires_when_open_goals_all_orphaned(
    conn: sqlite3.Connection,
) -> None:
    """The P13 wedge (2026-06-13): an open goal exists but is ORPHANED
    (reachable only through a DEAD strategy, never the alive seed), so BFS
    can never dispatch it — the problem IS stalled and T4 must fire a
    Strategist. The pre-fix raw `status='open'` probe in `problems_stalled`
    masked exactly this and left the daemon idle-exiting on a collapsed
    decomposition."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    root_id = _insert_root(conn, "alpha", status="attempting")
    open_id = db.insert_goal(
        conn, problem="alpha", slug="orphan_open",
        lean_path="Problems/alpha/proofs/L_orphan_open.lean",
        statement="T", origin="backward",
    )
    # Link only under a DEAD strategy → unreachable from the alive seed.
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'dead', '', 'test', ?)",
        (root_id, db.now()))
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, open_id))
    conn.commit()

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1


def test_t4_stall_skipped_when_inflight_inject_batch(
    conn: sqlite3.Connection,
) -> None:
    """Inject batch in flight = Strategist already acting on this
    problem; `inject_batch_done` will re-fire it. T4 must not enqueue
    redundantly. (last_routine_at recent isolates T4 — T1 is now
    intentionally NOT batch-suppressed; see the dedicated T1 test.)"""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha", status="attempting")
    db.insert_goal(
        conn, problem="alpha", slug="other",
        lean_path="Problems/alpha/proofs/L_other.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, 2, "attempting")  # not 'open'
    # Outstanding Inject batch (Forward not landed yet).
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id,"
        " outcome, created_at, updated_at)"
        " VALUES ('alpha', 0, 'first_launch', 'Inject', '## brief',"
        " '{\"pipeline\":\"Forward\"}', 'b1', NULL, ?, ?)",
        (db.now(), db.now()),
    )
    conn.commit()

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t4_stall_skipped_when_root_terminal(
    conn: sqlite3.Connection,
) -> None:
    """If root already proved, stall trigger is moot."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="proved")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t4_stall_dedup_with_existing_strategist_queue_entry(
    conn: sqlite3.Connection,
) -> None:
    """If a Strategist task is already queued for this root, T4 must
    not add a duplicate."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha", status="attempting")
    db.enqueue(conn, kind="Strategist", target_id=str(root),
               target_kind="Goal", priority=10)

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1  # still just one


# ---------------------------------------------------------------------
# _derive_strategist_trigger — trigger_kind selection from DB state
# ---------------------------------------------------------------------

def test_derive_trigger_first_launch_only_when_bootstrap_done_zero(
    conn: sqlite3.Connection,
) -> None:
    """`first_launch` fires only when bootstrap_done=0 (truly first
    Strategist wake on this problem). Pre-fix the dispatcher picked
    first_launch whenever root.status='frozen', regardless of how
    many decisions had landed — jordan_normal_form 2026-05-23:
    200+ decisions committed but root still frozen because Strategist
    had been injecting prereq bricks rather than Reopen(root); pre-
    fix a manually-injected routine wake repeatedly hit
    first_launch.md instead of routine.md.
    """
    _insert_problem(conn, name="alpha", bootstrap_done=0)
    _insert_root(conn, "alpha", status="frozen")

    trigger, pending = _derive_strategist_trigger(conn, "alpha")
    assert trigger == "first_launch"
    assert pending is None


def test_derive_trigger_routine_when_frozen_root_but_bootstrap_done(
    conn: sqlite3.Connection,
) -> None:
    """Root frozen + bootstrap_done=1 → routine (Strategist has acted
    before; subsequent wakes should run the active-audit checklist,
    not the bootstrap survey)."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="frozen")

    trigger, pending = _derive_strategist_trigger(conn, "alpha")
    assert trigger == "routine"
    assert pending is None


def test_derive_trigger_routine_when_root_open_and_no_pending(
    conn: sqlite3.Connection,
) -> None:
    """Steady state — open root, no pending review, no unack inject
    batch → routine."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="open")

    trigger, _ = _derive_strategist_trigger(conn, "alpha")
    assert trigger == "routine"


def test_derive_trigger_pending_review_beats_frozen_root(
    conn: sqlite3.Connection,
) -> None:
    """A goal in pending_strategist_review must take priority over
    a frozen root — even on bootstrap_done=0, that specific goal
    needs a verdict before any other planning."""
    _insert_problem(conn, name="alpha", bootstrap_done=0)
    _insert_root(conn, "alpha", status="frozen")
    sub = _insert_sub(conn, "alpha", "sub_a",
                       status="pending_strategist_review")

    trigger, pending = _derive_strategist_trigger(conn, "alpha")
    assert trigger == "pending_review"
    assert pending == sub


def test_derive_trigger_inject_batch_done_beats_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """An unacknowledged Inject batch is the freshest event — beats
    pending_review and everything else. Strategist must consume the
    batch result before any other reasoning."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="attempting")
    _insert_sub(conn, "alpha", "sub_a",
                status="pending_strategist_review")
    # Seed an unack batch (an Inject decision with batch_id, outcome
    # filled, no Strategist response after).
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id,"
        " outcome, created_at, updated_at)"
        " VALUES ('alpha', 0, 'first_launch', 'Inject', '## brief',"
        " '{\"pipeline\":\"Forward\",\"step_index\":0,\"batch_size\":1}',"
        " 'batch-abc', 'success', ?, ?)",
        (ts, ts),
    )
    conn.commit()

    trigger, _ = _derive_strategist_trigger(conn, "alpha")
    assert trigger == "inject_batch_done"


# ---------------------------------------------------------------------
# reconcile_stuck_states — per-tick mid-run stuck-state safety net (#5)
# ---------------------------------------------------------------------

def _insert_null_inject(conn: sqlite3.Connection, *, problem: str,
                        pipeline: str, target_id: int | None = None,
                        produced_goal_id: int | None = None,
                        produced_strategy_id: int | None = None) -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, payload, outcome,"
        " produced_goal_id, produced_strategy_id, created_at, updated_at)"
        " VALUES (?, 0, 'inject_batch_done', 'Inject', ?, ?, NULL, ?, ?, ?, ?)",
        (problem, target_id, json.dumps({"pipeline": pipeline}),
         produced_goal_id, produced_strategy_id, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_problems_with_pending_review_lists_only_pending(
    conn: sqlite3.Connection,
) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "lemma1")
    assert db.problems_with_pending_review(conn) == []   # none pending yet
    db.update_goal_status(conn, sub, "pending_strategist_review")
    assert db.problems_with_pending_review(conn) == [("alpha", root)]
    assert db.problems_with_pending_review(conn, scope="beta%") == []


def test_problems_with_pending_review_includes_shelved_root(
    conn: sqlite3.Connection,
) -> None:
    # Regression (2026-06-14): a brick that shelves to pending_review under a
    # SHELVED (ConfirmShelve+Inject-parked) root must still be listed — the
    # old `NOT IN (...,'shelved',...)` filter orphaned it, and on a fresh
    # daemon start with no other work it idle-exited the run. Hard-terminal
    # roots (proved / disproved) stay excluded.
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "brick1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    db.update_goal_status(conn, root, "shelved")
    assert db.problems_with_pending_review(conn) == [("alpha", root)]
    # hard-terminal root → still excluded (problem is genuinely done/dead)
    db.update_goal_status(conn, root, "proved")
    assert db.problems_with_pending_review(conn) == []


def test_reconcile_enqueues_strategist_for_orphaned_pending_review(
    conn: sqlite3.Connection,
) -> None:
    # The core fix: a pending_review goal with NO strategist queued/in-flight
    # gets one enqueued on its root (the spawn then derives a pending_review
    # wake). Closes the orphan the cascade-time enqueue can drop.
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "lemma1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    reconcile_stuck_states(conn, running=set())
    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'").fetchall()
    assert [int(r["target_id"]) for r in q] == [root]


def test_reconcile_pending_review_dedups_queue_and_inflight(
    conn: sqlite3.Connection,
) -> None:
    # Serialization invariant: never a second Strategist while one is queued
    # OR in-flight for the same root.
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "lemma1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    # already queued → no second
    db.enqueue(conn, kind="Strategist", target_id=str(root),
               target_kind="Goal", priority=20)
    reconcile_stuck_states(conn, running=set())
    assert conn.execute(
        "SELECT count(*) c FROM queue WHERE kind='Strategist'"
    ).fetchone()["c"] == 1
    # in-flight (running) → no enqueue at all
    conn.execute("DELETE FROM queue")
    conn.commit()
    reconcile_stuck_states(conn, running={(str(root), "Strategist", None)})
    assert conn.execute(
        "SELECT count(*) c FROM queue WHERE kind='Strategist'"
    ).fetchone()["c"] == 0


def test_reconcile_pending_review_skipped_under_awaiting_human(
    conn: sqlite3.Connection,
) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "lemma1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at) VALUES ('alpha', 1, 'first_launch', 'RequestUserAmend',"
        " '{}', 'awaiting_human', ?, ?)", (db.now(), db.now()),
    )
    conn.commit()
    reconcile_stuck_states(conn, running=set())
    assert conn.execute(
        "SELECT count(*) c FROM queue WHERE kind='Strategist'"
    ).fetchone()["c"] == 0


def test_null_inject_redispatch_specs_applies_artifact_guards(
    conn: sqlite3.Connection,
) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    tgt = _insert_sub(conn, "alpha", "tgt")   # real goal for FK target_id
    sid = db.insert_strategy(                  # real strategy for FK
        conn, goal_id=tgt, lean_path="Problems/alpha/Root.lean",
        scratch_path="Problems/alpha/proofs/_strategy_s1.lean",
        created_by="pid")
    d_fwd = _insert_null_inject(conn, problem="alpha", pipeline="Forward")
    _insert_null_inject(conn, problem="alpha", pipeline="Forward",
                        produced_goal_id=tgt)                 # skip (lemma)
    d_bwd = _insert_null_inject(conn, problem="alpha", pipeline="Backward",
                                target_id=tgt)
    _insert_null_inject(conn, problem="alpha", pipeline="Backward",
                        target_id=tgt, produced_strategy_id=sid)  # skip(strat)
    specs = {s["decision_id"]: s for s in
             db.null_inject_redispatch_specs(conn)}
    assert set(specs) == {d_fwd, d_bwd}        # only the no-artifact ones
    assert specs[d_fwd]["kind"] == "Forward"
    assert specs[d_fwd]["target_kind"] == "Problem"
    assert specs[d_bwd]["kind"] == "Backward"
    assert specs[d_bwd]["target_id"] == str(tgt)


def test_reconcile_reenqueues_null_inject_in_flight_gated(
    conn: sqlite3.Connection,
) -> None:
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    d1 = _insert_null_inject(conn, problem="alpha", pipeline="Forward")
    # not in-flight, not queued → re-enqueued
    reconcile_stuck_states(conn, running=set())
    q = conn.execute(
        "SELECT kind, decision_id FROM queue WHERE kind='Forward'").fetchall()
    assert [(r["kind"], r["decision_id"]) for r in q] == [("Forward", d1)]
    # in-flight worker for this decision → not re-enqueued
    conn.execute("DELETE FROM queue")
    conn.commit()
    reconcile_stuck_states(conn, running={("alpha", "Forward", d1)})
    assert conn.execute(
        "SELECT count(*) c FROM queue WHERE kind='Forward'"
    ).fetchone()["c"] == 0
    # already queued → no duplicate
    db.enqueue(conn, kind="Forward", target_id="alpha",
               target_kind="Problem", priority=10, decision_id=d1)
    reconcile_stuck_states(conn, running=set())
    assert conn.execute(
        "SELECT count(*) c FROM queue WHERE decision_id=?", (d1,)
    ).fetchone()["c"] == 1
