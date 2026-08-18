"""Phase 2 cascade rules — helper functions in dispatcher.py.

Covers:
  Rule 3 — `_has_terminal_disproved_ancestor` (Reopen safety walk)
           `_has_dead_strategy_in_chain` (auto-detach trigger detection)

Rule 1 (cascade_one decline-directive split) is covered in
`tests/test_infeasible_escape.py`.

Rule 2 was the original downward `_cascade_shelve_descendants` cascade;
removed once `shelved` became reopenable and Strategist's context view
gained an alive-set filter. BFS already excluded dead-chain descendants
via `db.open_goals`'s recursive alive seed, so flipping descendant
status added no behavior and broke Reopen flow on the parent (cascade-
shelved children stayed `shelved` even after a sibling/parent strategy
revived the chain, since `db.open_goals` filters `status='open'`).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.core.dispatcher import (
    _has_terminal_disproved_ancestor,
    _has_hard_terminal_ancestor,
    _has_dead_strategy_in_chain,
    _enqueue_strategist_review,
    _propagate_shelve,
    _propagate_disproved,
    _propagate_dead,
    _cascade_shelve_descendants,
    _inward_kill_strategies,
    cascade_one,
)
from Tooling.state import db

def _top(conn, problem):
    """The problem's top-group id as the queue stores it (v35: the
    Strategist seat is keyed by group, not by problem)."""
    from Tooling.state import groups as _g
    return str(_g.ensure_top_group(conn, problem))



@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done) "
        "VALUES ('p', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_goal(conn: sqlite3.Connection, *, slug: str,
                 origin: str = "backward", status: str = "open",
                 problem: str = "p") -> int:
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts,"
        " integrity_verified, detached, created_at, updated_at)"
        " VALUES (?, ?, ?, 'T', 'theorem', ?, ?, 0, 0, 0, 0, ?, ?)",
        (problem, slug, f"Problems/{problem}/proofs/L_{slug}.lean",
         origin, status, db.now(), db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _insert_strategy(conn: sqlite3.Connection, *, goal_id: int,
                     status: str = "proposed") -> int:
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', ?, '', 'test', ?)",
        (goal_id, status, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _link(conn: sqlite3.Connection, strategy_id: int,
          subgoal_ids: list[int]) -> None:
    for pos, sg in enumerate(subgoal_ids):
        conn.execute(
            "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
            " VALUES (?, ?, ?)",
            (strategy_id, sg, pos),
        )
    conn.commit()


# ---------------------------------------------------------------------
# DAG-aware shelve cascade: a shared (multi-parent) goal is only shelved
# when it loses its LAST live parent, not when one branch dies.
# ---------------------------------------------------------------------

def _status(conn: sqlite3.Connection, gid: int) -> str:
    return str(conn.execute(
        "SELECT status FROM goals WHERE id = ?", (gid,)).fetchone()["status"])


def test_cascade_spares_cross_branch_shared_goal(
    conn: sqlite3.Connection,
) -> None:
    """R → S_R → {A, B}; A → S_A → X and B → S_B → X (X shared, e.g. a
    cross-branch cited / auto-linked sibling). Shelving branch A must NOT
    shelve X — B's live path still needs it. Only when B also dies does X
    lose its last live path and get shelved."""
    r = _insert_goal(conn, slug="r", origin="root", status="open")
    s_r = _insert_strategy(conn, goal_id=r)
    a = _insert_goal(conn, slug="a", status="open")
    b = _insert_goal(conn, slug="b", status="open")
    _link(conn, s_r, [a, b])
    s_a = _insert_strategy(conn, goal_id=a)
    s_b = _insert_strategy(conn, goal_id=b)
    x = _insert_goal(conn, slug="x", status="open")
    _link(conn, s_a, [x])
    _link(conn, s_b, [x])

    # Shelve branch A (the real flow inward-kills the shelved goal's own
    # strategies; replicate so the alive CTE cuts the A-path).
    db.update_goal_status(conn, a, "shelved")
    _inward_kill_strategies(conn, a)
    _cascade_shelve_descendants(conn, a)
    assert _status(conn, a) == "shelved"
    assert _status(conn, x) == "open"   # spared — B's path still needs it

    # Now branch B dies too → X loses its last live path → shelved.
    db.update_goal_status(conn, b, "shelved")
    _inward_kill_strategies(conn, b)
    _cascade_shelve_descendants(conn, b)
    assert _status(conn, x) == "shelved"


def test_cascade_shelves_single_parent_descendant(
    conn: sqlite3.Connection,
) -> None:
    """Common (tree) case unaffected: a descendant whose only path runs
    through the dying goal is still cascade-shelved."""
    r = _insert_goal(conn, slug="r", origin="root", status="open")
    s_r = _insert_strategy(conn, goal_id=r)
    a = _insert_goal(conn, slug="a", status="open")
    _link(conn, s_r, [a])
    s_a = _insert_strategy(conn, goal_id=a)
    leaf = _insert_goal(conn, slug="leaf", status="open")
    _link(conn, s_a, [leaf])

    db.update_goal_status(conn, a, "shelved")
    _inward_kill_strategies(conn, a)
    _cascade_shelve_descendants(conn, a)
    assert _status(conn, leaf) == "shelved"


# ---------------------------------------------------------------------
# #4: outcome_detail — Forward decline `## Why` stashed pre-cascade is
# preserved when cascade fills the coarse outcome (COALESCE).
# ---------------------------------------------------------------------

def _insert_decision(conn: sqlite3.Connection) -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, created_at, updated_at)"
        " VALUES ('p', 1, 'routine', 'Inject', '{}', ?, ?)",
        (ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_record_outcome_preserves_prewritten_detail(
    conn: sqlite3.Connection,
) -> None:
    from Tooling.core.dispatcher import _record_inject_decision_outcome
    did = _insert_decision(conn)
    # Forward stashed the decline `## Why` pre-cascade (outcome NULL).
    db.set_inject_decision_outcome_detail(
        conn, did, "brief under-specified: name the lemma")
    # cascade later fills the coarse outcome, carrying no detail of its own.
    _record_inject_decision_outcome(conn, did, "failed", "agent_declined")
    row = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions WHERE id=?",
        (did,)).fetchone()
    assert row["outcome"] == "failed:agent_declined"
    assert row["outcome_detail"] == "brief under-specified: name the lemma"


def test_set_outcome_detail_skips_when_outcome_already_settled(
    conn: sqlite3.Connection,
) -> None:
    """Don't disturb a row whose outcome already landed."""
    did = _insert_decision(conn)
    conn.execute(
        "UPDATE strategist_decisions SET outcome = 'proved' WHERE id = ?",
        (did,))
    conn.commit()
    db.set_inject_decision_outcome_detail(conn, did, "late detail")
    od = conn.execute(
        "SELECT outcome_detail FROM strategist_decisions WHERE id=?",
        (did,)).fetchone()["outcome_detail"]
    assert od is None


# ---------------------------------------------------------------------
# Rule 3: _has_terminal_disproved_ancestor
# ---------------------------------------------------------------------

def test_disproved_ancestor_detected(conn: sqlite3.Connection) -> None:
    """G → S → sub. Set G.status='disproved'. sub has a disproved
    ancestor."""
    g = _insert_goal(conn, slug="g", origin="root", status="disproved")
    s = _insert_strategy(conn, goal_id=g)
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s, [sub])

    assert _has_terminal_disproved_ancestor(conn, sub) is True


def test_shelved_ancestor_not_a_terminal_block(
    conn: sqlite3.Connection,
) -> None:
    """`shelved` is soft terminal (reopenable). It does NOT block Reopen
    on a descendant — that's the point of the Phase 2 detach mechanism."""
    g = _insert_goal(conn, slug="g", origin="root", status="shelved")
    s = _insert_strategy(conn, goal_id=g)
    sub = _insert_goal(conn, slug="sub", status="shelved")
    _link(conn, s, [sub])

    assert _has_terminal_disproved_ancestor(conn, sub) is False


def test_no_ancestor_means_no_block(conn: sqlite3.Connection) -> None:
    """Root goal has no ancestor → no block."""
    g = _insert_goal(conn, slug="g", origin="root")
    assert _has_terminal_disproved_ancestor(conn, g) is False


def test_disproved_at_depth_2(conn: sqlite3.Connection) -> None:
    """G (open) → S1 → mid (disproved) → S2 → sub. Walk should find
    mid's status, return True."""
    g = _insert_goal(conn, slug="g", origin="root")
    s1 = _insert_strategy(conn, goal_id=g)
    mid = _insert_goal(conn, slug="mid", status="disproved")
    _link(conn, s1, [mid])
    s2 = _insert_strategy(conn, goal_id=mid)
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s2, [sub])

    assert _has_terminal_disproved_ancestor(conn, sub) is True


def test_dead_ancestor_blocks_reopen(conn: sqlite3.Connection) -> None:
    """Phase 6: `dead` ancestor (parent_needs_fix verdict) also blocks
    Reopen on descendants. The descendant exists only in the wrong
    context that produced the dead ancestor; reopening it would attempt
    proof in an abandoned strategy direction. Salvage useful descendants
    via Inject(Backward, target=<other-goal>) instead."""
    g = _insert_goal(conn, slug="g_dead", origin="root", status="dead")
    s = _insert_strategy(conn, goal_id=g)
    sub = _insert_goal(conn, slug="sub_under_dead", status="shelved")
    _link(conn, s, [sub])

    found, kind = _has_hard_terminal_ancestor(conn, sub)
    assert found is True
    assert kind == "dead"
    # Legacy alias keeps returning True for either disproved/dead.
    assert _has_terminal_disproved_ancestor(conn, sub) is True


def test_dead_at_depth_2_blocks_reopen(conn: sqlite3.Connection) -> None:
    """G (open) → S1 → mid (dead) → S2 → sub. Walk finds mid='dead',
    returns True with kind='dead'."""
    g = _insert_goal(conn, slug="g_d2", origin="root")
    s1 = _insert_strategy(conn, goal_id=g)
    mid = _insert_goal(conn, slug="mid_d2", status="dead")
    _link(conn, s1, [mid])
    s2 = _insert_strategy(conn, goal_id=mid)
    sub = _insert_goal(conn, slug="sub_d2", status="shelved")
    _link(conn, s2, [sub])

    found, kind = _has_hard_terminal_ancestor(conn, sub)
    assert found is True
    assert kind == "dead"


def test_shelved_ancestor_not_a_hard_terminal(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6 helper returns (False, None) on shelved ancestors —
    they don't block Reopen; auto-detach handles them."""
    g = _insert_goal(conn, slug="g_shelved", origin="root",
                    status="shelved")
    s = _insert_strategy(conn, goal_id=g)
    sub = _insert_goal(conn, slug="sub_under_shelved", status="shelved")
    _link(conn, s, [sub])

    found, kind = _has_hard_terminal_ancestor(conn, sub)
    assert found is False
    assert kind is None


# ---------------------------------------------------------------------
# Rule 3: _has_dead_strategy_in_chain (auto-detach trigger)
# ---------------------------------------------------------------------

def test_dead_strategy_in_chain_detected(conn: sqlite3.Connection) -> None:
    """G → S(dead) → sub. The dead strategy means sub is orphaned;
    a Reopen on sub should auto-detach it."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g, status="dead")
    sub = _insert_goal(conn, slug="sub", status="shelved")
    _link(conn, s, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is True


def test_superseded_strategy_in_chain_detected(
    conn: sqlite3.Connection,
) -> None:
    """Same as dead — a superseded strategy means downstream goals are
    orphaned from this branch."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g, status="superseded")
    sub = _insert_goal(conn, slug="sub", status="shelved")
    _link(conn, s, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is True


def test_alive_chain_no_detach(conn: sqlite3.Connection) -> None:
    """All strategies in the chain are proposed/succeeded → no detach
    needed. Reopen restores attempting without setting detached."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g, status="proposed")
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is False


def test_dead_at_depth_2(conn: sqlite3.Connection) -> None:
    """G → S1(dead) → mid → S2(proposed) → sub. The dead S1 means the
    whole chain is broken even if S2 is alive."""
    g = _insert_goal(conn, slug="g", origin="root")
    s1 = _insert_strategy(conn, goal_id=g, status="dead")
    mid = _insert_goal(conn, slug="mid", status="shelved")
    _link(conn, s1, [mid])
    s2 = _insert_strategy(conn, goal_id=mid, status="proposed")
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s2, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is True


# ---------------------------------------------------------------------
# Rule 1 / dispatcher.cascade_one helper: _enqueue_strategist_review
# ---------------------------------------------------------------------

def test_enqueue_strategist_review_sets_status_and_queues(
    conn: sqlite3.Connection,
) -> None:
    """_enqueue_strategist_review marks goal pending and enqueues a
    problem-keyed Strategist row (Phase 6: target_id=<problem name>,
    target_kind='Problem')."""
    _insert_goal(conn, slug="main", origin="root")
    sub = _insert_goal(conn, slug="sub", status="attempting")

    _enqueue_strategist_review(conn, sub)

    assert db.get_goal(conn, sub)["status"] == "pending_strategist_review"
    q = conn.execute(
        "SELECT kind, target_id, target_kind, priority FROM queue"
        " WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == _top(conn, "p")
    assert q[0]["target_kind"] == "Group"
    # Priority 20 per pipelines.md §2.1 (T2 > T1/T4=10); regression guard
    # against db.enqueue default=0 putting T2 below Backward / Builder.
    assert q[0]["priority"] == 20


def test_enqueue_strategist_review_skips_orphan_chain(
    conn: sqlite3.Connection,
) -> None:
    """When a worker returns agent_shelved on a goal whose ancestor
    strategy has already died (orphaned subtree), the cleanup path
    must skip the Strategist enqueue and shelve the goal directly.
    Strategist on a dead-chain goal is a wasted spawn: Reopen would
    auto-detach a goal about to be shelve-cascaded, Inject(Forward)
    would build a lemma nothing cites.

    Residue_thm 2026-05-19 regression: Backward on g2107 returned
    agent_shelved after its grandparent strategy s10285 died; the
    framework still enqueued Strategist + ran one full cycle +
    committed ConfirmShelve. Pure overhead the cascade walk would
    catch later anyway.
    """
    root = _insert_goal(conn, slug="main", origin="root")
    parent = _insert_goal(conn, slug="parent_goal", status="open")
    dead_strat = _insert_strategy(conn, goal_id=parent, status="dead")
    sub = _insert_goal(conn, slug="orphan_sub", status="attempting")
    _link(conn, dead_strat, [sub])

    _enqueue_strategist_review(conn, sub)

    # Should NOT enqueue Strategist
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0
    # Should shelve sub directly
    assert db.get_goal(conn, sub)["status"] == "shelved"
    # parent_goal stays open (its status flip is _propagate_shelve's job
    # via increment_attempts threshold; out of scope for this unit test)
    assert root  # silence unused warning


def test_cascade_missing_parent_stub_shelves_no_spin(
    conn: sqlite3.Connection,
) -> None:
    """Backward `missing_parent_stub` (the goal's own L_<slug>.lean vanished
    from disk while the row stays dispatchable — a DB↔file drift) must
    TERMINALLY shelve the goal on the FIRST occurrence, NOT fall into the
    generic attempts++/SHELVE_THRESHOLD path. `run_backward` reads the stub
    BEFORE spawning, so this fails instantly (no agent, no cooldown); without
    the terminal the dispatcher tight-loops re-dispatch ~20/s until threshold
    (P13 g4437 2026-06-16: 4 dead_attempts in 167ms). One occurrence →
    shelved, attempts incremented exactly once (1:1 with its dead_attempt),
    no spin."""
    _insert_goal(conn, slug="main", origin="root")
    g = _insert_goal(conn, slug="orphan_stub", status="attempting")
    cascade_one(
        conn, pipeline_id="pid-mps", kind="Backward",
        target_id=str(g), target_kind="Goal",
        outcome="failed", failure_reason="missing_parent_stub",
    )
    gg = db.get_goal(conn, g)
    assert gg["status"] == "shelved"   # terminal park, not left dispatchable
    assert gg["attempts"] == 1         # one increment, NOT spun to threshold


def test_enqueue_strategist_review_dedups_in_flight(
    conn: sqlite3.Connection,
) -> None:
    """Two sub-goals shelving on the same problem produce only ONE
    Strategist queue entry. Per-problem in-flight dedup."""
    root = _insert_goal(conn, slug="main", origin="root")
    sub_a = _insert_goal(conn, slug="sub_a", status="attempting")
    sub_b = _insert_goal(conn, slug="sub_b", status="attempting")

    _enqueue_strategist_review(conn, sub_a)
    _enqueue_strategist_review(conn, sub_b)

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1
    # Both sub-goals are pending
    assert db.get_goal(conn, sub_a)["status"] == "pending_strategist_review"
    assert db.get_goal(conn, sub_b)["status"] == "pending_strategist_review"


def test_enqueue_strategist_review_skips_orphan_guard_when_detached(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: if the goal was explicitly detached (Strategist
    Reopen+auto-detach or Inject(Backward)+auto-detach), the orphan-
    chain guard does NOT fire — the detach flag signals that
    Strategist owns this dispatch even though upward strategies are
    dead. pending_review is the right next stop, not auto-shelve.
    """
    root = _insert_goal(conn, slug="main", origin="root")
    parent = _insert_goal(conn, slug="parent_goal", status="open")
    dead_strat = _insert_strategy(conn, goal_id=parent, status="dead")
    sub = _insert_goal(conn, slug="detached_orphan_sub", status="attempting")
    _link(conn, dead_strat, [sub])
    # Strategist auto-detach simulation
    db.set_goal_detached(conn, sub, True)

    _enqueue_strategist_review(conn, sub)

    # Strategist DOES enqueue (no orphan auto-shelve)
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1
    # Goal moves to pending_strategist_review (not shelved)
    assert db.get_goal(conn, sub)["status"] == "pending_strategist_review"
    assert root  # silence unused warning


def test_propagate_shelve_does_not_kill_upward(
    conn: sqlite3.Connection,
) -> None:
    """`_propagate_shelve` does inward kill only — it never HARD-kills the
    upward chain ('dead'), so the chain stays reopenable.

    Phase 11 refinement: when the soft-shelve leaves the parent strategy
    with zero alive sub-goals, it is PARKED 'stalled' (reopenable, and it
    resolves the producing inject's outcome) rather than left 'proposed'.
    'stalled' is still not 'dead': a sub-goal Reopen flips it back to
    'proposed'. (A parent that retains an alive sibling stays 'proposed' —
    see test_shelve_with_alive_sibling_keeps_parent_proposed.)

    2026-07-09 (putnam_2025_b6 mutual-deadlock fix B): parking the parent
    goal's LAST live route now escalates that goal to
    pending_strategist_review (T2) instead of leaving it a silent
    `attempting` nobody would ever touch again."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    parent_s = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    target = _insert_goal(conn, slug="target", status="shelved")
    _link(conn, parent_s, [target])

    own_s = _insert_strategy(conn, goal_id=target, status="proposed")

    _propagate_shelve(conn, target)

    # Inward: own strategy killed
    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (own_s,)
    ).fetchone()["status"] == "dead"
    # Upward: parent PARKED 'stalled' (reopenable), not hard-killed 'dead'
    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (parent_s,)
    ).fetchone()["status"] == "stalled"
    # Parent goal's last live route just parked → escalated to the T2
    # review path (fix B); still fully reopenable via Reopen/Inject.
    assert db.get_goal(conn, parent_g)["status"] == "pending_strategist_review"


def test_propagate_disproved_kills_upward(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: `_propagate_disproved` (counterexample) kills upward
    strategies AND inward strategies. Parent goal reopens for retry
    via different decomposition."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    parent_s = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    target = _insert_goal(conn, slug="target", status="disproved")
    _link(conn, parent_s, [target])

    _propagate_disproved(conn, target)

    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (parent_s,)
    ).fetchone()["status"] == "dead"
    assert db.get_goal(conn, parent_g)["status"] == "open"


def test_propagate_dead_kills_upward(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: `_propagate_dead` (parent_needs_fix) kills upward and
    inward. Parent reopens to try a different decomposition."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    parent_s = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    target = _insert_goal(conn, slug="target", status="dead")
    _link(conn, parent_s, [target])

    _propagate_dead(conn, target)

    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (parent_s,)
    ).fetchone()["status"] == "dead"
    assert db.get_goal(conn, parent_g)["status"] == "open"


# ---------------------------------------------------------------------
# Sibling-orphan sweep — when _kill_upward_chain kills a strategy, its
# other subgoals become orphans of the alive-strategy DAG. Without the
# sweep, their status disagrees with dispatchability — TREE.md /
# Strategist context misrepresent active work that BFS cannot reach.
# ---------------------------------------------------------------------

def test_kill_upward_cascades_open_sibling_to_shelved(
    conn: sqlite3.Connection,
) -> None:
    """strategy s1 has subgoals g_terminating + g_sibling (open).
    When g_terminating goes dead, s1 dies; g_sibling has no other
    parent strategy → status should flip 'shelved' so status reflects
    'not dispatchable' (matches BFS's alive-set CTE)."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    s1 = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    terminating = _insert_goal(conn, slug="terminating", status="dead")
    sibling = _insert_goal(conn, slug="sibling", status="open")
    _link(conn, s1, [terminating, sibling])

    _propagate_dead(conn, terminating)

    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (s1,)
    ).fetchone()["status"] == "dead"
    assert db.get_goal(conn, sibling)["status"] == "shelved"


def test_kill_upward_cascades_attempting_sibling(
    conn: sqlite3.Connection,
) -> None:
    """Attempting sibling — a worker may have been dispatched on it,
    or its sub-strategy may already exist. Sibling sweep shelves it
    so subsequent late worker results are race-guarded out (cascade_one's
    terminal-status early-return)."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    s1 = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    terminating = _insert_goal(conn, slug="t", status="disproved")
    sibling = _insert_goal(conn, slug="sib_att", status="attempting")
    _link(conn, s1, [terminating, sibling])

    _propagate_disproved(conn, terminating)

    assert db.get_goal(conn, sibling)["status"] == "shelved"


def test_kill_upward_cascades_sibling_subtree(
    conn: sqlite3.Connection,
) -> None:
    """The sibling can carry its own live sub-strategy + subgoals.
    The sweep should propagate downward (via
    `_set_goal_terminal_and_propagate` cascade-descendants), and inward-
    kill the sibling's own strategy (via `_propagate_shelve`)."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    s1 = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    terminating = _insert_goal(conn, slug="t", status="dead")
    sibling = _insert_goal(conn, slug="sib", status="attempting")
    _link(conn, s1, [terminating, sibling])
    # Sibling's own sub-strategy
    s_sib = _insert_strategy(conn, goal_id=sibling, status="proposed")
    grand_a = _insert_goal(conn, slug="grand_a", status="attempting")
    grand_b = _insert_goal(conn, slug="grand_b", status="open")
    _link(conn, s_sib, [grand_a, grand_b])

    _propagate_dead(conn, terminating)

    assert db.get_goal(conn, sibling)["status"] == "shelved"
    # Sibling's own strategy: inward-killed by _propagate_shelve(sibling)
    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (s_sib,)
    ).fetchone()["status"] == "dead"
    # Grandchildren: cascade-shelved via _cascade_shelve_descendants(sibling)
    assert db.get_goal(conn, grand_a)["status"] == "shelved"
    assert db.get_goal(conn, grand_b)["status"] == "shelved"


def test_kill_upward_skips_proved_sibling(
    conn: sqlite3.Connection,
) -> None:
    """Proved siblings are valid library artifacts (Backward dedupe pool
    cites them); the sweep must walk past without flipping status."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    s1 = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    terminating = _insert_goal(conn, slug="t", status="dead")
    sibling = _insert_goal(conn, slug="proved_sib", status="proved")
    _link(conn, s1, [terminating, sibling])

    _propagate_dead(conn, terminating)

    # Proved is preserved.
    assert db.get_goal(conn, sibling)["status"] == "proved"


def test_kill_upward_skips_already_terminal_sibling(
    conn: sqlite3.Connection,
) -> None:
    """Already-shelved / disproved / dead siblings are skipped — no
    redundant re-flip, idempotent on re-cascade."""
    parent_g = _insert_goal(conn, slug="parent_g", status="attempting")
    s1 = _insert_strategy(conn, goal_id=parent_g, status="proposed")
    terminating = _insert_goal(conn, slug="t", status="dead")
    already_shelved = _insert_goal(conn, slug="sh", status="shelved")
    _link(conn, s1, [terminating, already_shelved])

    _propagate_dead(conn, terminating)

    # No re-flip; still 'shelved'.
    assert db.get_goal(conn, already_shelved)["status"] == "shelved"


def test_cascade_one_terminal_goal_guard_blocks_late_worker(
    conn: sqlite3.Connection,
) -> None:
    """Race guard: a worker dispatched on g before g cascaded-shelved
    (via sibling sweep) commits success after the cascade. The early-
    return in cascade_one for goals already in terminal status
    (shelved / disproved / dead / proved) must prevent the late commit
    from flipping g back to attempting/proved."""
    g = _insert_goal(conn, slug="g", status="shelved")
    cascade_one(
        conn, pipeline_id="late-pid", kind="Backward",
        target_id=str(g), target_kind="Goal",
        outcome="success", failure_reason="",
    )
    # Worker's commit did NOT mutate the shelved status.
    assert db.get_goal(conn, g)["status"] == "shelved"

    # Same for dead status
    g2 = _insert_goal(conn, slug="g2", status="dead")
    cascade_one(
        conn, pipeline_id="late-pid2", kind="Builder",
        target_id=str(g2), target_kind="Goal",
        outcome="proved", failure_reason="",
    )
    assert db.get_goal(conn, g2)["status"] == "dead"


def test_forward_cascade_without_decision_id_is_noop(
    conn: sqlite3.Connection,
) -> None:
    """Phase 2.5 unified — every Forward dispatches from an Inject batch
    so `decision_id` is always set in practice. When the parameter is
    absent (defensive / test edge), cascade does nothing: no audit-row
    update, no Strategist enqueue. The legacy 'failed Forward + existing
    pending_review → re-enqueue Strategist' shortcut was removed; the
    batch-done hook is the single trigger path."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    _insert_goal(conn, slug="kelly_contrapositive",
                 status="pending_strategist_review")
    cascade_one(
        conn, pipeline_id="pid-fwd", kind="Forward",
        target_id="p", target_kind="Problem",
        outcome="failed", failure_reason="forward_no_new_goal",
    )
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_forward_cascade_with_batch_decision_fires_strategist(
    conn: sqlite3.Connection,
) -> None:
    """Forward terminal outcome (success or failure) on a batch
    decision_id advances the batch and, when the last sibling finishes,
    enqueues Strategist (problem-keyed). Mirrors the new single trigger
    path."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    [rid] = _seed_inject_batch_rows(conn, batch_id="batch-A", count=1)
    cascade_one(
        conn, pipeline_id="pid-fwd", kind="Forward",
        target_id="p", target_kind="Problem",
        outcome="failed", failure_reason="forward_no_new_goal",
        decision_id=rid,
    )
    q = conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == _top(conn, "p")
    assert q[0]["target_kind"] == "Group"


def test_t2_pops_before_bfs(
    conn: sqlite3.Connection,
) -> None:
    """A T2 (pending_review) Strategist enqueue must pop before any
    Backward / Builder BFS enqueue already in the queue. Regression
    guard: pre-fix, `_enqueue_strategist_review` omitted the priority
    kwarg and inherited db.enqueue default=0, putting T2 below
    Backward (=2) and Builder (=5) — inverting pipelines.md §2.1
    'T2 > T0 > T1' (and the §4.3 implied 'Strategist > Backward /
    Builder for pending review'). T2-vs-T1/T4 ordering is moot at
    runtime because per-problem Strategist dedup in
    `_enqueue_strategist_review` prevents simultaneous T1/T4+T2 rows
    for the same problem."""
    _insert_goal(conn, slug="main", origin="root")
    sub = _insert_goal(conn, slug="sub", status="attempting")

    db.enqueue(conn, kind="Backward", target_id="999", priority=2,
               problem="p")
    db.enqueue(conn, kind="Builder",  target_id="998", priority=5,
               problem="p")
    _enqueue_strategist_review(conn, sub)

    first = db.pop_queue(conn)
    assert first is not None
    assert first["kind"] == "Strategist"
    assert first["priority"] == 20
    assert first["target_id"] == _top(conn, "p")


# ---------------------------------------------------------------------
# Cascade-shelve descendants — `_set_goal_terminal_and_propagate`
# applies a downward `shelved` cascade whenever any goal flips to
# `shelved` or `disproved`. Single uniform terminology: status
# `shelved` regardless of the path (own shelve, ConfirmShelve,
# parent_needs_fix, descendant cascade).
# ---------------------------------------------------------------------

def test_shelve_cascades_to_open_descendant(conn: sqlite3.Connection) -> None:
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    parent = _insert_goal(conn, slug="parent", origin="root")
    sid = _insert_strategy(conn, goal_id=parent)
    child = _insert_goal(conn, slug="child", status="open")
    _link(conn, sid, [child])

    _set_goal_terminal_and_propagate(conn, parent, "shelved")
    assert db.get_goal(conn, parent)["status"] == "shelved"
    assert db.get_goal(conn, child)["status"] == "shelved"


def test_shelve_cascades_to_attempting_descendant(
    conn: sqlite3.Connection,
) -> None:
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    parent = _insert_goal(conn, slug="parent", origin="root")
    sid = _insert_strategy(conn, goal_id=parent)
    child = _insert_goal(conn, slug="child", status="attempting")
    _link(conn, sid, [child])

    _set_goal_terminal_and_propagate(conn, parent, "shelved")
    assert db.get_goal(conn, child)["status"] == "shelved"


def test_shelve_preserves_proved_descendant_but_walks_past(
    conn: sqlite3.Connection,
) -> None:
    """Cascade walks past `proved` descendants without overwriting
    them, so deeper active descendants under the proved subtree still
    get cascade-shelved."""
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    parent = _insert_goal(conn, slug="parent", origin="root")
    sid = _insert_strategy(conn, goal_id=parent)
    mid = _insert_goal(conn, slug="mid", status="proved")
    _link(conn, sid, [mid])
    sid2 = _insert_strategy(conn, goal_id=mid)
    grand = _insert_goal(conn, slug="grand", status="open")
    _link(conn, sid2, [grand])

    _set_goal_terminal_and_propagate(conn, parent, "shelved")
    assert db.get_goal(conn, mid)["status"] == "proved"  # untouched
    assert db.get_goal(conn, grand)["status"] == "shelved"


def test_shelve_skips_pending_review_descendant(
    conn: sqlite3.Connection,
) -> None:
    """`pending_strategist_review` is transitional; Strategist will
    decide. Cascading would race with that decision."""
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    parent = _insert_goal(conn, slug="parent", origin="root")
    sid = _insert_strategy(conn, goal_id=parent)
    pending = _insert_goal(conn, slug="pending",
                           status="pending_strategist_review")
    _link(conn, sid, [pending])

    _set_goal_terminal_and_propagate(conn, parent, "shelved")
    assert db.get_goal(conn, pending)["status"] == "pending_strategist_review"


def test_disproved_cascades_descendants_as_shelved_not_disproved(
    conn: sqlite3.Connection,
) -> None:
    """A disproved goal taints its descendants but they were not
    independently disproved — they get `shelved` (soft terminal,
    Reopenable), not `disproved`. Preserves `disproved`'s dedupe
    semantics: only counterexample-shown statements block future
    same-shape proposals."""
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    parent = _insert_goal(conn, slug="parent", origin="root")
    sid = _insert_strategy(conn, goal_id=parent)
    child = _insert_goal(conn, slug="child", status="open")
    _link(conn, sid, [child])

    _set_goal_terminal_and_propagate(conn, parent, "disproved")
    assert db.get_goal(conn, parent)["status"] == "disproved"
    assert db.get_goal(conn, child)["status"] == "shelved"


def test_cascade_shelve_inward_kills_descendant_strategies(
    conn: sqlite3.Connection,
) -> None:
    """When `_cascade_shelve_descendants` flips a descendant from
    attempting → shelved, the descendant's OWN proposed strategies must
    also be inward-killed (same as a direct `_propagate_shelve` would
    do). Without that symmetry the descendant ends up shelved in the
    goal table but its proposed strategy still maps to it, the alive-
    DAG CTE keeps walking that edge as live, and the subtree keeps
    leaking 'active' status to TREE.md / Strategist context. Mirrors
    the residue_thm 2026-05-21 cleanup where s10309/s10330 remained
    'proposed' under cascade-shelved goals until manually re-shelved."""
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    parent = _insert_goal(conn, slug="parent", origin="root")
    p_strat = _insert_strategy(conn, goal_id=parent)
    mid = _insert_goal(conn, slug="mid", status="attempting")
    _link(conn, p_strat, [mid])
    # `mid` has its own proposed strategy that the cascade should
    # inward-kill once `mid` itself flips to shelved.
    mid_strat = _insert_strategy(conn, goal_id=mid, status="proposed")
    leaf = _insert_goal(conn, slug="leaf", status="open")
    _link(conn, mid_strat, [leaf])

    _set_goal_terminal_and_propagate(conn, parent, "shelved")

    assert db.get_goal(conn, mid)["status"] == "shelved"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (mid_strat,),
    ).fetchone()["status"] == "dead"
    # Deeper descendants still get the cascade.
    assert db.get_goal(conn, leaf)["status"] == "shelved"


def test_proved_does_not_cascade(conn: sqlite3.Connection) -> None:
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    from Tooling.state import transitions
    parent = _insert_goal(conn, slug="parent", origin="root")
    sid = _insert_strategy(conn, goal_id=parent)
    child = _insert_goal(conn, slug="child", status="open")
    _link(conn, sid, [child])

    _set_goal_terminal_and_propagate(
        conn, parent, "proved",
        receipt=transitions.ProvedReceipt("verify_collapse", "test"))
    # No shelve cascade on the proved path.
    assert db.get_goal(conn, child)["status"] == "open"


def test_shelve_idempotent(conn: sqlite3.Connection) -> None:
    """Re-running on an already-shelved parent / child does nothing."""
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    parent = _insert_goal(conn, slug="parent", origin="root")
    sid = _insert_strategy(conn, goal_id=parent)
    child = _insert_goal(conn, slug="child", status="open")
    _link(conn, sid, [child])

    _set_goal_terminal_and_propagate(conn, parent, "shelved")
    _set_goal_terminal_and_propagate(conn, parent, "shelved")  # 2nd run
    assert db.get_goal(conn, child)["status"] == "shelved"


# ---------------------------------------------------------------------
# Phase 2.5 — Inject batch completion hook
# ---------------------------------------------------------------------

def _seed_inject_batch_rows(conn: sqlite3.Connection, *,
                            problem: str = "p",
                            batch_id: str,
                            count: int) -> list[int]:
    ts = db.now()
    ids: list[int] = []
    for i in range(count):
        cur = conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, target_id, brief, reason,"
            " payload, batch_id, outcome, created_at, updated_at)"
            " VALUES (?, 0, 'pending_review', 'Inject', NULL, ?, NULL,"
            "         ?, ?, NULL, ?, ?)",
            (problem, f"brief {i}",
             '{"pipeline":"Forward","step_index":' + str(i)
                + ',"batch_size":' + str(count) + '}',
             batch_id, ts, ts),
        )
        ids.append(int(cur.lastrowid))
    conn.commit()
    return ids


def test_batch_partial_completion_does_not_enqueue_strategist(
    conn: sqlite3.Connection,
) -> None:
    """2/3 Forwards done → no Strategist trigger yet. The hook only
    fires when EVERY decision row in the batch has outcome filled."""
    root = _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="batch-x", count=3)

    cascade_one(conn, pipeline_id="pid1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[0])
    cascade_one(conn, pipeline_id="pid2", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="lake_build_error",
                decision_id=ids[1])
    # 1 row still pending → no Strategist enqueue
    q_strat = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q_strat["n"] == 0
    # Outcomes recorded on the two done rows
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE batch_id='batch-x' ORDER BY id"
    ))
    assert rows[0]["outcome"] is not None
    assert rows[1]["outcome"] is not None
    assert rows[2]["outcome"] is None


def test_batch_full_completion_enqueues_one_strategist(
    conn: sqlite3.Connection,
) -> None:
    """All 3 Forwards done → exactly one problem-keyed Strategist
    enqueue with priority=20. Idempotent: a second cascade for the same
    batch must not double-enqueue (dedup via is_in_queue)."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="batch-z", count=3)

    for pid, rid in zip(["p1", "p2", "p3"], ids):
        cascade_one(conn, pipeline_id=pid, kind="Forward",
                    target_id="p", target_kind="Problem",
                    outcome="success", decision_id=rid)

    q = list(conn.execute(
        "SELECT kind, target_id, target_kind, priority FROM queue"
        " WHERE kind='Strategist'"
    ))
    assert len(q) == 1
    assert q[0]["target_id"] == _top(conn, "p")
    assert q[0]["target_kind"] == "Group"
    assert q[0]["priority"] == 20

    # Re-fire cascade on the same last row (idempotent path); no second
    # enqueue. (`is_in_queue` blocks the duplicate.)
    cascade_one(conn, pipeline_id="p3-replay", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[-1])
    q2 = list(conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ))
    assert q2[0]["n"] == 1


def test_batch_done_fires_for_pure_nl_problem_without_root(
    conn: sqlite3.Connection,
) -> None:
    """Pure-NL mode (no root goal at all): batch completion still wakes
    the Strategist — Phase 6 made the wake problem-keyed, so it no
    longer depends on an origin='root' goal existing."""
    ids = _seed_inject_batch_rows(conn, batch_id="batch-nl", count=1)
    cascade_one(conn, pipeline_id="pnl", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[0])
    q = list(conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind='Strategist'"
    ))
    assert [(r["target_id"], r["target_kind"]) for r in q] == [
        (_top(conn, "p"), "Group")]


def test_batch_done_defers_until_produced_lemma_proved(
    conn: sqlite3.Connection,
) -> None:
    """residue_thm 2026-05-19 regression: Inject decision outcome must
    be filled when produced lemma reaches terminal, not when Forward
    agent finishes writing. With produced_goal_id linked, cascade_one
    leaves outcome=NULL and inject_batch_done does not fire."""
    root = _insert_goal(conn, slug="main", origin="root",
                        status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="defer-batch", count=2)
    # Two Forward-produced sorry-bearing goals
    fwd_a = _insert_goal(conn, slug="fwd_a", origin="forward",
                         status="open")
    fwd_b = _insert_goal(conn, slug="fwd_b", origin="forward",
                         status="open")
    db.set_inject_decision_produced_goal(conn, ids[0], fwd_a)
    db.set_inject_decision_produced_goal(conn, ids[1], fwd_b)

    # Both Forward pipelines "finish writing" → cascade_one fires.
    cascade_one(conn, pipeline_id="p1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[0])
    cascade_one(conn, pipeline_id="p2", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[1])

    # Outcomes STILL NULL — deferred
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE batch_id='defer-batch'"
    ))
    assert all(r["outcome"] is None for r in rows)
    # No Strategist enqueued yet
    q = list(conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ))
    assert q[0]["n"] == 0

    # First lemma proved → propagate → still one pending → no enqueue
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    from Tooling.state import transitions
    _receipt = transitions.ProvedReceipt("axiom_gate", "test")
    _set_goal_terminal_and_propagate(conn, fwd_a, "proved",
                                     receipt=_receipt)
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE batch_id='defer-batch' ORDER BY id"
    ))
    assert rows[0]["outcome"] == "success"
    assert rows[1]["outcome"] is None
    q = list(conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ))
    assert q[0]["n"] == 0

    # Second lemma proved → batch complete → Strategist enqueued exactly once
    _set_goal_terminal_and_propagate(conn, fwd_b, "proved",
                                     receipt=_receipt)
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE batch_id='defer-batch' ORDER BY id"
    ))
    assert all(r["outcome"] == "success" for r in rows)
    q = list(conn.execute(
        "SELECT kind, target_id, target_kind FROM queue"
        " WHERE kind='Strategist'"
    ))
    assert len(q) == 1
    assert q[0]["target_id"] == _top(conn, "p")
    assert q[0]["target_kind"] == "Group"
    assert root  # root exists but the wake is problem-keyed


def test_batch_done_does_not_fire_when_produced_lemma_shelved(
    conn: sqlite3.Connection,
) -> None:
    """If the produced lemma SHELVES (parked, reopenable), the inject's
    outcome stays NULL and the batch does NOT complete — a shelved brick is
    not a settled inject (see propagate_inject_outcome_from_goal). Settling it
    re-fired the Strategist on every park (the P13 4284 futile spin,
    2026-06-15); re-engaging a parked brick is T4's call (the active-check),
    not an unconditional inject_batch_done."""
    root = _insert_goal(conn, slug="main", origin="root",
                        status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="shelve-batch", count=1)
    fwd = _insert_goal(conn, slug="fwd", origin="forward", status="open")
    db.set_inject_decision_produced_goal(conn, ids[0], fwd)

    cascade_one(conn, pipeline_id="p1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[0])
    assert _seed_inject_batch_rows  # silence import-only lint
    assert root  # root exists for the problem

    # Lemma shelves → outcome stays NULL (not settled), batch incomplete.
    from Tooling.core.dispatcher import _set_goal_terminal_and_propagate
    _set_goal_terminal_and_propagate(conn, fwd, "shelved")
    row = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (ids[0],),
    ).fetchone()
    assert row["outcome"] is None
    # No Strategist enqueued — no spurious inject_batch_done on a park.
    q = list(conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ))
    assert q[0]["n"] == 0


def test_batch_done_immediate_on_leaf_bypass(
    conn: sqlite3.Connection,
) -> None:
    """Forward leaf-bypass (sorry-free) produces a goal already at
    status='proved'. forward.forward_parse guards `outcome.status !=
    'proved'` so it does NOT set produced_goal_id. cascade_one then
    fills outcome immediately (legacy path), no defer."""
    root = _insert_goal(conn, slug="main", origin="root",
                        status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="leaf-batch", count=1)
    # Simulate leaf-bypass: produced_goal_id is NOT set on decision.
    # cascade_one Forward branch sees no produced_goal_id → fills
    # outcome immediately.
    cascade_one(conn, pipeline_id="p1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[0])
    row = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (ids[0],),
    ).fetchone()
    assert row["outcome"] is not None
    q = list(conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ))
    assert q[0]["n"] == 1


def test_batch_done_immediate_on_forward_fail_no_goal(
    conn: sqlite3.Connection,
) -> None:
    """Forward that doesn't produce a goal (forward_no_new_goal,
    agent_declined, parse_rejected) leaves produced_goal_id=NULL.
    cascade_one fills outcome immediately (legacy)."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="fail-batch", count=1)

    cascade_one(conn, pipeline_id="p1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="forward_no_new_goal",
                decision_id=ids[0])
    row = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (ids[0],),
    ).fetchone()
    assert row["outcome"] is not None
    assert "forward_no_new_goal" in str(row["outcome"])


def test_batch_infra_failure_does_not_advance_completion(
    conn: sqlite3.Connection,
) -> None:
    """Infra outcomes (spawn_fast_fail / gateway_unreachable / quota_
    exhausted / transient_timeout / missing_dep) don't fill the batch
    row's outcome — those are transport failures, not the agent's
    Forward decision. Batch completion is not advanced; Strategist
    not enqueued."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="batch-infra", count=2)

    cascade_one(conn, pipeline_id="pid1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="spawn_fast_fail",
                decision_id=ids[0])
    cascade_one(conn, pipeline_id="pid2", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="gateway_unreachable",
                decision_id=ids[1])
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE batch_id='batch-infra'"
    ))
    assert all(r["outcome"] is None for r in rows)
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_null_batch_id_row_records_outcome_but_no_batch_trigger(
    conn: sqlite3.Connection,
) -> None:
    """Defensive: under unified Phase 2.5 every Inject is a batch and
    every row carries batch_id. If a legacy or manually-inserted Inject
    row has batch_id=NULL, cascade still records outcome (useful for
    failure_replay) but the batch-done check no-ops via
    `_maybe_enqueue_inject_batch_done`'s NULL guard — no Strategist
    enqueue fires."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'Inject', NULL, 'solo',"
        "         NULL, '{}', NULL, NULL, ?, ?)",
        (db.now(), db.now()),
    )
    rid = int(cur.lastrowid)
    conn.commit()

    cascade_one(conn, pipeline_id="pidsolo", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=rid)
    r = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?", (rid,)
    ).fetchone()
    assert r["outcome"] is not None
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_one_shot_proved_brick_still_closes_its_batch(
    conn: sqlite3.Connection,
) -> None:
    """The best case must still fire the batch-done relay.

    A Forward brick that lands proved in ONE shot fills its own decision
    outcome at commit time (`forward.py`, since the produced-goal link
    became unconditional in e9e55599) and its goal never transitions
    again — so the goal-side relay never runs for it either. If the
    cascade also stays silent, a batch of such bricks completes with
    nobody woken and only T4's stall backstop rescues the run: the
    Strategist then wakes reading `## Framework stalled` on a batch
    where every brick succeeded (SG 2026-08-02, 4 of 6 `[stall-wake]`).
    """
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="batch-oneshot", count=2)

    for i, did in enumerate(ids):
        g = _insert_goal(conn, slug=f"brick{i}", origin="forward",
                         status="proved")
        # Exactly what forward.py does once the brick commits proved.
        db.set_inject_decision_produced_goal(conn, did, g, kind="minted")
        db.propagate_inject_outcome_from_goal(conn, g)
        # Then the pipeline result reaches the cascade.
        cascade_one(conn, pipeline_id=f"pid{i}", kind="Formalizer",
                    target_id="p", target_kind="Problem",
                    outcome="proved", decision_id=did)

    pending = conn.execute(
        "SELECT COUNT(*) AS n FROM strategist_decisions"
        " WHERE batch_id = 'batch-oneshot' AND outcome IS NULL"
    ).fetchone()["n"]
    assert pending == 0
    rows = conn.execute(
        "SELECT target_id FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert [r["target_id"] for r in rows] == [_top(conn, "p")]


def test_unacknowledged_inject_batches_helper(
    conn: sqlite3.Connection,
) -> None:
    """db.unacknowledged_inject_batches returns batch_ids with all rows
    outcome-filled AND a row update newer than last_strategist_at."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids_a = _seed_inject_batch_rows(conn, batch_id="batch-A", count=2)
    ids_b = _seed_inject_batch_rows(conn, batch_id="batch-B", count=2)

    # A fully done
    for rid in ids_a:
        conn.execute(
            "UPDATE strategist_decisions SET outcome='success', updated_at = ?"
            " WHERE id = ?", (db.now(), rid))
    # B half done
    conn.execute(
        "UPDATE strategist_decisions SET outcome='success', updated_at = ?"
        " WHERE id = ?", (db.now(), ids_b[0]))
    conn.commit()
    batches = db.unacknowledged_inject_batches(conn, "p")
    assert batches == ["batch-A"]

    # Advance last_strategist_at; batch A becomes acknowledged
    db.update_problem_last_strategist_at(conn, "p")
    batches2 = db.unacknowledged_inject_batches(conn, "p")
    assert batches2 == []


# ---------------------------------------------------------------------
# cascade_one Strategist failure handling (2026-05-27 Banach-Tarski bug)
# ---------------------------------------------------------------------

def test_cascade_strategist_infra_failure_re_enqueues(
    conn: sqlite3.Connection, capsys: pytest.CaptureFixture,
) -> None:
    """An infra failure on a Strategist spawn (watchdog stuck-kill,
    claude.exe crash, gateway transient) leaves the originating T0/T1/T2
    trigger unfulfilled. Re-enqueue so the next tick retries; without
    this fix the framework waits up to `strategist.interval_min` for the
    next T1 wake.

    Regression: 2026-05-27 Banach-Tarski daemon — Strategist spawn died
    rc=128 (stuck_thinking); g3246 stuck in pending_strategist_review
    for 30+ min until the next T1.
    """
    root = _insert_goal(conn, slug="main", origin="root")
    cascade_one(
        conn, pipeline_id="pid-strat-infra",
        kind="Strategist", target_id=str(root), target_kind="Goal",
        outcome="failed", failure_reason="spawn_fast_fail",
    )
    rows = conn.execute(
        "SELECT kind, target_id, target_kind, priority FROM queue"
        " WHERE kind='Strategist'"
    ).fetchall()
    assert len(rows) == 1
    assert int(rows[0]["target_id"]) == root
    assert rows[0]["target_kind"] == "Goal"
    assert rows[0]["priority"] == 20
    captured = capsys.readouterr()
    assert "[strategist-retry]" in captured.out


def test_strategist_infra_retry_resolves_a_group_targets_problem(
    conn: sqlite3.Connection, capsys,
) -> None:
    """2026-08-03 SLC 3h20m stall: v35 strategist targets are
    Group-keyed but `_queue_problem_of` only knew Problem/Goal, so the
    fast-fail retry enqueued `problem=''` — a POISON row a scoped pop
    can never claim while `is_in_queue` still counts it, suppressing
    T1 and T4 for the group forever. The retry row must carry the
    group's real problem."""
    from Tooling.state import groups
    top = groups.ensure_top_group(conn, "p")
    conn.commit()
    cascade_one(
        conn, pipeline_id="pid-strat-group-infra",
        kind="Strategist", target_id=str(top), target_kind="Group",
        outcome="failed", failure_reason="spawn_fast_fail",
    )
    row = conn.execute(
        "SELECT problem FROM queue WHERE kind='Strategist'"
        " AND target_id=?", (str(top),)).fetchone()
    assert row is not None and row["problem"] == "p"


def test_strategist_infra_retry_never_enqueues_a_poison_row(
    conn: sqlite3.Connection, capsys,
) -> None:
    """An unresolvable target must NOT be re-enqueued with an empty
    problem — skip loudly and leave the wake to the T4 backstop."""
    cascade_one(
        conn, pipeline_id="pid-strat-poison",
        kind="Strategist", target_id="999999", target_kind="Group",
        outcome="failed", failure_reason="spawn_fast_fail",
    )
    n = conn.execute(
        "SELECT COUNT(*) FROM queue WHERE kind='Strategist'"
        " AND (problem IS NULL OR problem = '')").fetchone()[0]
    assert n == 0
    captured = capsys.readouterr()
    assert "SKIPPED re-queue" in captured.out


def test_is_in_queue_ignores_poison_rows(conn: sqlite3.Connection) -> None:
    """The deadlock's second edge: a scoped pop can never dispatch an
    empty-problem row, so counting it as 'in queue' converts one bad
    row into permanent T1/T4 suppression for its target."""
    conn.execute(
        "INSERT INTO queue (kind, target_id, target_kind, priority,"
        " problem, created_at) VALUES ('Strategist', '42', 'Group', 10,"
        " '', ?)", (db.now(),))
    conn.commit()
    assert db.is_in_queue(conn, target_id="42", kind="Strategist") is False


def test_recovery_sweeps_poison_rows_regardless_of_scope(
    conn: sqlite3.Connection, capsys,
) -> None:
    """recovery's scoped clean filters `problem LIKE scope`, which is
    exactly why the 08-03 poison row survived every restart — an empty
    problem matches no scope. The poison sweep must run scope-blind."""
    from Tooling.state import recovery
    conn.execute(
        "INSERT INTO queue (kind, target_id, target_kind, priority,"
        " problem, created_at) VALUES ('Strategist', '42', 'Group', 10,"
        " '', ?)", (db.now(),))
    conn.commit()
    recovery.recover_at_startup(conn, scope="Some.other_problem")
    n = conn.execute(
        "SELECT COUNT(*) FROM queue WHERE problem = ''").fetchone()[0]
    assert n == 0
    assert "POISON" in capsys.readouterr().out


def test_cascade_strategist_success_does_not_re_enqueue(
    conn: sqlite3.Connection,
) -> None:
    """Happy path: a successful Strategist commit must NOT trigger
    re-enqueue (would race with the next T2 trigger and double-spawn)."""
    root = _insert_goal(conn, slug="main", origin="root")
    cascade_one(
        conn, pipeline_id="pid-strat-ok",
        kind="Strategist", target_id=str(root), target_kind="Goal",
        outcome="success",
    )
    rows = conn.execute(
        "SELECT COUNT(*) c FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert rows["c"] == 0


def test_cascade_strategist_non_infra_failure_does_not_re_enqueue(
    conn: sqlite3.Connection,
) -> None:
    """Agent-quality failures (decisions all rejected by verify_decision,
    etc.) ARE deterministic — re-enqueueing would just re-fail the same
    way. Only infra reasons re-enqueue; everything else waits for the
    next T1 routine wake.
    """
    root = _insert_goal(conn, slug="main", origin="root")
    cascade_one(
        conn, pipeline_id="pid-strat-bad-decision",
        kind="Strategist", target_id=str(root), target_kind="Goal",
        outcome="failed", failure_reason="agent_no_annotation",
    )
    rows = conn.execute(
        "SELECT COUNT(*) c FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert rows["c"] == 0


# ---------------------------------------------------------------------
# cascade_one Forward infra failure re-enqueue (batch-wedge fix)
# ---------------------------------------------------------------------

def test_cascade_forward_infra_failure_re_enqueues(
    conn: sqlite3.Connection, capsys: pytest.CaptureFixture,
) -> None:
    """An infra failure on an Inject Forward consumes the queue row
    WITHOUT filling the decision outcome (by design — no real attempt
    happened). Without a re-enqueue the batch can never complete: the
    NULL outcome suppresses every Strategist wake on the problem (T0 /
    T1 / T4 all carry the in-flight-batch NOT EXISTS clause) and
    `inject_batch_done` never fires — the problem wedges until a daemon
    restart. cascade must re-enqueue the Forward with the same
    decision_id, mirroring the Strategist infra re-enqueue."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    [rid] = _seed_inject_batch_rows(conn, batch_id="batch-fwd-infra",
                                    count=1)

    cascade_one(conn, pipeline_id="pid-fwd-infra", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="spawn_fast_fail",
                decision_id=rid)

    rows = conn.execute(
        "SELECT target_id, target_kind, priority, decision_id FROM queue"
        " WHERE kind='Formalizer'").fetchall()
    assert len(rows) == 1
    assert rows[0]["target_id"] == "p"
    assert rows[0]["target_kind"] == "Problem"
    assert int(rows[0]["decision_id"]) == rid
    # Outcome must STAY NULL — the retried attempt fills it; filling
    # here would fire inject_batch_done before the lemma exists.
    r = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (rid,)).fetchone()
    assert r["outcome"] is None
    assert "[forward-retry]" in capsys.readouterr().out


def test_cascade_forward_infra_with_produced_goal_no_re_enqueue(
    conn: sqlite3.Connection,
) -> None:
    """If the Forward already linked `produced_goal_id` (sorry-bearing
    lemma committed before the infra failure), the outcome arrives via
    `propagate_inject_outcome_from_goal` when the lemma terminates —
    re-spawning would mint a second lemma onto the same decision row.
    Guard mirrors recovery's in-flight Inject re-enqueue."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    lemma = _insert_goal(conn, slug="s1_lemma", status="open")
    [rid] = _seed_inject_batch_rows(conn, batch_id="batch-fwd-prod",
                                    count=1)
    db.set_inject_decision_produced_goal(conn, rid, lemma)

    cascade_one(conn, pipeline_id="pid-fwd-infra2", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="quota_exhausted",
                decision_id=rid)

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Forward'").fetchone()
    assert q["n"] == 0
    # Outcome stays NULL here too — it belongs to the lemma's terminal.
    r = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (rid,)).fetchone()
    assert r["outcome"] is None


def test_return_to_nl_routes_to_review(
    conn: sqlite3.Connection,
) -> None:
    """NL-first (2026-07-25): a worker declining `no_nl_correspondence`
    (goal traces to no Programme Proof step) routes the goal to
    pending_strategist_review — the claim's justification is the
    Strategist's debt, not a death. Mirrors the agent_shelved path:
    attempts++ once, upward chain stays alive, Strategist enqueued."""
    _insert_goal(conn, slug="main", origin="root")
    g = _insert_goal(conn, slug="unbacked_claim", status="attempting")
    cascade_one(
        conn, pipeline_id="pid-nonl", kind="Backward",
        target_id=str(g), target_kind="Goal",
        outcome="failed", failure_reason="return_to_nl",
    )
    gg = db.get_goal(conn, g)
    assert gg["status"] == "pending_strategist_review"
    assert gg["attempts"] == 1
    row = conn.execute(
        "SELECT COUNT(*) FROM queue WHERE kind = 'Strategist'").fetchone()
    assert row[0] == 1
