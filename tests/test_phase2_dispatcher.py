"""Phase 2/6 — dispatcher Strategist triggers (T1 routine + T4 stall;
problem-keyed rows) + bfs_refill detached/pending review handling +
awaiting_human gate + queue.decision_id plumbing.

Phase 6: T0/first_launch is retired — a fresh problem is structurally
STALLED, so the T4 trigger wakes the Strategist; Strategist queue rows
are target_id=<problem name>, target_kind='Problem'; problem liveness
is `problems.ingested_at IS NULL` (not root status).

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
    _dispatch_is_duplicate,
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
# Fresh-problem wake (Phase 6 — T0/first_launch retired; a fresh problem
# is structurally STALLED, so the T4 stall trigger wakes the Strategist)
# ---------------------------------------------------------------------

def test_fresh_problem_stalls_and_wakes_strategist(
    conn: sqlite3.Connection,
) -> None:
    """A fresh problem (frozen root, nothing dispatchable, no committed
    Ingest) is structurally stalled → T4 wakes the Strategist with a
    problem-keyed row (target_id=<problem name>, target_kind='Problem').
    Replaces the retired T0/first_launch trigger. (last_routine_at
    recent isolates T4 from T1.)"""
    _insert_problem(conn, name="alpha", bootstrap_done=0,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha", status="frozen")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT kind, target_id, target_kind, priority FROM queue"
        " WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == "alpha"
    assert q[0]["target_kind"] == "Problem"
    assert q[0]["priority"] == 10


def test_fresh_pure_nl_problem_stalls_and_wakes_strategist(
    conn: sqlite3.Connection,
) -> None:
    """Pure-NL mode (Root/Defs optional): a problem with NO root goal at
    all still gets the T4 stall wake — the problem-keyed trigger no
    longer JOINs on an origin='root' goal."""
    _insert_problem(conn, name="alpha", bootstrap_done=0,
                    last_routine_at=db.now())

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == "alpha"
    assert q[0]["target_kind"] == "Problem"


def test_no_wake_when_dispatchable_goal_and_recent_routine(
    conn: sqlite3.Connection,
) -> None:
    """An actively-progressing problem (dispatchable open root, routine
    clock fresh) gets no Strategist wake."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())  # T1 also skipped fresh
    _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_ingested_problem_gets_no_wake(conn: sqlite3.Connection) -> None:
    """No pointless wake for a FINISHED problem: `ingested_at` set (the
    Phase 6 terminal state) suppresses every trigger, regardless of the
    root's status. Replaces the old root-terminal suppression."""
    for terminal in ("proved", "shelved", "disproved"):
        name = f"p_{terminal}"
        _insert_problem(conn, name=name, bootstrap_done=0)
        _insert_root(conn, name, status=terminal)
        db.set_problem_ingested(conn, name)

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_terminal_root_without_ingest_still_wakes(
    conn: sqlite3.Connection,
) -> None:
    """Load-bearing Phase 6 behavior: a PROVED root with no committed
    Ingest IS stalled when idle — this is the engine that wakes the
    Strategist to judge the Manifest and commit Ingest (the only exit
    trigger). Shelved/disproved roots no longer suppress the stall
    either."""
    for terminal in ("proved", "shelved", "disproved"):
        name = f"p_{terminal}"
        _insert_problem(conn, name=name, bootstrap_done=1,
                        last_routine_at=db.now())
        _insert_root(conn, name, status=terminal)

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
        " ORDER BY target_id"
    ).fetchall()
    assert [(r["target_id"], r["target_kind"]) for r in q] == [
        ("p_disproved", "Problem"),
        ("p_proved", "Problem"),
        ("p_shelved", "Problem"),
    ]


def test_stall_wake_dedups_inflight_strategist(
    conn: sqlite3.Connection,
) -> None:
    """The stall wake won't enqueue a second Strategist if one is
    already running (in-memory running set) or already in queue."""
    _insert_problem(conn, name="alpha", bootstrap_done=0,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha", status="frozen")
    # Simulate already in queue (problem-keyed row).
    db.enqueue(conn, kind="Strategist", target_id="alpha",
               target_kind="Problem", priority=10, problem="alpha")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1  # not 2

    # In-flight (running set) → no enqueue at all.
    conn.execute("DELETE FROM queue")
    conn.commit()
    strategist_triggers(conn, running={("alpha", "Strategist", None)})
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_fresh_problem_wake_deferred_while_inject_batch_in_flight(
    conn: sqlite3.Connection,
) -> None:
    """The stall wake must not fire while a Forward Inject batch started
    by the previous Strategist run is still resolving: the enqueued
    Forward worker (is_problem_stalled condition 3) keeps T4 quiet. The
    cascade-side `inject_batch_done` trigger fires Strategist when the
    last outcome lands; T4 firing in the meantime burns spawns on Noop
    decisions ("waiting for Forward"). Mirrors the principle that a
    normal goal isn't re-dispatched while its current attempt is in
    flight. (last_routine_at recent isolates T4 — T1 is intentionally
    NOT batch-suppressed.)
    """
    _insert_problem(conn, name="alpha", last_routine_at=db.now())
    root = _insert_root(conn, "alpha", status="frozen")
    # Simulate a prior Strategist Inject(briefs=[...]) commit: a
    # strategist_decisions row with batch_id non-NULL and outcome still
    # NULL (Forward not terminal yet) AND the Forward worker it enqueued
    # at commit (strategist._commit_inject_forward) — the queue row is
    # what keeps the stall trigger (T4) quiet while the brick is in
    # flight.
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id,"
        " outcome, created_at, updated_at)"
        " VALUES (?, 0, 'inject_batch_done', 'Inject', '## brief\n...',"
        " '{\"pipeline\": \"Forward\"}', 'batchXYZ', NULL, ?, ?)",
        ("alpha", db.now(), db.now()),
    )
    db.enqueue(conn, kind="Forward", target_id="alpha",
               target_kind="Problem", priority=10, problem="alpha")
    conn.commit()

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0
    # Sanity: once the batch outcome lands (and the worker drains), T4
    # must re-enqueue — problem-keyed.
    conn.execute(
        "UPDATE strategist_decisions SET outcome='success'"
        " WHERE batch_id='batchXYZ'"
    )
    conn.execute("DELETE FROM queue WHERE kind='Forward'")
    conn.commit()
    strategist_triggers(conn, running=set())
    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == "alpha"
    assert q[0]["target_kind"] == "Problem"
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
    _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == "alpha"
    assert q[0]["target_kind"] == "Problem"


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
    _insert_root(conn, "alpha")

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'").fetchall()
    assert [r["target_id"] for r in q] == ["alpha"]


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
    _insert_root(conn, "alpha")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id, outcome,"
        " created_at, updated_at) VALUES ('alpha', 0, 'inject_batch_done',"
        " 'Inject', '## b', '{\"pipeline\":\"Forward\"}', 'b1', NULL, ?, ?)",
        (db.now(), db.now()),
    )
    conn.commit()

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'").fetchall()
    assert [r["target_id"] for r in q] == ["alpha"]   # fired despite batch


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


def test_t1_skips_ingested_problems(conn: sqlite3.Connection) -> None:
    """Phase 6 — T1 filters on the problem terminal state (`ingested_at`
    set), NOT root status: an ingested problem is never routine-audited;
    a proved-root problem WITHOUT a committed Ingest still is (the
    Strategist must still judge the Manifest and commit Ingest)."""
    stale_ts = "2026-01-01T00:00:00+00:00"
    for prob, root_status in [
        ("alpha", "proved"),
        ("beta", "shelved"),
        ("gamma", "disproved"),
    ]:
        _insert_problem(conn, name=prob, bootstrap_done=1,
                        last_routine_at=stale_ts)
        _insert_root(conn, prob, status=root_status)
        db.set_problem_ingested(conn, prob)

    strategist_triggers(conn, running=set(), interval_min=60.0)

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0

    # Complement: not-yet-ingested proved-root problem IS T1-audited.
    db.set_problem_ingested(conn, "alpha", ingested=False)
    strategist_triggers(conn, running=set(), interval_min=60.0)
    q = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'").fetchall()
    assert [r["target_id"] for r in q] == ["alpha"]


# ---------------------------------------------------------------------
# awaiting_human gate
# ---------------------------------------------------------------------

def test_awaiting_human_gates_strategist_triggers(
    conn: sqlite3.Connection,
) -> None:
    """A problem with an outstanding RequestUserAmend fires neither the
    T4 stall wake (frozen root → stalled) nor T1 (NULL last_routine_at
    → ancient)."""
    _insert_problem(conn, name="alpha", bootstrap_done=0)
    _insert_root(conn, "alpha", status="frozen")
    # Simulate an awaiting_human strategist_decisions row
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at)"
        " VALUES ('alpha', 1, 'routine', 'RequestUserAmend',"
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
    """A committed Forward Inject is a NULL-outcome decision row AND an
    enqueued Forward worker (strategist._commit_inject_forward enqueues at
    commit). The enqueued worker (is_problem_stalled condition 3) is what
    keeps T4 quiet while the brick is in flight; `inject_batch_done` re-fires
    the Strategist when it lands. T4 must not enqueue redundantly.
    (last_routine_at recent isolates T4 — T1 is intentionally NOT batch-
    suppressed; see the dedicated T1 test.)"""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha", status="attempting")
    db.insert_goal(
        conn, problem="alpha", slug="other",
        lean_path="Problems/alpha/proofs/L_other.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, 2, "attempting")  # not 'open'
    # Outstanding Inject batch (Forward not landed yet) + its enqueued worker.
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id,"
        " outcome, created_at, updated_at)"
        " VALUES ('alpha', 0, 'inject_batch_done', 'Inject', '## brief',"
        " '{\"pipeline\":\"Forward\"}', 'b1', NULL, ?, ?)",
        (db.now(), db.now()),
    )
    db.enqueue(conn, kind="Forward", target_id="alpha",
               target_kind="Problem", priority=10, problem="alpha")
    conn.commit()

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t4_wakes_on_proved_root_until_ingested(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6 — a PROVED root with no committed Ingest IS stalled when
    idle: T4 wakes the Strategist to judge the Manifest and commit the
    terminal Ingest. Once `ingested_at` is set the problem is never
    stalled again."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha", status="proved")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == "alpha"
    assert q[0]["target_kind"] == "Problem"

    # Ingest committed → terminal → no further wake.
    conn.execute("DELETE FROM queue")
    conn.commit()
    db.set_problem_ingested(conn, "alpha")
    strategist_triggers(conn, running=set())
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t4_stall_wakes_pure_nl_problem_without_root(
    conn: sqlite3.Connection,
) -> None:
    """Pure-NL problem (no root goal at all), one shelved brick, nothing
    dispatchable → stalled → T4 wake, problem-keyed."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_sub(conn, "alpha", "brick", status="shelved")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert [(r["target_id"], r["target_kind"]) for r in q] == [
        ("alpha", "Problem")]


def test_t4_stall_not_masked_by_dispatchable_detached_goal(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6 — the stall predicate's alive CTE seeds root UNION
    detached: a dispatchable DETACHED open Forward goal is real pending
    work, so the problem is NOT stalled (pre-fix the root-only seed
    read it as stalled while BFS happily dispatched it)."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_sub(conn, "alpha", "fwd_brick", status="open", detached=1)

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t4_stall_dedup_with_existing_strategist_queue_entry(
    conn: sqlite3.Connection,
) -> None:
    """If a Strategist task is already queued for this problem, T4 must
    not add a duplicate."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="attempting")
    db.enqueue(conn, kind="Strategist", target_id="alpha",
               target_kind="Problem", priority=10, problem="alpha")

    strategist_triggers(conn, running=set())

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1  # still just one


# ---------------------------------------------------------------------
# _derive_strategist_trigger — trigger_kind selection from DB state
# ---------------------------------------------------------------------

def test_derive_trigger_batch_done_on_stall(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6 — `first_launch` is retired. A fresh problem (frozen
    root, nothing dispatchable, no committed Ingest) is structurally
    STALLED and derives `inject_batch_done` (the "empty batch done"
    reading) — the only prompt carrying the mandatory-advance rule, so
    the wake bootstraps the first Inject instead of Noop'ing."""
    _insert_problem(conn, name="alpha", bootstrap_done=0)
    _insert_root(conn, "alpha", status="frozen")

    trigger, pending = _derive_strategist_trigger(conn, "alpha")
    assert trigger == "inject_batch_done"
    assert pending is None


def test_derive_trigger_batch_done_on_pure_nl_fresh_problem(
    conn: sqlite3.Connection,
) -> None:
    """Pure-NL fresh problem (no root goal at all) is stalled too and
    derives the same `inject_batch_done` wake."""
    _insert_problem(conn, name="alpha", bootstrap_done=0)

    trigger, pending = _derive_strategist_trigger(conn, "alpha")
    assert trigger == "inject_batch_done"
    assert pending is None


def test_derive_trigger_routine_when_worker_in_flight(
    conn: sqlite3.Connection,
) -> None:
    """A frozen-root problem with an in-flight Forward worker (queued)
    is NOT stalled (is_problem_stalled condition 3) → the wake is a
    plain routine check-in, not the mandatory-advance batch-done."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="frozen")
    db.enqueue(conn, kind="Forward", target_id="alpha",
               target_kind="Problem", priority=10, problem="alpha")

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


def _insert_decision(conn, problem: str, *, trigger: str = "routine",
                     kind: str = "EmitDirective",
                     created_at: str = "2026-01-01T00:00:00+00:00") -> None:
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at) VALUES (?, 0, ?, ?, '{}', 'success', ?, ?)",
        (problem, trigger, kind, created_at, created_at))
    conn.commit()


def test_derive_trigger_audit_due_beats_stall(
    conn: sqlite3.Connection,
) -> None:
    """v26 auditor: on a STALLED problem whose decision history is older
    than the audit interval, the wake classifies as 'audit' — above the
    stall reclassification on purpose (a walled problem fires stall
    wakes continuously; the wall is where beliefs fossilize)."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="frozen")   # structurally stalled
    _insert_decision(conn, "alpha")                # old history → due

    trigger, pending = _derive_strategist_trigger(
        conn, "alpha", audit_interval_min=180.0)
    assert trigger == "audit"
    assert pending is None
    # Auditor disabled (default 0) → the stall reading is back.
    trigger2, _ = _derive_strategist_trigger(conn, "alpha")
    assert trigger2 == "inject_batch_done"


def test_derive_trigger_audit_needs_history_and_interval(
    conn: sqlite3.Connection,
) -> None:
    """No decision history → never audit (young problems have no belief
    corpus); a RECENT audit-trigger decision re-anchors the clock."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="frozen")

    trigger, _ = _derive_strategist_trigger(
        conn, "alpha", audit_interval_min=180.0)
    assert trigger == "inject_batch_done"   # no history → stall reading

    _insert_decision(conn, "alpha")  # old birth → due
    _insert_decision(conn, "alpha", trigger="audit", created_at=db.now())
    trigger2, _ = _derive_strategist_trigger(
        conn, "alpha", audit_interval_min=180.0)
    assert trigger2 == "inject_batch_done"  # fresh audit → not due


def test_derive_trigger_audit_beats_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """Periodic wakes outrank events (user ruling 2026-07-12): a due
    audit fires even while a goal awaits review — the pending goal is
    persistent state, its seat re-arms every tick, so it is delayed by
    exactly one wake; the audit that fixes the belief corpus first
    makes the verdict after it a better verdict. pending_id still rides
    along for context."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha", status="attempting")
    sub = _insert_sub(conn, "alpha", "sub_a",
                      status="pending_strategist_review")
    _insert_decision(conn, "alpha")

    trigger, pending = _derive_strategist_trigger(
        conn, "alpha", audit_interval_min=180.0)
    assert trigger == "audit"
    assert pending == sub
    # Auditor disabled → the pending verdict is back in front.
    trigger2, pending2 = _derive_strategist_trigger(conn, "alpha")
    assert trigger2 == "pending_review"
    assert pending2 == sub


def test_derive_trigger_routine_due_beats_batch_done_and_audit(
    conn: sqlite3.Connection,
) -> None:
    """Routine is the same periodic mechanism as audit up to period
    (user ruling 2026-07-12) and sits on top: with the routine clock
    overdue, the wake classifies routine even over an unacknowledged
    batch or a due audit. since_iso (daemon start) excludes down-time:
    a start newer than the stale clock re-arms it."""
    ts = "2026-01-01T00:00:00+00:00"
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_strategist_at=ts, last_routine_at=ts)
    _insert_root(conn, "alpha", status="attempting")
    _insert_decision(conn, "alpha")   # old history → audit due too
    # Unacknowledged resolved batch (would classify inject_batch_done).
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, batch_id,"
        " outcome, created_at, updated_at)"
        " VALUES ('alpha', 0, 'routine', 'Inject', '## b',"
        " '{\"pipeline\":\"Forward\",\"step_index\":0,\"batch_size\":1}',"
        " 'batch-x', 'success', ?, ?)", (db.now(), db.now()))
    conn.commit()

    trigger, _ = _derive_strategist_trigger(
        conn, "alpha", audit_interval_min=180.0,
        routine_interval_min=60.0)
    assert trigger == "routine"
    # Daemon started NOW → running time ≈ 0 → routine re-armed; audit
    # (also since_iso-gated) re-armed too; the batch is back in front.
    trigger2, _ = _derive_strategist_trigger(
        conn, "alpha", audit_interval_min=180.0,
        routine_interval_min=60.0, since_iso=db.now())
    assert trigger2 == "inject_batch_done"


def test_t15_audit_enqueue_is_a_seat_source(
    conn: sqlite3.Connection, capsys,
) -> None:
    """T1.5 (user call 2026-07-11): a due audit ENQUEUES its own
    Strategist seat instead of riding seats other events open. Isolated
    from T1/T4: dispatchable open root (no stall) + fresh routine clock."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha")            # open → not stalled
    _insert_decision(conn, "alpha")        # old history → audit due

    strategist_triggers(conn, running=set(), audit_interval_min=180.0)

    q = conn.execute(
        "SELECT target_id, target_kind, priority FROM queue"
        " WHERE kind='Strategist'").fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == "alpha" and q[0]["target_kind"] == "Problem"
    assert "[audit-wake]" in capsys.readouterr().out
    # Re-run: in-flight dedup (queued row) → no pileup.
    strategist_triggers(conn, running=set(), audit_interval_min=180.0)
    n = conn.execute("SELECT COUNT(*) AS n FROM queue"
                     " WHERE kind='Strategist'").fetchone()
    assert n["n"] == 1


def test_t15_audit_enqueue_gates(conn: sqlite3.Connection) -> None:
    """T1.5 stays quiet when: disabled (interval 0, the default), not due
    (fresh audit re-anchors), or the problem is ingested."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha")
    _insert_decision(conn, "alpha")

    strategist_triggers(conn, running=set())          # default: disabled
    assert conn.execute("SELECT COUNT(*) AS n FROM queue"
                        " WHERE kind='Strategist'").fetchone()["n"] == 0

    _insert_decision(conn, "alpha", trigger="audit", created_at=db.now())
    strategist_triggers(conn, running=set(), audit_interval_min=180.0)
    assert conn.execute("SELECT COUNT(*) AS n FROM queue"
                        " WHERE kind='Strategist'").fetchone()["n"] == 0

    conn.execute("UPDATE strategist_decisions SET created_at ="
                 " '2026-01-01T00:00:00+00:00', updated_at ="
                 " '2026-01-01T00:00:00+00:00'")   # due again…
    conn.execute("UPDATE problems SET ingested_at = ? WHERE name='alpha'",
                 (db.now(),))                      # …but ingested
    conn.commit()
    strategist_triggers(conn, running=set(), audit_interval_min=180.0)
    assert conn.execute("SELECT COUNT(*) AS n FROM queue"
                        " WHERE kind='Strategist'").fetchone()["n"] == 0


def test_t15_audit_enqueue_awaiting_human_gate(
    conn: sqlite3.Connection,
) -> None:
    """An outstanding RequestUserAmend gates T1.5 like every other seat."""
    _insert_problem(conn, name="alpha", bootstrap_done=1,
                    last_routine_at=db.now())
    _insert_root(conn, "alpha")
    _insert_decision(conn, "alpha")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at)"
        " VALUES ('alpha', 1, 'routine', 'RequestUserAmend',"
        " '{}', 'awaiting_human', ?, ?)", (db.now(), db.now()))
    conn.commit()

    strategist_triggers(conn, running=set(), audit_interval_min=180.0)
    assert conn.execute("SELECT COUNT(*) AS n FROM queue"
                        " WHERE kind='Strategist'").fetchone()["n"] == 0


def test_consecutive_strategist_probe(
    conn: sqlite3.Connection, capsys,
) -> None:
    """Log-only probe (user call 2026-07-11): a Strategist wake whose
    problem's LAST pipeline was also a Strategist (nothing in flight)
    prints [consecutive-strategist]; an in-flight worker (leased queue
    row) or a non-Strategist last pipeline stays silent."""
    from Tooling.core.dispatcher import _warn_consecutive_strategist
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha", status="open")
    ts = db.now()
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('s-prev', 'Strategist', 'alpha', 'Problem',"
        " 'succeeded', 'success', ?, ?)", (ts, ts))
    conn.commit()

    _warn_consecutive_strategist(conn, "alpha", "inject_batch_done")
    out = capsys.readouterr().out
    assert "[consecutive-strategist] alpha" in out
    assert "trigger=inject_batch_done" in out

    # An in-flight worker (queue row) suppresses the probe — the
    # in-between pipeline just has no pipelines row yet.
    db.enqueue(conn, kind="Backward", target_id=str(root),
               target_kind="Goal", priority=5, problem="alpha")
    _warn_consecutive_strategist(conn, "alpha", "inject_batch_done")
    assert "[consecutive-strategist]" not in capsys.readouterr().out
    conn.execute("DELETE FROM queue")

    # A non-Strategist pipeline in between → silent.
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('b-mid', 'Backward', ?, 'Goal', 'failed', 'failed',"
        " ?, ?)", (str(root), db.now(), db.now()))
    conn.commit()
    _warn_consecutive_strategist(conn, "alpha", "routine")
    assert "[consecutive-strategist]" not in capsys.readouterr().out


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
    _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "lemma1")
    assert db.problems_with_pending_review(conn) == []   # none pending yet
    db.update_goal_status(conn, sub, "pending_strategist_review")
    assert db.problems_with_pending_review(conn) == ["alpha"]
    assert db.problems_with_pending_review(conn, scope="beta%") == []


def test_problems_with_pending_review_root_status_irrelevant(
    conn: sqlite3.Connection,
) -> None:
    # Regression (2026-06-14): a brick that shelves to pending_review under a
    # SHELVED (ConfirmShelve+Inject-parked) root must still be listed.
    # Phase 6: the exclusion is the problem terminal state (`ingested_at`),
    # not root status — even a PROVED root still needs review wakes (the
    # Strategist has to judge the review AND eventually commit Ingest).
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    root = _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "brick1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    db.update_goal_status(conn, root, "shelved")
    assert db.problems_with_pending_review(conn) == ["alpha"]
    # proved root → STILL listed (Phase 6: only Ingest is terminal)
    db.update_goal_status(conn, root, "proved")
    assert db.problems_with_pending_review(conn) == ["alpha"]
    # committed Ingest → excluded (problem is genuinely done)
    db.set_problem_ingested(conn, "alpha")
    assert db.problems_with_pending_review(conn) == []


def test_reconcile_enqueues_strategist_for_orphaned_pending_review(
    conn: sqlite3.Connection,
) -> None:
    # The core fix: a pending_review goal with NO strategist queued/in-flight
    # gets one enqueued on its problem (the spawn then derives a
    # pending_review wake). Closes the orphan the cascade-time enqueue can
    # drop.
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "lemma1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    reconcile_stuck_states(conn, running=set())
    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert [(r["target_id"], r["target_kind"]) for r in q] == [
        ("alpha", "Problem")]


def test_reconcile_pending_review_pure_nl_problem_without_root(
    conn: sqlite3.Connection,
) -> None:
    # Pure-NL mode: the reconcile wake works with NO root goal at all —
    # the problem-keyed enqueue does not depend on an origin='root' row.
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    sub = _insert_sub(conn, "alpha", "lemma1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    reconcile_stuck_states(conn, running=set())
    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert [(r["target_id"], r["target_kind"]) for r in q] == [
        ("alpha", "Problem")]


def test_reconcile_pending_review_dedups_queue_and_inflight(
    conn: sqlite3.Connection,
) -> None:
    # Serialization invariant: never a second Strategist while one is queued
    # OR in-flight for the same problem.
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    _insert_root(conn, "alpha")
    sub = _insert_sub(conn, "alpha", "lemma1")
    db.update_goal_status(conn, sub, "pending_strategist_review")
    # already queued → no second
    db.enqueue(conn, kind="Strategist", target_id="alpha",
               target_kind="Problem", priority=20, problem="alpha")
    reconcile_stuck_states(conn, running=set())
    assert conn.execute(
        "SELECT count(*) c FROM queue WHERE kind='Strategist'"
    ).fetchone()["c"] == 1
    # in-flight (running) → no enqueue at all
    conn.execute("DELETE FROM queue")
    conn.commit()
    reconcile_stuck_states(conn, running={("alpha", "Strategist", None)})
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
    # Separate target for the produced_strategy case so this test isolates the
    # artifact GUARDS from latest-per-target supersession (covered separately).
    tgt2 = _insert_sub(conn, "alpha", "tgt2")
    sid = db.insert_strategy(                  # real strategy for FK
        conn, goal_id=tgt2, lean_path="Problems/alpha/Root.lean",
        scratch_path="Problems/alpha/proofs/_strategy_s1.lean",
        created_by="pid")
    d_fwd = _insert_null_inject(conn, problem="alpha", pipeline="Forward")
    _insert_null_inject(conn, problem="alpha", pipeline="Forward",
                        produced_goal_id=tgt)                 # skip (lemma)
    d_bwd = _insert_null_inject(conn, problem="alpha", pipeline="Backward",
                                target_id=tgt)
    _insert_null_inject(conn, problem="alpha", pipeline="Backward",
                        target_id=tgt2, produced_strategy_id=sid)  # skip(strat)
    specs = {s["decision_id"]: s for s in
             db.null_inject_redispatch_specs(conn)}
    assert set(specs) == {d_fwd, d_bwd}        # only the no-artifact ones
    assert specs[d_fwd]["kind"] == "Forward"
    assert specs[d_fwd]["target_kind"] == "Problem"
    assert specs[d_bwd]["kind"] == "Backward"
    assert specs[d_bwd]["target_id"] == str(tgt)


def test_null_inject_redispatch_skips_backward_with_parked_target(
    conn: sqlite3.Connection,
) -> None:
    """A Backward Inject whose TARGET goal is parked (shelved) — e.g. a
    return_to_parent that committed no strategy — must NOT be redispatched.
    Its outcome stays NULL now that shelved no longer settles, but the work
    is parked, not missing; redispatching would re-spin the parked goal
    forever (the P13 4284 disease via the redispatch path)."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    tgt = _insert_sub(conn, "alpha", "tgt", status="shelved")
    d = _insert_null_inject(conn, problem="alpha", pipeline="Backward",
                            target_id=tgt)
    specs = {s["decision_id"]: s
             for s in db.null_inject_redispatch_specs(conn)}
    assert d not in specs
    # Sanity: the same inject IS redispatched once the target reopens.
    db.update_goal_status(conn, tgt, "open")
    specs = {s["decision_id"]: s
             for s in db.null_inject_redispatch_specs(conn)}
    assert d in specs


def test_null_inject_redispatch_builder_judged_by_target_not_backlink(
    conn: sqlite3.Connection,
) -> None:
    """Regression (P13 4284, 2026-06-15): a killed Builder Inject must be
    judged by its TARGET'S status, NOT by produced_goal_id. A Builder proves
    in place, so produced_goal_id is set to =target at commit as an outcome
    backlink — non-NULL from the start, NOT a work-done signal. The old guard
    (`Builder and produced_goal_id is not None → skip`) therefore skipped
    every killed Builder forever, while has_active_inflight_inject counted it
    active → the Strategist was suppressed and the work was never resumed →
    permanent deadlock + BFS moot-spin. Builder must now fall through to the
    parked-target check: open/attempting target → redispatch, terminal/parked
    → skip."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    tgt = _insert_sub(conn, "alpha", "tgt")   # open by default
    # Builder with produced_goal_id=target (always set at commit) + open
    # target → MUST redispatch (the killed-mid-run Builder resumes).
    d_open = _insert_null_inject(conn, problem="alpha", pipeline="Builder",
                                 target_id=tgt, produced_goal_id=tgt)
    specs = {s["decision_id"]: s
             for s in db.null_inject_redispatch_specs(conn)}
    assert d_open in specs
    assert specs[d_open]["kind"] == "Builder"
    assert specs[d_open]["target_id"] == str(tgt)
    assert specs[d_open]["target_kind"] == "Goal"
    # Target proved → work done, outcome propagates from the goal terminal →
    # skip (the parked-target check handles this, not a produced_goal guard).
    db.update_goal_status(conn, tgt, "proved")
    assert d_open not in {s["decision_id"]
                          for s in db.null_inject_redispatch_specs(conn)}
    # Target shelved (parked) → skip (redispatch would re-spin it forever).
    db.update_goal_status(conn, tgt, "shelved")
    assert d_open not in {s["decision_id"]
                          for s in db.null_inject_redispatch_specs(conn)}


def test_null_inject_redispatch_only_latest_inject_per_target(
    conn: sqlite3.Connection,
) -> None:
    """Regression (P13 4284, 2026-06-15): per goal-target, ONLY the latest
    Inject is redispatchable — every earlier one (ANY kind) is superseded. A
    thrash loop / re-decision across batches reopens the goal and would
    otherwise resurrect the stale earlier inject. Crucially this covers the
    CROSS-KIND case (Builder→Backward routing switch): the live bug was a stale
    Builder #924 re-launched alongside the new Backward #926 on 4284, because
    the prior same-(target,kind) collapse only deduped within a kind. Forward
    targets the problem (distinct lemmas, own target) — never superseded."""
    _insert_problem(conn, name="alpha", bootstrap_done=1)
    g = _insert_sub(conn, "alpha", "g")  # open
    d_old = _insert_null_inject(conn, problem="alpha", pipeline="Builder",
                                target_id=g, produced_goal_id=g)
    d_mid = _insert_null_inject(conn, problem="alpha", pipeline="Builder",
                                target_id=g, produced_goal_id=g)
    f1 = _insert_null_inject(conn, problem="alpha", pipeline="Forward")
    f2 = _insert_null_inject(conn, problem="alpha", pipeline="Forward")
    # Strategist switches Builder→Backward on g: this Backward is now latest.
    d_bwd = _insert_null_inject(conn, problem="alpha", pipeline="Backward",
                                target_id=g)
    ids = {s["decision_id"] for s in db.null_inject_redispatch_specs(conn)}
    assert d_bwd in ids        # latest inject on g = the live intent
    assert d_old not in ids    # superseded (older Builder)
    assert d_mid not in ids    # superseded — INCL. cross-kind by the Backward
    assert {f1, f2} <= ids     # both Forwards kept (distinct lemmas, own target)


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
               target_kind="Problem", priority=10, decision_id=d1,
               problem="alpha")
    reconcile_stuck_states(conn, running=set())
    assert conn.execute(
        "SELECT count(*) c FROM queue WHERE decision_id=?", (d1,)
    ).fetchone()["c"] == 1


# ---------------------------------------------------------------------
# _dispatch_is_duplicate — pop-loop dedup (Builder capped one-per-goal)
# ---------------------------------------------------------------------

def test_dispatch_dup_exact_triple_match() -> None:
    """Base case (any kind): an exact (target, kind, decision_id) match
    in the running set is a duplicate; a different decision_id is not."""
    running = {("7", "Backward", 3)}
    assert _dispatch_is_duplicate(running, "7", "Backward", 3)
    assert not _dispatch_is_duplicate(running, "7", "Backward", 4)


def test_dispatch_dup_second_builder_same_goal_diff_decision() -> None:
    """THE FIX: a goal hosts at most ONE Builder regardless of
    decision_id. An organic Builder (decision_id=None) in flight blocks a
    routine/recovery-injected Builder (decision_id set) on the same goal,
    and vice-versa — they would race the single proofs/L_<slug>.lean and a
    failing loser could stub-clobber the winner's proof."""
    assert _dispatch_is_duplicate({("42", "Builder", None)}, "42",
                                  "Builder", 99)
    assert _dispatch_is_duplicate({("42", "Builder", 99)}, "42",
                                  "Builder", None)


def test_dispatch_dup_parallel_backward_or_node_allowed() -> None:
    """Backward is NOT capped per goal: parallel OR-node decompositions
    (distinct decision_id) each write an isolated _strategy_<sid>.lean and
    are intentionally allowed to run concurrently."""
    assert not _dispatch_is_duplicate({("42", "Backward", 1)}, "42",
                                      "Backward", 2)


def test_dispatch_dup_builder_on_other_goal_not_blocked() -> None:
    """A Builder in flight on one goal must not block a Builder on a
    different goal."""
    assert not _dispatch_is_duplicate({("42", "Builder", None)}, "43",
                                      "Builder", None)
