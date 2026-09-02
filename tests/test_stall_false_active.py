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

def _top(conn, problem):
    """The problem's top-group id as the queue stores it (v35: the
    Strategist seat is keyed by group, not by problem)."""
    from Tooling.state import groups as _g
    return str(_g.ensure_top_group(conn, problem))



def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)",
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
        " AND target_id = ?", (_top(conn, P),)).fetchone()
    assert q["n"] == 1
    conn.close()


def _confirm_shelve(conn, goal_id: int, *, batch: str) -> int:
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, batch_id, outcome,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'pending_review', 'ConfirmShelve', CAST(? AS TEXT),"
        " ?, 'success', ?, ?)",
        (P, goal_id, batch, _db.now(), _db.now()))
    conn.commit()
    return int(cur.lastrowid)


def _mint_inject(conn, *, batch: str, outcome: str | None) -> int:
    """A no-target Inject sibling — the helper brick a ConfirmShelve
    promises. `outcome=None` = still in flight."""
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, outcome,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'pending_review', 'Inject', ?, ?, ?, ?)",
        (P, batch, outcome, _db.now(), _db.now()))
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------
# Promise-aware aliveness (2026-07-30, b6_1 four-level review cascade)
# ---------------------------------------------------------------------

def test_promised_park_does_not_escalate_the_parent(tmp_path: Path) -> None:
    """A shelved sub-goal whose promised helper batch is still in flight
    keeps the parent WAITING — no stall, no review wake.

    b6_1 07-30: the leaf was parked by a ConfirmShelve that minted two
    helper bricks in the same batch, yet the parent's only strategy was
    stalled and the parent (attempts=0, never failed) was handed to a
    review wake; the Strategist, asked about a goal whose only blocker
    was the parked child, answered ConfirmShelve — four levels, root
    included, four full batch cycles. `pending_strategist_review`
    already counts as alive because a wake is scheduled for it; a park
    with a live promise has the same property."""
    conn = _conn(tmp_path)
    pa = _goal(conn, "pa", status="attempting")
    sp = _strategy(conn, pa, "proposed")
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _link(conn, sp, leaf)
    _confirm_shelve(conn, leaf, batch="promise-1")
    _mint_inject(conn, batch="promise-1", outcome=None)  # in flight

    _tr._maybe_stall_parent_strategies(conn, leaf)

    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sp,)).fetchone()
    assert str(s["status"]) == "proposed"        # still waiting
    assert str(_db.get_goal(conn, pa)["status"]) == "attempting"
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
        " AND target_id = ?", (_top(conn, P),)).fetchone()
    assert q["n"] == 0                           # no churn wake
    conn.close()


def _delegate_row(conn, *, batch: str, outcome: str | None) -> int:
    """A Delegate sibling — a park waiting on a sub-group's charter.
    `outcome=None` = the group is still active; group terminal fills it
    (state.groups.set_status)."""
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, outcome,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'pending_review', 'Delegate', ?, ?, ?, ?)",
        (P, batch, outcome, _db.now(), _db.now()))
    conn.commit()
    return int(cur.lastrowid)


def test_park_waiting_on_a_delegate_keeps_the_parent_waiting(
        tmp_path: Path) -> None:
    """v35 seam, live on the Frankl opener (2026-08-06): the batch's
    mint resolved in minutes while the Delegate (the actual wait
    target, the entropy sub-group) stayed open — with only 'Inject'
    counted as a promise carrier the root was handed to a review wake
    to adjudicate a non-question, the exact cascade b047b910 killed.
    A Delegate with outcome NULL is a live promise; the group's
    terminal transition fills it and completes the batch."""
    conn = _conn(tmp_path)
    pa = _goal(conn, "pa", status="attempting")
    sp = _strategy(conn, pa, "proposed")
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _link(conn, sp, leaf)
    _confirm_shelve(conn, leaf, batch="promise-d")
    _mint_inject(conn, batch="promise-d", outcome="success")   # landed
    _delegate_row(conn, batch="promise-d", outcome=None)       # group live

    assert _tr._awaiting_promised_batch(conn, leaf)
    _tr._maybe_stall_parent_strategies(conn, leaf)
    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sp,)).fetchone()
    assert str(s["status"]) == "proposed"        # still waiting
    assert str(_db.get_goal(conn, pa)["status"]) == "attempting"

    # Group reaches terminal → outcome filled → promise DUE.
    conn.execute(
        "UPDATE strategist_decisions SET outcome='failed:returned'"
        " WHERE decision_kind='Delegate' AND batch_id='promise-d'")
    conn.commit()
    assert not _tr._awaiting_promised_batch(conn, leaf)


def test_park_without_a_promise_still_escalates(tmp_path: Path) -> None:
    """No promise (ConfirmShelve batched with no Inject) → unchanged
    2026-07-09 behaviour: stall + escalate, or the goal is stranded
    (BFS dispatches only `open`)."""
    conn = _conn(tmp_path)
    pa = _goal(conn, "pa", status="attempting")
    sp = _strategy(conn, pa, "proposed")
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _link(conn, sp, leaf)
    _confirm_shelve(conn, leaf, batch="lonely")   # no Inject sibling

    _tr._maybe_stall_parent_strategies(conn, leaf)

    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sp,)).fetchone()
    assert str(s["status"]) == "stalled"
    assert (str(_db.get_goal(conn, pa)["status"])
            == "pending_strategist_review")
    conn.close()


def test_promise_that_came_due_escalates_again(tmp_path: Path) -> None:
    """Once every promised Inject has settled the promise is DUE, not
    live: `maybe_enqueue_inject_batch_done` has put the Strategist wake
    in front of it, and if that wake leaves the goal parked with no
    fresh promise the branch is genuinely out of routes. No timer is
    involved — the batch reaching terminal state IS the signal."""
    conn = _conn(tmp_path)
    pa = _goal(conn, "pa", status="attempting")
    sp = _strategy(conn, pa, "proposed")
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _link(conn, sp, leaf)
    _confirm_shelve(conn, leaf, batch="promise-2")
    _mint_inject(conn, batch="promise-2", outcome="success")   # landed

    assert not _tr._awaiting_promised_batch(conn, leaf)
    _tr._maybe_stall_parent_strategies(conn, leaf)
    assert (str(_db.get_goal(conn, pa)["status"])
            == "pending_strategist_review")

    # ... and a FRESH promise on the same goal makes it wait again —
    # the user's case: the Strategist re-parks it and mints another
    # helper instead of reviving. No expiry rule can express this; the
    # latest ConfirmShelve's batch does.
    _confirm_shelve(conn, leaf, batch="promise-3")
    _mint_inject(conn, batch="promise-3", outcome=None)
    assert _tr._awaiting_promised_batch(conn, leaf)
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
        " AND target_id = ?", (_top(conn, P),)).fetchone()["n"] == 1
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
    notes-only batch (Noop; held FetchPaper, and EmitDirective before
    RS-B — both retired) discharges nothing — reject; the same
    batch plus a decision TARGETING the reviewed goal passes."""
    import json
    from Tooling.pipeline import strategist
    conn = _conn(tmp_path)
    _ga, grev = _pending_review_wedge(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "record the wall"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem=P)
    assert "review not discharged" in err and f"g{grev}" in err
    ds2, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "record the wall"},
        {"kind": "Inject", "pipeline": "Backward",
         "target_goal_id": grev, "proof": "## Need\nfresh attack"},
    ]))
    err2 = strategist.verify_decisions(ds2, conn, problem=P)
    assert "review not discharged" not in err2
    conn.close()


def test_predicted_batch_delta_counts_transitions_not_kinds(
        tmp_path: Path) -> None:
    """FSM §2.3: the stall-advance currency. Self-edges (re-confirm a
    shelved goal, shelve a hard terminal, re-mark) count ZERO; real
    edges and new dispatches count."""
    from Tooling.pipeline.strategist import Decision
    conn = _conn(tmp_path)
    g_open = _goal(conn, "d_open", status="open")
    g_shelved = _goal(conn, "d_shelved", status="shelved")
    g_proved = _goal(conn, "d_proved", status="proved")
    conn.execute("UPDATE goals SET is_deliverable = 1 WHERE id = ?",
                 (g_proved,))
    g_proved2 = _goal(conn, "d_proved2", status="proved")
    conn.commit()

    def delta(*ds) -> int:
        return _tr.predicted_batch_delta(conn, list(ds))

    assert delta(Decision(kind="Inject")) == 1
    # AttemptDisproof retired 2026-08-04 — no longer a state-moving kind
    # (the verifier rejects it before commit anyway).
    assert delta(Decision(kind="AttemptDisproof", target_id=g_open)) == 0
    assert delta(Decision(kind="Ingest")) == 1
    assert delta(Decision(kind="RequestUserAmend")) == 1
    assert delta(Decision(kind="Noop")) == 0
    assert delta(Decision(kind="EmitDirective")) == 0
    # ConfirmShelve: live target = edge; shelved/proved target = no-op.
    assert delta(Decision(kind="ConfirmShelve", target_id=g_open)) == 1
    assert delta(Decision(kind="ConfirmShelve", target_id=g_shelved)) == 0
    assert delta(Decision(kind="ConfirmShelve", target_id=g_proved)) == 0
    # MarkDeliverable: proved+unmarked = edge; marked / unproved = no-op.
    assert delta(Decision(kind="MarkDeliverable", target_id=g_proved2)) == 1
    assert delta(Decision(kind="MarkDeliverable", target_id=g_proved)) == 0
    assert delta(Decision(kind="MarkDeliverable", target_id=g_open)) == 0
    # Batch sums; one real action carries a zero-delta companion.
    assert delta(Decision(kind="ConfirmShelve", target_id=g_shelved),
                 Decision(kind="Inject")) == 1
    conn.close()


def test_stall_advance_gate_rejects_zero_delta(tmp_path: Path) -> None:
    """FSM §3.1 — the pure-NL re-confirm pump (simple_loop_conjecture
    2026-07-12, 9+ consecutive strategist wakes): a stalled rootless
    problem must move ≥1 state or dispatch new work per wake. Zero-delta
    batches (re-confirm / Noop) bounce with the researcher-charge
    message; a real Inject passes; periodic triggers and non-stalled
    problems are untouched."""
    import json
    from Tooling.pipeline import strategist
    conn = _conn(tmp_path)
    _goal(conn, "done", status="proved")
    g_sh = _goal(conn, "parked", status="shelved")
    conn.commit()
    assert _db.is_problem_stalled(conn, P) is True

    reconfirm = [{"kind": "ConfirmShelve", "target_goal_id": g_sh,
                  "reason": "still parked"}]
    ds, _ = strategist.parse_decisions(json.dumps(reconfirm))
    err = strategist.verify_decisions(
        ds, conn, problem=P, trigger_kind="inject_batch_done")
    assert "changes nothing" in err and "researcher" in err

    noop = [{"kind": "Noop", "reason": "honest idle"}]
    ds2, _ = strategist.parse_decisions(json.dumps(noop))
    err2 = strategist.verify_decisions(
        ds2, conn, problem=P, trigger_kind="inject_batch_done")
    assert "changes nothing" in err2

    with_inject = reconfirm + [{
        "kind": "Inject", "pipeline": "Forward",
        "proof": "## Need\na genuinely new brick"}]
    ds3, _ = strategist.parse_decisions(json.dumps(with_inject))
    err3 = strategist.verify_decisions(
        ds3, conn, problem=P, trigger_kind="inject_batch_done")
    assert "changes nothing" not in err3

    # The periodic wake keeps its curation-legal exemption.
    err4 = strategist.verify_decisions(
        ds, conn, problem=P, trigger_kind="routine")
    assert "changes nothing" not in err4

    # A live in-flight inject → not stalled → rule inert.
    g_live = _goal(conn, "inflight", status="open")
    _inject(conn, produced_goal=g_live)
    assert _db.is_problem_stalled(conn, P) is False
    err5 = strategist.verify_decisions(
        ds, conn, problem=P, trigger_kind="inject_batch_done")
    assert "changes nothing" not in err5
    conn.close()


def test_markdeliverable_requires_proved_unmarked(tmp_path: Path) -> None:
    """FSM §3.2: marking is a real edge only for a PROVED forward node
    not already marked BY THIS GROUP — unproved marks and same-group
    re-marks are per-item errors. (Since the 2026-08-17 owner ruling a
    mark is shareable: another group's mark, or a bare flag with no
    attributed decision row, does not block a first mark by this group
    — see `test_a_mark_is_shareable_across_groups`.)"""
    import json
    from Tooling.pipeline import strategist
    from Tooling.state import groups as _groups
    conn = _conn(tmp_path)
    g_open = _goal(conn, "m_open", status="open")
    g_marked = _goal(conn, "m_marked", status="proved")
    conn.execute("UPDATE goals SET is_deliverable = 1 WHERE id = ?",
                 (g_marked,))
    top = _groups.ensure_top_group(conn, P)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, payload,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'MarkDeliverable', ?, ?, '{}', 't', 't')",
        (P, top, g_marked))
    conn.commit()
    ds, _ = strategist.parse_decisions(json.dumps(
        [{"kind": "MarkDeliverable", "target_goal_id": g_open}]))
    assert "PROVED" in strategist.verify_decisions(ds, conn, problem=P)
    ds2, _ = strategist.parse_decisions(json.dumps(
        [{"kind": "MarkDeliverable", "target_goal_id": g_marked}]))
    assert "already marked" in strategist.verify_decisions(
        ds2, conn, problem=P)
    conn.close()


def test_amend_identical_rerequest_rejected(tmp_path: Path) -> None:
    """FSM §3.3 human-attention guard: a RequestUserAmend byte-identical
    to an already-adjudicated one is mechanically rejected; a changed
    proposal is a new ask."""
    import json
    from Tooling.pipeline import strategist
    conn = _conn(tmp_path)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at) VALUES (?, 0, 'routine', 'RequestUserAmend', ?,"
        " 'rejected', ?, ?)",
        (P, json.dumps({"file": "charter", "proposed_body": "OLD ASK",
                        "question": "q?"}), _db.now(), _db.now()))
    conn.commit()
    req = {"kind": "RequestUserAmend", "reason": "statement wrong",
           "file": "charter", "question": "q?",
           "proposed_body": "OLD ASK"}
    ds, _ = strategist.parse_decisions(json.dumps([req]))
    assert "already adjudicated" in strategist.verify_decisions(
        ds, conn, problem=P)
    req2 = dict(req, proposed_body="NEW ASK")
    ds2, _ = strategist.parse_decisions(json.dumps([req2]))
    assert "already adjudicated" not in strategist.verify_decisions(
        ds2, conn, problem=P)
    conn.close()


def test_review_discharge_exempts_periodic_wakes(tmp_path: Path) -> None:
    """The periodic wake outranks events (2026-07-12): a routine wake
    may fire while goals await review, and its curation/notes batch must
    NOT be bounced by the discharge rule — disposal belongs to the
    frontier wakes, whose pressure re-arms every tick. Frontier trigger
    kinds (and the kind-less legacy default) keep the rule."""
    import json
    from Tooling.pipeline import strategist
    conn = _conn(tmp_path)
    _ga, grev = _pending_review_wedge(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "clean audit"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem=P,
                                      trigger_kind="routine")
    assert "review not discharged" not in err
    for kind in ("pending_review", "inject_batch_done", ""):
        err = strategist.verify_decisions(ds, conn, problem=P,
                                          trigger_kind=kind)
        assert "review not discharged" in err and f"g{grev}" in err, kind
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
            {"kind": "Noop", "reason": "notes"},
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
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)",
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
    over-budget review with a verdict that leaves the goal open at the
    same attempts count, bfs must NOT re-escalate; a NEW attempt
    re-arms it."""
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
        " VALUES (?, 0, 'pending_review', 'Inject', ?, '{}', NULL,"
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


def test_stall_trigger_kind_is_batch_done_like_everywhere(
    tmp_path: Path,
) -> None:
    """v43 identity split (owner ruling 2026-08-24): the T4 rescue
    records `trigger_kind='stall'` so the rescue rate is SQL-visible,
    but BEHAVES as inject_batch_done — the mandatory-advance gate must
    fire for it a fortiori (a stall wake IS the stall), and the prompt
    it reads is inject_batch_done.md (there is no stall.md)."""
    import json
    from Tooling.pipeline import strategist
    conn = _conn(tmp_path)
    _goal(conn, "done", status="proved")
    g_sh = _goal(conn, "parked", status="shelved")
    conn.commit()
    assert _db.is_problem_stalled(conn, P) is True

    reconfirm = [{"kind": "ConfirmShelve", "target_goal_id": g_sh,
                  "reason": "still parked"}]
    ds, _ = strategist.parse_decisions(json.dumps(reconfirm))
    err = strategist.verify_decisions(
        ds, conn, problem=P, trigger_kind="stall")
    assert "changes nothing" in err and "researcher" in err

    assert "stall" in strategist.TRIGGER_KINDS
    # 2026-08-30: routine_fired (the wake a fired routine audit seats)
    # joined the batch-done family.
    assert strategist.BATCH_DONE_LIKE == {"inject_batch_done", "stall",
                                          "routine_fired"}
    # No stall.md exists nor should one: the split is for the DB record.
    from Tooling.pipeline import PROMPT_DIR
    assert not (PROMPT_DIR / "strategist" / "stall.md").exists()
    assert (PROMPT_DIR / "strategist" / "inject_batch_done.md").exists()
    conn.close()


# ---------------------------------------------------------------------
# human authority (human_interface_design.md §3.2) — a person's park is
# a TERMINAL stop, not a machine park waiting on a prerequisite
# ---------------------------------------------------------------------


def _human_confirm_shelve(conn, goal_id: int, *,
                          batch: "str | None" = None) -> int:
    """The row a human `ConfirmShelve` command lands (§3.3): same table,
    same kind, `trigger_kind='human'` and `actor='human'`. Unpaired by
    design — the pairing rule exists because the MACHINE may never stop
    itself, and the human is the one role allowed to."""
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, batch_id, outcome,"
        " actor, created_at, updated_at)"
        " VALUES (?, 0, 'human', 'ConfirmShelve', CAST(? AS TEXT),"
        " ?, 'success', 'human', ?, ?)",
        (P, goal_id, batch, _db.now(), _db.now()))
    conn.commit()
    return int(cur.lastrowid)


def test_human_park_is_not_a_promise_waiting_on_a_prerequisite(
        tmp_path: Path) -> None:
    """§3.2: a human ConfirmShelve has no paired Inject, so it can never
    be "waiting on its batch" — not even if the applier files it under a
    batch id alongside the machine's own in-flight work. Reading it as a
    live promise would hold the parent open forever on a wait that has
    no end."""
    conn = _conn(tmp_path)
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _human_confirm_shelve(conn, leaf, batch="promise-h")
    _mint_inject(conn, batch="promise-h", outcome=None)   # machine, live
    assert not _tr._awaiting_promised_batch(conn, leaf)
    conn.close()


def test_machine_park_after_a_human_one_keeps_machine_semantics(
        tmp_path: Path) -> None:
    """The other direction of the same rule: the machine's own park is
    untouched — a live promise batch still holds the parent."""
    conn = _conn(tmp_path)
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _human_confirm_shelve(conn, leaf)
    _confirm_shelve(conn, leaf, batch="promise-m")
    _mint_inject(conn, batch="promise-m", outcome=None)
    assert _tr._awaiting_promised_batch(conn, leaf)
    conn.close()


def test_human_park_survives_a_later_machine_inject(tmp_path: Path) -> None:
    """§3.2: the human park is TERMINAL. The machine un-parks its OWN
    ConfirmShelve by targeting the goal again (that is what makes the
    goal citable/revivable), and applying that rule to a person's stop
    would let a redispatch quietly overrule it."""
    conn = _conn(tmp_path)
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _human_confirm_shelve(conn, leaf)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, batch_id, outcome,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Inject', CAST(? AS TEXT), 'b9',"
        " NULL, ?, ?)", (P, leaf, _db.now(), _db.now()))
    conn.commit()
    assert _db.is_confirm_shelve_parked(conn, leaf)
    conn.close()


def test_machine_park_is_still_unparked_by_a_later_inject(
        tmp_path: Path) -> None:
    """Today's semantics, pinned so the human branch cannot swallow
    them: the machine's park ends when the Strategist targets the goal
    again, which is what lets citation revive it."""
    conn = _conn(tmp_path)
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _confirm_shelve(conn, leaf, batch="promise-m")
    assert _db.is_confirm_shelve_parked(conn, leaf)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, batch_id, outcome,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Inject', CAST(? AS TEXT), 'b9',"
        " NULL, ?, ?)", (P, leaf, _db.now(), _db.now()))
    conn.commit()
    assert not _db.is_confirm_shelve_parked(conn, leaf)
    conn.close()


def test_a_human_reopen_ends_the_human_park(tmp_path: Path) -> None:
    """Terminal does not mean irreversible — it means only the human
    reverses it. A human Inject on the same goal lifts the park; without
    this the person who stopped a line could never restart it."""
    conn = _conn(tmp_path)
    leaf = _goal(conn, "pleaf", status="shelved", origin="backward")
    _human_confirm_shelve(conn, leaf)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, batch_id, outcome,"
        " actor, created_at, updated_at)"
        " VALUES (?, 0, 'human', 'Inject', CAST(? AS TEXT), 'bh',"
        " NULL, 'human', ?, ?)", (P, leaf, _db.now(), _db.now()))
    conn.commit()
    assert not _db.is_confirm_shelve_parked(conn, leaf)
    conn.close()
