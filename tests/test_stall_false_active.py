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


def test_bfs_routes_over_budget_open_goal_to_review(
        tmp_path: Path) -> None:
    """Organic budget guard (putnam_2025_b6 hot moot loop, 4,317
    pipelines): an OPEN goal at/over SHELVE_THRESHOLD must go to T2
    review, never to a dispatch whose retry pre-loop would moot it and
    leave it open for the next tick."""
    from Tooling.core.dispatcher import bfs_refill
    from Tooling.state import thresholds
    conn = _conn(tmp_path)
    g = _goal(conn, "over_budget", status="open")
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (thresholds.SHELVE_THRESHOLD, g))
    conn.commit()

    bfs_refill(conn, running=set())

    assert str(_db.get_goal(conn, g)["status"]) == (
        "pending_strategist_review")
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind IN "
        "('Backward','Builder')").fetchone()["n"] == 0
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
        " AND target_id = ?", (P,)).fetchone()["n"] == 1
    conn.close()


def test_bfs_dispatches_goal_with_remaining_budget(
        tmp_path: Path) -> None:
    """Below the threshold the organic path is untouched."""
    from Tooling.core.dispatcher import bfs_refill
    from Tooling.state import thresholds
    conn = _conn(tmp_path)
    g = _goal(conn, "has_budget", status="open")
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (thresholds.SHELVE_THRESHOLD - 1, g))
    conn.commit()

    bfs_refill(conn, running=set())

    assert str(_db.get_goal(conn, g)["status"]) == "open"
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE target_id = ?",
        (str(g),)).fetchone()["n"] == 1
    conn.close()


# ---------------------------------------------------------------------
# 2026-07-11 — T2 wake-pump livelock (b6, 301 spawns / 2.05M out-tokens):
# gate-side "dispatch" frontier, has_live_inflight_inject narrowing,
# review-discharge rule, bfs review dedup, predicate-alignment invariant
# ---------------------------------------------------------------------

def _pending_review_wedge(conn) -> tuple[int, int]:
    """The b6 pump shape: NULL Inject → gA(attempting) —proposed→
    gRev(pending_strategist_review). The pending review both pumps T2
    wakes AND (pre-fix) opened the anti-idle gate's escape hatch."""
    ga = _goal(conn, "wga", status="attempting")
    s = _strategy(conn, ga, "proposed")
    grev = _goal(conn, "wrev", status="pending_strategist_review",
                 origin="backward")
    _link(conn, s, grev)
    conn.commit()
    _inject(conn, produced_goal=ga)
    return ga, grev


def test_dispatch_frontier_excludes_pending_review(tmp_path: Path) -> None:
    """The same subtree reads differently per semantics: a pending
    review is a frontier for the STALL side (T2 will come; T4 must not
    race) but NOT for the gate side (the queued handler IS the
    strategist standing at the gate — self-reference)."""
    conn = _conn(tmp_path)
    ga, grev = _pending_review_wedge(conn)
    assert _db._subtree_has_live_frontier(conn, ga, frontier="stall") is True
    assert _db._subtree_has_live_frontier(
        conn, ga, frontier="dispatch") is False
    # An open goal is a frontier for BOTH.
    s2 = _strategy(conn, ga, "proposed")
    leaf = _goal(conn, "wopen", status="open", origin="backward")
    _link(conn, s2, leaf)
    conn.commit()
    assert _db._subtree_has_live_frontier(
        conn, ga, frontier="dispatch") is True
    conn.close()


def test_dispatch_frontier_sees_queued_worker(tmp_path: Path) -> None:
    """A queued/leased worker on a subtree goal moves without the
    Strategist → gate-side frontier (the gate has no cond-3 to see
    workers for it, so the frontier looks at the queue itself)."""
    conn = _conn(tmp_path)
    ga, grev = _pending_review_wedge(conn)
    assert _db._subtree_has_live_frontier(
        conn, ga, frontier="dispatch") is False
    _db.enqueue(conn, kind="Backward", target_id=str(grev),
                target_kind="Goal", priority=5, problem=P)
    conn.commit()
    assert _db._subtree_has_live_frontier(
        conn, ga, frontier="dispatch") is True
    conn.close()


def test_live_inject_wedge_is_not_live(tmp_path: Path) -> None:
    """b6 leak repro: a NULL inject whose produced work bottoms out in
    pending_strategist_review must NOT count as live at the gate."""
    conn = _conn(tmp_path)
    _pending_review_wedge(conn)
    assert _db.has_live_inflight_inject(conn, P) is False
    conn.close()


def test_live_inject_producing_worker_still_live(tmp_path: Path) -> None:
    """The original broad-predicate reason survives the narrowing: a
    Forward inject whose worker has not yet registered its lemma
    (produced ids both NULL) is in flight — Strategist may wait."""
    conn = _conn(tmp_path)
    _inject(conn)  # produced_goal/strategy both NULL
    assert _db.has_live_inflight_inject(conn, P) is True
    conn.close()


def test_live_inject_open_subtree_is_live(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    g = _goal(conn, "lfresh", status="open")
    _inject(conn, produced_goal=g)
    assert _db.has_live_inflight_inject(conn, P) is True
    conn.close()


def test_review_discharge_rejects_notes_only_batch(tmp_path: Path) -> None:
    """While a goal waits in pending_strategist_review, an
    EmitDirective-only batch discharges nothing — reject; the same
    batch plus a decision TARGETING the reviewed goal passes."""
    import json
    from Tooling.pipeline import strategist
    conn = _conn(tmp_path)
    _ga, grev = _pending_review_wedge(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "EmitDirective", "scope": f"problem:{P}",
         "body": "wall notes", "reason": "record the wall"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem=P)
    assert "review not discharged" in err and f"g{grev}" in err
    ds2, _ = strategist.parse_decisions(json.dumps([
        {"kind": "EmitDirective", "scope": f"problem:{P}",
         "body": "wall notes", "reason": "record the wall"},
        {"kind": "Inject", "pipeline": "Backward",
         "target_goal_id": grev, "brief": "## Need\nfresh attack"},
    ]))
    err2 = strategist.verify_decisions(ds2, conn, problem=P)
    assert "review not discharged" not in err2
    conn.close()


def test_alignment_invariant_stalled_implies_gate_rejects(
        tmp_path: Path) -> None:
    """Rule-6 invariant for the P13 'two predicates disagree' disease
    (4284 spin → cond-4 deadlock → the b6 Noop-gate leak): on wedge
    shapes, NEVER (problem stalled AND the gate accepts a notes-only
    batch). Checked on both the b6 pending-review pump shape and the
    fully-parked blocked-root shape."""
    import json
    from Tooling.pipeline import strategist

    def gate_accepts_notes_only(conn) -> bool:
        ds, _ = strategist.parse_decisions(json.dumps([
            {"kind": "EmitDirective", "scope": f"problem:{P}",
             "body": "notes", "reason": "notes"},
        ]))
        return strategist.verify_decisions(ds, conn, problem=P) == ""

    # Shape 1 — b6 pump: pending review present.
    conn = _conn(tmp_path)
    _pending_review_wedge(conn)
    assert not (_db.is_problem_stalled(conn, P)
                and gate_accepts_notes_only(conn))
    assert gate_accepts_notes_only(conn) is False  # review-discharge
    conn.close()

    # Shape 2 — fully-parked tree under a blocked root, no pending
    # review: stalled, and the root-blocked gate must reject.
    conn2 = sqlite3.connect(str(tmp_path / "asterism2.db"))
    conn2.row_factory = sqlite3.Row
    _db.init_schema(conn2)
    conn2.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, 'Problems/Test/wedge/Manifest.md', ?)",
        (P, _db.now()))
    root = _db.insert_goal(
        conn2, problem=P, slug="main",
        lean_path="Problems/Test/wedge/Root.lean",
        statement="T", origin="root", status="shelved")
    _inject(conn2, produced_goal=root)
    conn2.commit()
    stalled = _db.is_problem_stalled(conn2, P)
    accepts = gate_accepts_notes_only(conn2)
    assert not (stalled and accepts)
    assert accepts is False  # blocked root + no live inject → reject
    conn2.close()


def test_bfs_review_dedup_once_per_attempts(tmp_path: Path) -> None:
    """Fuel line #2 of the pump: after the Strategist answers the
    over-budget review (e.g. Reopen — goal open again, attempts
    unchanged), bfs must NOT re-escalate; a NEW attempt re-arms it."""
    from Tooling.core.dispatcher import bfs_refill
    from Tooling.state import thresholds
    conn = _conn(tmp_path)
    g = _goal(conn, "dedup_goal", status="open")
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (thresholds.SHELVE_THRESHOLD, g))
    # An old attempt, then the Strategist's answer AFTER it.
    for pid in ("p1", "p2"):
        conn.execute(
            "INSERT INTO pipelines (id, kind, target_id, target_kind,"
            " status, outcome, started_at, finished_at)"
            " VALUES (?, 'Backward', ?, 'Goal', 'failed', 'failed',"
            " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
            (pid, str(g)))
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, ts)"
        " VALUES (?, 'Goal', 'p1', 'agent_declined', '',"
        " '2026-01-01T00:00:00+00:00')", (g,))
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, payload, batch_id,"
        " outcome, created_at, updated_at)"
        " VALUES (?, 0, 'pending_review', 'Reopen', ?, '{}', NULL,"
        " 'success', '2026-01-02T00:00:00+00:00',"
        " '2026-01-02T00:00:00+00:00')", (P, g))
    conn.commit()

    bfs_refill(conn, running=set())
    assert str(_db.get_goal(conn, g)["status"]) == "open"  # held quietly
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM queue").fetchone()["n"] == 0

    # A NEW attempt after the answer re-arms the escalation.
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, ts)"
        " VALUES (?, 'Goal', 'p2', 'agent_declined', '',"
        " '2026-01-03T00:00:00+00:00')", (g,))
    conn.commit()
    bfs_refill(conn, running=set())
    assert str(_db.get_goal(conn, g)["status"]) == (
        "pending_strategist_review")
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
