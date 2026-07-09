"""Stall condition-4 false-activity + park escalation (2026-07-09
putnam_2025_b6 silent-idle wedge).

The disease: a NULL-outcome Forward-Inject's produced goal sat
`attempting` while its entire subtree was parked (strategies all
dead/'stalled', zero open goals, nothing queued). The old
status-shallow active-check counted it ACTIVE → suppressed T4 forever,
while the park machinery waited for the Strategist wake that
suppression blocked (mutual deadlock).

Fix A (predicate): `has_active_inflight_inject` recurses — an
`attempting` produced goal counts active only with a live dispatch
frontier (`db._subtree_has_live_frontier`).
Fix B (state): parking a goal's LAST live route escalates the goal to
`pending_strategist_review` (T2) via
`transitions._maybe_review_goal_out_of_routes`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.state import db as _db
from Tooling.state import transitions as _tr

P = "Test.wedge"


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, 'Problems/Test/wedge/Manifest.md', ?)",
        (P, _db.now()))
    conn.commit()
    return conn


def _goal(conn, slug: str, status: str = "open",
          origin: str = "forward") -> int:
    return _db.insert_goal(
        conn, problem=P, slug=slug,
        lean_path=f"Problems/Test/wedge/proofs/L_{slug}.lean",
        statement="T", origin=origin, status=status)


def _strategy(conn, goal_id: int, status: str = "proposed") -> int:
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', ?, '', 'test', ?)",
        (goal_id, status, _db.now()))
    return int(cur.lastrowid)


def _link(conn, sid: int, gid: int, pos: int = 0) -> None:
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, ?)", (sid, gid, pos))


def _inject(conn, *, produced_goal: int | None = None,
            produced_strategy: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, batch_id,"
        " produced_goal_id, produced_strategy_id, outcome,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Inject',"
        " '{\"pipeline\":\"Forward\"}', 'b1', ?, ?, NULL, ?, ?)",
        (P, produced_goal, produced_strategy, _db.now(), _db.now()))
    conn.commit()
    return int(cur.lastrowid)


def _parked_chain(conn) -> tuple[int, int]:
    """The putnam_2025_b6 shape: gA(attempting) —proposed→
    [gB(attempting), gC(proved)]; gB's routes = one dead + one
    'stalled' over shelved leaves. Returns (gA, gB)."""
    ga = _goal(conn, "ga", status="attempting")
    gb = _goal(conn, "gb", status="attempting")
    gc = _goal(conn, "gc", status="proved")
    sa = _strategy(conn, ga, "proposed")
    _link(conn, sa, gb, 0)
    _link(conn, sa, gc, 1)
    _strategy(conn, gb, "dead")
    sb = _strategy(conn, gb, "stalled")
    leaf = _goal(conn, "leaf", status="shelved")
    _link(conn, sb, leaf)
    conn.commit()
    return ga, gb


# ---------------------------------------------------------------------
# Fix A — has_active_inflight_inject recursion
# ---------------------------------------------------------------------

def test_parked_attempting_chain_not_active(tmp_path: Path) -> None:
    """The wedge repro: NULL Inject → attempting goal whose subtree is
    fully parked → NOT active; the problem IS stalled (T4 may wake)."""
    conn = _conn(tmp_path)
    ga, _gb = _parked_chain(conn)
    _inject(conn, produced_goal=ga)
    assert _db.has_active_inflight_inject(conn, P) is False
    assert _db.is_problem_stalled(conn, P) is True
    conn.close()


def test_live_frontier_keeps_suppression(tmp_path: Path) -> None:
    """Same chain but one leaf is genuinely open → active, and cond-2
    sees the dispatchable goal anyway."""
    conn = _conn(tmp_path)
    ga, gb = _parked_chain(conn)
    s_live = _strategy(conn, gb, "proposed")
    open_leaf = _goal(conn, "open_leaf", status="open", origin="backward")
    _link(conn, s_live, open_leaf)
    conn.commit()
    _inject(conn, produced_goal=ga)
    assert _db.has_active_inflight_inject(conn, P) is True
    assert _db.is_problem_stalled(conn, P) is False
    conn.close()


def test_pending_review_descendant_is_frontier(tmp_path: Path) -> None:
    """A queued T2 review in the subtree counts as a frontier — the
    Strategist is already on its way; suppression stays."""
    conn = _conn(tmp_path)
    ga, gb = _parked_chain(conn)
    s_live = _strategy(conn, gb, "proposed")
    rev = _goal(conn, "rev", status="pending_strategist_review",
                origin="backward")
    _link(conn, s_live, rev)
    conn.commit()
    _inject(conn, produced_goal=ga)
    assert _db.has_active_inflight_inject(conn, P) is True
    conn.close()


def test_open_produced_goal_still_active(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    g = _goal(conn, "fresh", status="open")
    _inject(conn, produced_goal=g)
    assert _db.has_active_inflight_inject(conn, P) is True
    conn.close()


def test_shelved_produced_goal_stays_inactive(tmp_path: Path) -> None:
    """P13 regression pin: a shelved-produced NULL inject is parked,
    not in flight — must not suppress (the Phase 11 disease)."""
    conn = _conn(tmp_path)
    g = _goal(conn, "parked", status="shelved")
    _inject(conn, produced_goal=g)
    assert _db.has_active_inflight_inject(conn, P) is False
    conn.close()


def test_strategy_branch_recurses(tmp_path: Path) -> None:
    """produced_strategy_id branch: an `attempting` subgoal with a
    fully-parked subtree no longer counts; an open grandchild does."""
    conn = _conn(tmp_path)
    ga, gb = _parked_chain(conn)
    # The inject produced gA's strategy (Inject(Backward) shape).
    sid = int(conn.execute(
        "SELECT id FROM strategies WHERE goal_id = ?", (ga,)
    ).fetchone()[0])
    _inject(conn, produced_strategy=sid)
    assert _db.has_active_inflight_inject(conn, P) is False
    # Open grandchild under gb → frontier reappears.
    s_live = _strategy(conn, gb, "proposed")
    open_leaf = _goal(conn, "deep_open", status="open", origin="backward")
    _link(conn, s_live, open_leaf)
    conn.commit()
    assert _db.has_active_inflight_inject(conn, P) is True
    conn.close()


# ---------------------------------------------------------------------
# Fix B — park last route → T2 review escalation
# ---------------------------------------------------------------------

def test_park_last_route_escalates_to_review(tmp_path: Path) -> None:
    """Parking a goal's last 'proposed' strategy flips the goal to
    pending_strategist_review and enqueues the T2 Strategist."""
    conn = _conn(tmp_path)
    pa = _goal(conn, "pa", status="attempting")  # forward → detached=1
    sp = _strategy(conn, pa, "proposed")
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _link(conn, sp, leaf)
    conn.commit()

    _tr._maybe_stall_parent_strategies(conn, leaf)

    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sp,)).fetchone()
    assert str(s["status"]) == "stalled"
    g = _db.get_goal(conn, pa)
    assert str(g["status"]) == "pending_strategist_review"
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
        " AND target_id = ?", (P,)).fetchone()
    assert q["n"] == 1
    conn.close()


def test_park_with_remaining_route_stays_attempting(
        tmp_path: Path) -> None:
    """A second live strategy on the goal → no escalation."""
    conn = _conn(tmp_path)
    pa = _goal(conn, "pa2", status="attempting")
    sp = _strategy(conn, pa, "proposed")
    leaf = _goal(conn, "pleaf2", status="shelved", origin="backward")
    _link(conn, sp, leaf)
    s2 = _strategy(conn, pa, "proposed")
    alive = _goal(conn, "alive2", status="open", origin="backward")
    _link(conn, s2, alive)
    conn.commit()

    _tr._maybe_stall_parent_strategies(conn, leaf)

    assert str(conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sp,)
    ).fetchone()["status"]) == "stalled"
    assert str(_db.get_goal(conn, pa)["status"]) == "attempting"
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()["n"] == 0
    conn.close()
