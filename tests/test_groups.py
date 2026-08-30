"""Discussion-group store + v35 migration (discussion_group_design.md).

Strategy mirrors test_phase2_migration.py: for the store, drive
`state.groups` against a fresh schema; for the migration, hand-roll the
v34 shape of the three rebuilt tables and assert the widening preserves
every row while the backfill leaves a one-group tree that describes
exactly what was there before.
"""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.state import db
from Tooling.state import db_migrations
from Tooling.state import groups


def _conn(tmp_path, name="asterism.db"):
    c = db.connect(tmp_path / name)
    db.init_schema(c)
    return c


def _problem(conn, name="Test.p"):
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, '2026-08-02T00:00:00Z')", (name,))
    return name


def _goal(conn, problem, slug, *, origin="forward", status="open"):
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement, origin,"
        " status, created_at, updated_at)"
        " VALUES (?, ?, ?, 'theorem x : True', ?, ?, 't', 't')",
        (problem, slug, f"{problem}/{slug}.lean", origin, status))
    return int(cur.lastrowid)


def _decision(conn, problem, *, group_id, produced_goal_id=None,
              kind="Inject"):
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, produced_goal_id,"
        " payload, created_at, updated_at)"
        " VALUES (?, 0, 'routine', ?, ?, ?, '{}', 't', 't')",
        (problem, kind, group_id, produced_goal_id))
    return int(cur.lastrowid)


def _edge(conn, parent_goal, child_goal):
    """parent_goal --(strategy)--> child_goal, the only tree edge shape."""
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at) VALUES (?, '', 'proposed', 'test', 't')",
        (parent_goal,))
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, child_goal))
    return sid


# ---------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------

def test_ensure_top_group_is_idempotent_and_carries_the_clocks(tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.clocks")
    conn.execute(
        "UPDATE problems SET last_routine_at = 'R', last_strategist_at = 'S'"
        " WHERE name = ?", (p,))
    gid = groups.ensure_top_group(conn, p)
    assert groups.ensure_top_group(conn, p) == gid
    row = groups.top_group(conn, p)
    assert row["last_routine_at"] == "R"
    assert row["last_strategist_at"] == "S"
    assert row["charter"] == ""          # no charter kwarg → empty; init
    assert groups.is_top(row)            # passes the problem's goal


def test_second_top_group_for_one_problem_is_rejected(tmp_path):
    """The 'who faces the human' invariant is pinned in the schema, not
    trusted to the code that creates it (CLAUDE.md rule 6)."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.uniq")
    groups.ensure_top_group(conn, p)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO groups (problem, parent_group_id, charter, status,"
            " created_at, updated_at) VALUES (?, NULL, '', 'active', 't', 't')",
            (p,))


def test_open_group_requires_a_charter(tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.charter")
    top = groups.ensure_top_group(conn, p)
    for empty in ("", "   ", "\n"):
        with pytest.raises(ValueError):
            groups.open_group(conn, problem=p, parent_group_id=top,
                              charter=empty)


def test_sub_group_is_not_top_and_walks_up_to_it(tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.tree")
    top = groups.ensure_top_group(conn, p)
    mid = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="settle claim A")
    leaf = groups.open_group(conn, problem=p, parent_group_id=mid,
                             charter="settle sub-claim A1")
    assert not groups.is_top(groups.get(conn, leaf))
    assert [int(r["id"]) for r in groups.ancestors(conn, leaf)] == [mid, top]
    assert groups.ancestors(conn, top) == []
    assert [int(r["id"]) for r in groups.children(conn, top)] == [mid]


def test_ancestors_does_not_spin_on_a_cycle(tmp_path):
    """A cycle is a framework bug; the walk must surface it as a short
    chain rather than hang the dispatcher tick that called it."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.cycle")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="a")
    b = groups.open_group(conn, problem=p, parent_group_id=a, charter="b")
    conn.execute("UPDATE groups SET parent_group_id = ? WHERE id = ?", (b, a))
    assert len(groups.ancestors(conn, b)) <= 3


def test_set_status_rejects_an_unknown_status(tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.status")
    top = groups.ensure_top_group(conn, p)
    with pytest.raises(ValueError):
        groups.set_status(conn, top, "finished")
    groups.set_status(conn, top, "delivered")
    assert groups.get(conn, top)["status"] == "delivered"


# ---------------------------------------------------------------------
# group_for_goal — which Strategist a review on this goal should wake
# ---------------------------------------------------------------------

def test_group_for_goal_prefers_the_anchor_over_the_producing_decision(
        tmp_path):
    """The rescue shape: the parent's decision promoted the goal, but the
    goal now belongs to the CHILD group it anchors."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.anchor")
    top = groups.ensure_top_group(conn, p)
    g = _goal(conn, p, "promoted")
    _decision(conn, p, group_id=top, produced_goal_id=g, kind="Delegate")
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="work the promoted goal",
                            anchor_goal_id=g)
    assert int(groups.group_for_goal(conn, p, g)["id"]) == sub


def test_group_for_goal_inherits_from_the_nearest_producing_ancestor(
        tmp_path):
    """A worker's sub-goals carry no decision of their own — they belong
    to whoever dispatched the goal above them."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.inherit")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    minted = _goal(conn, p, "minted")
    _decision(conn, p, group_id=sub, produced_goal_id=minted)
    kid = _goal(conn, p, "kid")
    grandkid = _goal(conn, p, "grandkid")
    _edge(conn, minted, kid)
    _edge(conn, kid, grandkid)
    assert int(groups.group_for_goal(conn, p, kid)["id"]) == sub
    assert int(groups.group_for_goal(conn, p, grandkid)["id"]) == sub


def test_group_for_goal_gives_a_reused_goal_to_its_latest_claimant(tmp_path):
    """Dedupe repoints an Inject at an existing goal, so two groups can
    have dispatched the same node. The one most recently waiting on it is
    the one a review concerns."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.reuse")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    b = groups.open_group(conn, problem=p, parent_group_id=top, charter="B")
    shared = _goal(conn, p, "shared")
    _decision(conn, p, group_id=a, produced_goal_id=shared)
    _decision(conn, p, group_id=b, produced_goal_id=shared)
    assert int(groups.group_for_goal(conn, p, shared)["id"]) == b


def test_group_for_goal_skips_a_finished_group(tmp_path):
    """A wake sent to a group with no seat is dropped on the floor; the
    leftovers belong to whoever is still working above it."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.finished")
    top = groups.ensure_top_group(conn, p)
    mid = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    leaf = groups.open_group(conn, problem=p, parent_group_id=mid,
                             charter="A1")
    g = _goal(conn, p, "leftover")
    _decision(conn, p, group_id=leaf, produced_goal_id=g)
    assert int(groups.group_for_goal(conn, p, g)["id"]) == leaf
    groups.set_status(conn, leaf, "returned")
    assert int(groups.group_for_goal(conn, p, g)["id"]) == mid
    groups.set_status(conn, mid, "closed")
    assert int(groups.group_for_goal(conn, p, g)["id"]) == top


def test_group_for_goal_survives_a_detached_mint(tmp_path):
    """`detached` seeds the top-down alive CTE; it does not remove the
    strategy_subgoals edges this walk climbs — so a detached mint's whole
    subtree still resolves to the group that minted it."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.detached")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    minted = _goal(conn, p, "minted")
    conn.execute("UPDATE goals SET detached = 1 WHERE id = ?", (minted,))
    _decision(conn, p, group_id=sub, produced_goal_id=minted)
    kid = _goal(conn, p, "kid")
    _edge(conn, minted, kid)
    assert int(groups.group_for_goal(conn, p, minted)["id"]) == sub
    assert int(groups.group_for_goal(conn, p, kid)["id"]) == sub


def test_group_for_goal_falls_back_to_the_top_group(tmp_path):
    """Orphans and pre-group work are the top group's — never None, or
    the wake would have nowhere to go."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.orphan")
    top = groups.ensure_top_group(conn, p)
    stray = _goal(conn, p, "stray")
    assert int(groups.group_for_goal(conn, p, stray)["id"]) == top


def test_group_for_goal_picks_the_nearest_when_two_groups_are_above(
        tmp_path):
    """Depth beats recency: the closest producing ancestor owns the goal,
    even when a group further up also produced one on the same chain."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.nearest")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    high = _goal(conn, p, "high")
    _decision(conn, p, group_id=top, produced_goal_id=high)
    low = _goal(conn, p, "low")
    _decision(conn, p, group_id=sub, produced_goal_id=low)
    kid = _goal(conn, p, "kid")
    _edge(conn, high, low)
    _edge(conn, low, kid)
    assert int(groups.group_for_goal(conn, p, kid)["id"]) == sub


# ---------------------------------------------------------------------
# The batch cycle — a delegated burden is the parent's third artifact
# ---------------------------------------------------------------------

def _delegate(conn, problem, *, group_id, produced_group_id, batch_id="b1"):
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, produced_group_id,"
        " batch_id, payload, created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Delegate', ?, ?, ?, '{}', 't', 't')",
        (problem, group_id, produced_group_id, batch_id))
    return int(cur.lastrowid)


def test_an_active_group_keeps_the_parent_in_flight(tmp_path):
    """The point of the third artifact: a delegated burden with no anchor
    goal has neither a produced goal nor a produced strategy, so without
    the group arm T4 would wake the parent on every tick while its child
    is still working."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.quiet")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    _delegate(conn, p, group_id=top, produced_group_id=sub)
    assert db.has_active_inflight_inject(conn, p) is True


@pytest.mark.parametrize("terminal", ["delivered", "returned", "closed"])
def test_a_finished_group_settles_the_delegate_and_wakes_the_parent(
        tmp_path, terminal):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.settle")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    did = _delegate(conn, p, group_id=top, produced_group_id=sub)

    groups.set_status(conn, sub, terminal)

    outcome = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (did,)).fetchone()["outcome"]
    assert outcome == ("success" if terminal == "delivered"
                       else f"failed:{terminal}")
    assert db.has_active_inflight_inject(conn, p) is False
    # The batch is complete, so exactly one Strategist wake was queued.
    assert conn.execute(
        "SELECT COUNT(*) FROM queue WHERE kind = 'Strategist'"
        " AND problem = ?", (p,)).fetchone()[0] == 1


def test_the_batch_waits_for_the_delegate_and_the_inject_together(tmp_path):
    """User's constraint: dispatch a Formalizer and a group in one batch
    and the parent wakes only when BOTH are terminal. The cycle keys on
    batch_id alone, so this holds without the counter knowing the kinds —
    but it is exactly what would silently break if a new kind were minted
    outside the batch."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.pair")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    minted = _goal(conn, p, "minted")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, produced_goal_id,"
        " batch_id, payload, created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Inject', ?, ?, 'b1', '{}', 't', 't')",
        (p, top, minted))
    _delegate(conn, p, group_id=top, produced_group_id=sub, batch_id="b1")

    # Only the group finishes → the batch is still open, no wake.
    groups.set_status(conn, sub, "delivered")
    assert conn.execute(
        "SELECT COUNT(*) FROM queue WHERE kind = 'Strategist'").fetchone()[
            0] == 0

    # The lemma lands too → the batch completes and the parent wakes once.
    conn.execute("UPDATE goals SET status = 'proved' WHERE id = ?", (minted,))
    filled = db.propagate_inject_outcome_from_goal(conn, minted)
    db.maybe_enqueue_inject_batch_done(conn, filled)
    assert conn.execute(
        "SELECT COUNT(*) FROM queue WHERE kind = 'Strategist'").fetchone()[
            0] == 1


def test_a_delegated_group_opens_the_anti_idle_gate(tmp_path):
    """The OTHER in-flight predicate. A parent woken by its routine clock
    must commit a batch; if it delegated everything, `Noop` is its only
    legal output — and `Noop` on a blocked root is rejected unless
    something moves without this Strategist. A child group moves by its
    own seat and its own clock, so it counts. Without this the parent is
    forced to invent work beside the burden it just handed off."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.antiidle")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    _delegate(conn, p, group_id=top, produced_group_id=sub)
    assert db.has_live_inflight_inject(conn, p) is True
    groups.set_status(conn, sub, "returned")
    assert db.has_live_inflight_inject(conn, p) is False


def test_both_in_flight_predicates_agree_about_a_group(tmp_path):
    """The two have disagreed on one state three times, each time a
    livelock or a deadlock (P13 4284 spin -> cond-4 deadlock -> the b6
    301-spawn pump). A new artifact form must enter BOTH gates."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.agree")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    _delegate(conn, p, group_id=top, produced_group_id=sub)
    for status in ("active", "delivered", "returned", "closed"):
        conn.execute("UPDATE groups SET status = ? WHERE id = ?",
                     (status, sub))
        assert (db.has_active_inflight_inject(conn, p)
                == db.has_live_inflight_inject(conn, p)), status


def test_reconcile_settles_a_delegate_whose_group_already_finished(tmp_path):
    """The stuck-outcome sweep must cover the third artifact too — a
    permanently-NULL Delegate outcome would suppress T4 forever."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.reconcile")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    did = _delegate(conn, p, group_id=top, produced_group_id=sub)
    # Terminal status written WITHOUT the sanctioned mutator — the exact
    # shape the sweep exists to repair.
    conn.execute("UPDATE groups SET status = 'delivered' WHERE id = ?", (sub,))
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (did,)).fetchone()["outcome"] == "success"


def test_a_delegate_is_never_queued_for_redispatch(tmp_path):
    """A Delegate has no worker to re-enqueue — its executor is the
    group's own Strategist seat."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.noredispatch")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    _delegate(conn, p, group_id=top, produced_group_id=sub)
    assert db.null_inject_redispatch_specs(conn) == []


# ---------------------------------------------------------------------
# The Strategist seat belongs to a group, not a problem
# ---------------------------------------------------------------------

def _stale(conn, group_id):
    conn.execute(
        "UPDATE groups SET last_routine_at = '2020-01-01T00:00:00+00:00'"
        " WHERE id = ?", (group_id,))


def _seats(conn):
    return {(r["target_id"], r["target_kind"]) for r in conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind = 'Strategist'")}


def test_sibling_groups_each_get_their_own_routine_seat(tmp_path):
    """The whole point of the tree: two live groups work concurrently
    instead of taking turns at one problem-wide seat."""
    from Tooling.core.dispatcher import strategist_triggers
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.seats")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    b = groups.open_group(conn, problem=p, parent_group_id=top, charter="B")
    for gid in (top, a, b):
        _stale(conn, gid)
    conn.commit()

    strategist_triggers(conn, running=set(), interval_min=60.0)

    assert _seats(conn) == {(str(top), "Group"), (str(a), "Group"),
                            (str(b), "Group")}


def test_a_running_group_does_not_block_its_sibling(tmp_path):
    """Serialization is per group. A Strategist in flight for A must not
    suppress B's seat — that would re-impose the old one-at-a-time
    behaviour while looking like it had been fixed."""
    from Tooling.core.dispatcher import strategist_triggers
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.concurrent")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    b = groups.open_group(conn, problem=p, parent_group_id=top, charter="B")
    for gid in (top, a, b):
        _stale(conn, gid)
    conn.commit()

    running = {(str(a), "Strategist", None)}
    strategist_triggers(conn, running=running, interval_min=60.0)

    seats = _seats(conn)
    assert (str(b), "Group") in seats
    assert (str(a), "Group") not in seats


def test_a_finished_group_holds_no_seat(tmp_path):
    from Tooling.core.dispatcher import strategist_triggers
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.done")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    for gid in (top, a):
        _stale(conn, gid)
    groups.set_status(conn, a, "delivered")
    conn.commit()

    strategist_triggers(conn, running=set(), interval_min=60.0)
    assert (str(a), "Group") not in _seats(conn)


def test_a_problem_without_a_top_group_is_healed_not_stranded(tmp_path):
    """Every trigger keys on a group, so a problem with none has NO seat
    at all and fails silently. The per-tick reconciler is the net."""
    from Tooling.core.dispatcher import reconcile_stuck_states
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.stranded")
    conn.commit()
    assert groups.top_group(conn, p) is None
    reconcile_stuck_states(conn, running=set())
    assert groups.top_group(conn, p) is not None


def test_a_legacy_problem_keyed_seat_still_resolves(tmp_path):
    """Rows queued before v35 carry the problem name; they mean the top
    group and must keep dispatching, not fail the worker thread."""
    from Tooling.core.dispatcher import _strategist_target
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.legacy")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    assert _strategist_target(conn, p, "Problem") == (top, p)
    assert _strategist_target(conn, str(top), "Group") == (top, p)
    # Unresolvable rows: a vanished GROUP is garbage (ids never reused);
    # an unknown problem NAME keeps the pre-v35 anti-wedge answer.
    assert _strategist_target(conn, "99999", "Group") == (None, None)
    assert _strategist_target(conn, "no.such", "Problem") == (None, None)


def test_a_committed_batch_is_stamped_with_its_authoring_group(tmp_path):
    """`strategist_decisions.group_id` is what routes the batch-done wake
    back to the group that ordered the work."""
    from Tooling.pipeline import strategist as _strategist
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.stamp")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    # Two kinds so the stamp is proven per-row, not per-batch.
    # (FetchPaper used to ride here — its per-kind INSERT was the ONE
    # call site that dropped group_id, 2026-08-05 — retired 2026-08-22.)
    ds = [_strategist.Decision(kind="Noop", reason="waiting"),
          _strategist.Decision(kind="Noop", reason="second note")]
    _strategist.commit_decisions(ds, conn, problem=p, tick=0,
                                 trigger_kind="routine",
                                 workspace=tmp_path, group_id=sub)
    rows = conn.execute(
        "SELECT decision_kind, group_id FROM strategist_decisions"
        " WHERE problem = ?", (p,)).fetchall()
    assert [str(r["decision_kind"]) for r in rows] == ["Noop", "Noop"]
    assert all(int(r["group_id"]) == sub for r in rows)
    # ...and the routine commit advanced THAT group's clock, not another's.
    assert groups.get(conn, sub)["last_routine_at"] is not None
    assert groups.get(conn, top)["last_routine_at"] is None


# ---------------------------------------------------------------------
# Delegate / ReturnToParent
# ---------------------------------------------------------------------

def _S():
    from Tooling.pipeline import strategist as _s
    return _s


def _commit(conn, tmp_path, decisions, problem, group_id, *,
            trigger="routine"):
    return _S().commit_decisions(
        decisions, conn, problem=problem, tick=0, trigger_kind=trigger,
        workspace=tmp_path, group_id=group_id)


def _verify(conn, decision, problem, group_id):
    return _S().verify_decision(decision, conn, problem=problem,
                                group_id=group_id)


def test_delegate_opens_a_group_and_seats_it(tmp_path):
    """The main shape: no target. The group starts from prose, and its
    first seat is queued now — a fresh group's clock is NULL, which the
    routine selector reads as due one full interval after daemon start,
    so leaving it to T1 would stall a just-delegated burden for hours."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.deleg")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    d = _S().Decision(kind="Delegate", brief="Settle claim A: X > Y.")
    out = _commit(conn, tmp_path, [d], p, top)[0]

    kid = groups.children(conn, top)[0]
    assert kid["charter"] == "Settle claim A: X > Y."
    assert kid["anchor_goal_id"] is None
    assert int(kid["opened_by"]) == out.decision_row_id
    row = conn.execute(
        "SELECT produced_group_id, batch_id, group_id, outcome"
        " FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()
    assert int(row["produced_group_id"]) == int(kid["id"])
    assert int(row["group_id"]) == top
    assert row["batch_id"] is not None
    assert row["outcome"] is None            # settles when the group does
    assert (str(kid["id"]), "Group") in _seats(conn)


def test_delegate_seeds_the_child_with_the_parents_conventions(tmp_path):
    """Copy-on-open (2026-08-11). Conventions stopped walking the ancestor
    chain, so the Delegate path is where a parent's standing rules cross
    into a group opened later — otherwise a footgun learned up here is
    lost to every group opened after it, silently, and the child cannot
    ask for a rule it has never been told exists."""
    from Tooling.state import programme
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.seed")
    top = groups.ensure_top_group(conn, p)
    programme.record_pass(
        conn, p,
        "# T\n## Argument\na\n## Proof\nb\n## Roadmap\nc\n"
        "## Conventions\nVERIFY HINT NAMES AGAINST CATALOG\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=top)
    conn.commit()
    _commit(conn, tmp_path,
            [_S().Decision(kind="Delegate", brief="Settle claim A.")],
            p, top)

    kid = groups.children(conn, top)[0]
    assert "VERIFY HINT NAMES" in str(kid["conventions_seed"])
    # and it is what the child's workers read until the child has its own
    assert "VERIFY HINT NAMES" in programme.conventions_for_group(
        conn, p, int(kid["id"]))


def test_delegate_with_a_target_anchors_it_as_attempting(tmp_path):
    """The rescue shape. `attempting` is the only status that is both
    undispatchable by BFS and ALIVE — `frozen`/`shelved` are parked and
    would let T4 wake the parent every tick."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.rescue")
    top = groups.ensure_top_group(conn, p)
    g = _goal(conn, p, "stuck")
    conn.commit()
    d = _S().Decision(kind="Delegate", brief="Take over g_stuck.",
                      target_id=g)
    _commit(conn, tmp_path, [d], p, top)

    kid = groups.children(conn, top)[0]
    assert int(kid["anchor_goal_id"]) == g
    assert db.get_goal(conn, g)["status"] == "attempting"
    assert db.has_active_inflight_inject(conn, p) is True


def _proposal_brief(claim="claim A"):
    """The minimal legal Delegate charter (2026-08-19 reshape: the
    three-heading research-proposal shape retired with the
    charter/reason/brief split — the fan rule and the depth cap carry
    the structural burden now, and the judge rules on substance)."""
    return f"Settle {claim} — a kernel-checkable research item."


def test_a_delegate_requires_charter_and_reason(tmp_path):
    """2026-08-19 reshape: the claim (charter) and the parent-side
    justification (reason) are both mandatory; the guidance hand-off
    (brief) is optional. Successor of the retired research-proposal
    check — same intent (a group must have something to be judged on,
    and the opening must be argued), new fields."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.proposalbrief")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    err = _verify(conn, S.Decision(kind="Delegate", brief="settle claim A"),
                  p, top)
    assert "reason" in err
    assert "AHEAD" in err, "the refusal names the in-house alternative"
    err = _verify(conn, S.Decision(
        kind="Delegate", reason="cannot prove in-house"), p, top)
    assert "charter" in err
    assert _verify(conn, S.Decision(
        kind="Delegate", brief=_proposal_brief(), reason="cannot prove in-house nor pace through AHEAD"), p, top) == ""


def test_delegate_verify_rejects_the_shapes_that_would_strand_work(
        tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.dverify")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    # empty charter — a sub-group's charter cannot be blank
    assert "charter" in _verify(
        conn, S.Decision(kind="Delegate", brief="   "), p, top)
    # byte-identical to a LIVE sibling = double dispatch
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief(), reason="cannot prove in-house nor pace through AHEAD")], p, top)
    err = _verify(conn, S.Decision(
        kind="Delegate", brief=_proposal_brief(), reason="cannot prove in-house nor pace through AHEAD"), p, top)
    assert "duplicate" in err.lower()
    # ...but the same charter after that group RETURNED is allowed: only
    # the Adversary can judge whether the retry differs.
    kid = groups.children(conn, top)[0]
    groups.set_status(conn, int(kid["id"]), "returned")
    assert _verify(conn, S.Decision(
        kind="Delegate", brief=_proposal_brief(), reason="cannot prove in-house nor pace through AHEAD"), p, top) == ""
    # a settled goal has nothing for a group to work
    done = _goal(conn, p, "done", status="proved")
    assert "proved" in _verify(
        conn, S.Decision(kind="Delegate", brief=_proposal_brief("c"), reason="cannot prove in-house nor pace through AHEAD",
                         target_id=done), p, top)
    # one anchor, one group
    g = _goal(conn, p, "g")
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("own it"), reason="cannot prove in-house nor pace through AHEAD",
                        target_id=g)], p, top)
    assert "already anchors" in _verify(
        conn, S.Decision(kind="Delegate", brief=_proposal_brief("mine too"), reason="cannot prove in-house nor pace through AHEAD",
                         target_id=g), p, top)


def test_the_top_group_cannot_return_to_a_parent(tmp_path):
    """The structural wall. Not a prompt rule: the top group has no
    parent, so the difficulty escape hatch cannot reach the human
    channel — `RequestUserAmend` stays for a WRONG user file."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.topreturn")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    d = _S().Decision(kind="ReturnToParent", reason="too hard",
                      payload={"flavour": "exhausted"})
    err = _verify(conn, d, p, top)
    assert "top group" in err and "no parent" in err


def test_only_the_top_group_may_speak_to_the_human(tmp_path):
    """The mirror of the ReturnToParent wall. `RequestUserAmend` sets
    `awaiting_human`, which freezes the whole problem including every
    sibling group — a sub-group reaching the human that way is the same
    escape hatch through a side door with a larger blast radius."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.amend")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    d = _S().Decision(
        kind="RequestUserAmend", reason="Defs.lean has a typo",
        payload={"file": "Defs.lean", "proposed_body": "def f := 1",
                 "question": "is this what you meant?"})
    err = _verify(conn, d, p, sub)
    assert "TOP group" in err and "ReturnToParent" in err
    assert _verify(conn, d, p, top) == ""


def test_return_flavours_carry_their_own_evidence(tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.flavour")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    S = _S()
    assert "flavour" in _verify(
        conn, S.Decision(kind="ReturnToParent", reason="r",
                         payload={"flavour": "gave_up"}), p, sub)
    # refuted without a kernel-checked negation is an opinion
    assert "target_goal_id" in _verify(
        conn, S.Decision(kind="ReturnToParent", reason="r",
                         payload={"flavour": "refuted"}), p, sub)
    open_g = _goal(conn, p, "neg")
    assert "not 'proved'" in _verify(
        conn, S.Decision(kind="ReturnToParent", reason="r", target_id=open_g,
                         payload={"flavour": "refuted"}), p, sub)
    conn.execute("UPDATE goals SET status = 'proved' WHERE id = ?",
                 (open_g,))
    # 2026-08-30: proved is necessary, not sufficient — the node must be
    # the brick the disproof gate minted (`<slug>_disproof` beside a
    # `disproved` <slug>); a hand-minted negation has no kernel link to
    # the claim it says it refutes (test_disproof_road pins the pair).
    assert "gate" in _verify(
        conn, S.Decision(kind="ReturnToParent", reason="r", target_id=open_g,
                         payload={"flavour": "refuted"}), p, sub)
    # amend must actually propose a change
    assert "proposed_charter" in _verify(
        conn, S.Decision(kind="ReturnToParent", reason="r",
                         payload={"flavour": "amend"}), p, sub)
    assert "identical" in _verify(
        conn, S.Decision(kind="ReturnToParent", reason="r",
                         payload={"flavour": "amend",
                                  "proposed_charter": "claim A"}), p, sub)


def test_returning_settles_the_parents_delegate_and_parks_the_anchor(
        tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.returning")
    top = groups.ensure_top_group(conn, p)
    g = _goal(conn, p, "anchor")
    conn.commit()
    S = _S()
    out = _commit(conn, tmp_path,
                  [S.Decision(kind="Delegate", brief="own it", target_id=g)],
                  p, top)[0]
    kid = int(groups.children(conn, top)[0]["id"])
    conn.execute("DELETE FROM queue")         # ignore the child's own seat
    conn.commit()

    _commit(conn, tmp_path,
            [S.Decision(kind="ReturnToParent", reason="three routes died",
                        payload={"flavour": "exhausted"})],
            p, kid, trigger="inject_batch_done")

    assert groups.get(conn, kid)["status"] == "returned"
    assert conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()["outcome"] == "failed:returned"
    assert db.get_goal(conn, g)["status"] == "shelved"
    assert db.has_active_inflight_inject(conn, p) is False
    # The parent is woken by the ordinary batch-done relay.
    assert (str(top), "Group") in _seats(conn)


def test_a_batch_of_inject_plus_delegate_wakes_the_parent_once(tmp_path):
    """End to end through the real commit path: same batch, two artifact
    forms, one wake — and only after BOTH are terminal."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.mixed")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    outs = _commit(conn, tmp_path, [
        S.Decision(kind="Inject", brief="mint lemma_x"),
        S.Decision(kind="Delegate", brief="settle claim A"),
    ], p, top)
    assert outs[0].batch_id == outs[1].batch_id
    kid = int(groups.children(conn, top)[0]["id"])
    conn.execute("DELETE FROM queue")
    conn.commit()

    groups.set_status(conn, kid, "delivered")
    assert _seats(conn) == set()              # the Inject is still open

    minted = _goal(conn, p, "lemma_x", status="proved")
    conn.execute(
        "UPDATE strategist_decisions SET produced_goal_id = ?"
        " WHERE id = ?", (minted, outs[0].decision_row_id))
    filled = db.propagate_inject_outcome_from_goal(conn, minted)
    db.maybe_enqueue_inject_batch_done(conn, filled)
    assert (str(top), "Group") in _seats(conn)


# ---------------------------------------------------------------------
# Stall is detected per group
# ---------------------------------------------------------------------

def test_group_stall_matches_problem_stall_when_alone(tmp_path):
    """The alignment invariant. With one group the two predicates must
    agree in every state — they have disagreed about one state three
    times in this codebase, each time a livelock or a deadlock."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.alone")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    for setup in ("empty", "open_goal", "proved_goal"):
        if setup == "open_goal":
            g = _goal(conn, p, "og")
            conn.execute("UPDATE goals SET detached = 1 WHERE id = ?", (g,))
        elif setup == "proved_goal":
            conn.execute("UPDATE goals SET status = 'proved'")
        conn.commit()
        assert (db.is_group_stalled(conn, p, top)
                == db.is_problem_stalled(conn, p)), setup


def test_group_ownership_agrees_in_bulk(tmp_path):
    """`goals_by_group` is the bulk twin of `group_for_goal`; two
    predicates that disagree about one node is the disease."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.agree")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    b = groups.open_group(conn, problem=p, parent_group_id=a, charter="B")
    root = _goal(conn, p, "main", origin="root")
    minted = _goal(conn, p, "minted")
    _decision(conn, p, group_id=a, produced_goal_id=minted)
    kid = _goal(conn, p, "kid")
    _edge(conn, minted, kid)
    anchor = _goal(conn, p, "anchor")
    conn.execute("UPDATE groups SET anchor_goal_id = ? WHERE id = ?",
                 (anchor, b))
    below = _goal(conn, p, "below")
    _edge(conn, anchor, below)
    orphan = _goal(conn, p, "orphan")
    conn.commit()

    bulk = groups.goals_by_group(conn, p)
    for gid in (root, minted, kid, anchor, below, orphan):
        assert bulk[gid] == int(groups.group_for_goal(conn, p, gid)["id"]), gid
    # ...and the slices are what the names say.
    assert groups.goal_ids_in_group(conn, p, a) == {minted, kid}
    assert groups.goal_ids_in_group(conn, p, b) == {anchor, below}
    assert groups.goal_ids_in_group(conn, p, top) == {root, orphan}


def test_a_stalled_child_wakes_itself_not_the_whole_problem(tmp_path):
    """The direction the parent-side quiet rule does not cover: with a
    sibling busy the PROBLEM is not stalled, so the problem-wide reading
    wakes nobody — and when it does fire it wakes the top group rather
    than the one that is stuck."""
    from Tooling.core.dispatcher import strategist_triggers
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.childstall")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [
        S.Decision(kind="Delegate", brief="busy line"),
        S.Decision(kind="Delegate", brief="stuck line"),
    ], p, top)
    busy, stuck = (int(r["id"]) for r in groups.children(conn, top))
    # The busy group has a dispatchable goal; the stuck one has nothing.
    g = _goal(conn, p, "live")
    conn.execute("UPDATE goals SET detached = 1 WHERE id = ?", (g,))
    _decision(conn, p, group_id=busy, produced_goal_id=g)
    conn.execute("DELETE FROM queue")          # drop the opening seats
    for gid in (top, busy, stuck):
        _stale(conn, gid)
    conn.execute("UPDATE groups SET last_routine_at = NULL")  # isolate T4
    conn.execute(
        "UPDATE problems SET last_routine_at = ? WHERE name = ?",
        (db.now(), p))
    conn.commit()

    # T1 is off (NULL clock is only due after a full interval from the
    # daemon baseline), so any seat here is T4's.
    strategist_triggers(conn, running=set(), interval_min=60.0,
                        daemon_start_iso=db.now())

    assert db.is_group_stalled(conn, p, stuck) is True
    assert db.is_group_stalled(conn, p, busy) is False
    assert db.is_group_stalled(conn, p, top) is False   # children in flight
    assert _seats(conn) == {(str(stuck), "Group")}
    # The problem-wide reading would have said "not stalled" and woken
    # nobody at all.
    assert db.is_problem_stalled(conn, p) is False


# ---------------------------------------------------------------------
# Programme / plan note / judge projection are per group
# ---------------------------------------------------------------------

def _prog(title="T"):
    return (f"# {title}\n\n## Argument\na\n\n## Proof\np\n\n"
            f"## Roadmap\nr\n")


def test_each_group_owns_its_revision_chain_from_one(tmp_path):
    from Tooling.state import programme
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.chains")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    assert programme.record_pass(conn, p, _prog("top-1"), {}, [], 0, None,
                                 group_id=top) == 1
    assert programme.record_pass(conn, p, _prog("sub-1"), {}, [], 0, None,
                                 group_id=sub) == 1
    assert programme.record_pass(conn, p, _prog("top-2"), {}, [], 0, None,
                                 group_id=top) == 2
    assert programme.current_rev(conn, p, top)["rev"] == 2
    assert programme.current_rev(conn, p, sub)["rev"] == 1
    assert "sub-1" in programme.current_rev(conn, p, sub)["body"]


def test_a_sub_groups_render_stays_out_of_the_problem_dir(tmp_path):
    """PROGRAMME.md must keep meaning "the problem's argument" for every
    existing reader — the human, the UI, the judge's projection."""
    from Tooling.state import programme
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.render")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    pdir = tmp_path / "pdir"
    pdir.mkdir()
    programme.record_pass(conn, p, _prog("top"), {}, [], 0, None,
                          group_id=top)
    programme.record_pass(conn, p, _prog("sub"), {}, [], 0, None,
                          group_id=sub)
    assert programme.render(conn, p, pdir, top) == pdir / "PROGRAMME.md"
    out = programme.render(conn, p, pdir, sub)
    assert out == pdir / ".groups" / str(sub) / "PROGRAMME.md"
    assert "# top" in (pdir / "PROGRAMME.md").read_text(encoding="utf-8")
    assert "# sub" in out.read_text(encoding="utf-8")


def test_plan_notes_do_not_clobber_each_other(tmp_path):
    """The note is a REWRITE by contract, so one shared file would mean
    each group erasing the other's facts every wake."""
    from Tooling.pipeline import _drafts
    pdir = tmp_path / "pdir"
    (pdir / ".drafts").mkdir(parents=True)
    a = _drafts.plan_note_path(pdir, 7)
    b = _drafts.plan_note_path(pdir, 9)
    top = _drafts.plan_note_path(pdir)
    assert len({a, b, top}) == 3
    a.write_text("facts of 7", encoding="utf-8")
    b.write_text("facts of 9", encoding="utf-8")
    assert _drafts.read_plan_note(pdir, 7) == "facts of 7"
    assert _drafts.read_plan_note(pdir, 9) == "facts of 9"
    assert _drafts.read_plan_note(pdir) is None


def test_the_judge_sees_the_charter_chain_at_every_depth(tmp_path):
    """Criterion 3 otherwise only catches a claim leaning on the PARENT's
    conclusion; on a deep tree circularity arrives a generation later.
    v40 (Manifest retirement): the top group renders too — its charter
    IS the problem's goal — and the ancestor chain includes it."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.charterdigest")
    top = groups.ensure_top_group(conn, p, charter="TOP: the root claim")
    a = groups.open_group(conn, problem=p, parent_group_id=top,
                          charter="A: the growth bound")
    b = groups.open_group(conn, problem=p, parent_group_id=a,
                          charter="B: the recurrence step")
    conn.commit()
    top_txt = groups.charter_digest(conn, p, top)
    assert "TOP: the root claim" in top_txt
    assert "Charters above this one" not in top_txt  # top has no ancestors
    # group_id=None resolves to the top group (problem-level callers).
    assert groups.charter_digest(conn, p, None) == top_txt
    txt = groups.charter_digest(conn, p, b)
    assert "B: the recurrence step" in txt
    assert "A: the growth bound" in txt        # the ancestor chain
    assert "TOP: the root claim" in txt        # ...top group included (v40)
    assert "circular" in txt


def test_the_judge_sees_charters_this_subtree_handed_back(tmp_path):
    """Material, not a gate: whether a retry differs is a judgement about
    mathematics, which a string comparison cannot make."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.returneddigest")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [S.Decision(kind="Delegate",
                                        brief="settle the p-adic bound")],
            p, top)
    dead = int(groups.children(conn, top)[0]["id"])
    _commit(conn, tmp_path,
            [S.Decision(kind="ReturnToParent",
                        reason="valuation argument circular at step 3",
                        payload={"flavour": "exhausted"})],
            p, dead, trigger="inject_batch_done")
    fresh = groups.open_group(conn, problem=p, parent_group_id=top,
                              charter="settle the p-adic bound, again")
    conn.commit()

    txt = groups.charter_digest(conn, p, fresh)
    assert "settle the p-adic bound" in txt
    assert "exhausted" in txt
    assert "circular at step 3" in txt
    assert "not a verdict" in txt.lower()


def test_a_cousin_branchs_failures_stay_out_of_my_projection(tmp_path):
    """Per-group projection isolation: only the failures on MY chain —
    what the groups above me already tried — are mine to see. A cousin
    branch's returned charter is another judge's business, and pulling
    it in is exactly the cross-group leak the isolation ruling forbids."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.cousins")
    top = groups.ensure_top_group(conn, p)
    S = _S()
    # Two branches under the top group; the failure happens in branch A.
    a = groups.open_group(conn, problem=p, parent_group_id=top,
                          charter="branch A")
    b = groups.open_group(conn, problem=p, parent_group_id=top,
                          charter="branch B")
    conn.commit()
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief="A's sub-line")], p, a)
    dead = int(groups.children(conn, a)[0]["id"])
    _commit(conn, tmp_path,
            [S.Decision(kind="ReturnToParent", reason="A's line died",
                        payload={"flavour": "exhausted"})],
            p, dead, trigger="inject_batch_done")
    conn.commit()

    # A sees its own branch's failure; B — a cousin — must not.
    assert "A's sub-line" in groups.charter_digest(conn, p, a)
    assert "A's sub-line" not in groups.charter_digest(conn, p, b)


def test_the_your_group_section_is_absent_for_the_top_group(tmp_path):
    """Conditional by construction: today's single-group runs pay
    nothing, and a reader is never shown a verb it cannot use."""
    from Tooling.agent import phase2_context as ctx
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.section")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    assert ctx._section_your_group(conn, p, top) == []
    assert ctx._section_your_group(conn, p, None) == []
    body = "\n".join(ctx._section_your_group(conn, p, sub))
    assert "ReturnToParent" in body
    assert "charter.md" in body
    assert "not the problem" in body       # overrides the static Ingest line


def test_rev_for_goal_falls_back_within_the_owning_group(tmp_path):
    """The last-resort branch must not serve a sibling group's argument
    to a worker."""
    from Tooling.state import programme
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.revfallback")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    programme.record_pass(conn, p, _prog("top"), {}, [], 0, None,
                          group_id=top)
    programme.record_pass(conn, p, _prog("sub"), {}, [], 0, None,
                          group_id=sub)
    owned = _goal(conn, p, "owned")
    _decision(conn, p, group_id=sub, produced_goal_id=owned)
    kid = _goal(conn, p, "kid")
    _edge(conn, owned, kid)
    conn.commit()
    # No decision carries a batch_id here, so resolution reaches the
    # fallback — which must land in the goal's OWN group.
    assert "# sub" in programme.rev_for_goal(
        conn, p, goal_id=kid)["body"]
    stray = _goal(conn, p, "stray")
    assert "# top" in programme.rev_for_goal(
        conn, p, goal_id=stray)["body"]


# ---------------------------------------------------------------------
# A sub-group's Ingest is a delivery, not a terminal
# ---------------------------------------------------------------------

def _mark(conn, problem, goal_id, group_id):
    conn.execute("UPDATE goals SET is_deliverable = 1 WHERE id = ?",
                 (goal_id,))
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, payload,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'MarkDeliverable', ?, ?, '{}', 't', 't')",
        (problem, group_id, goal_id))


def test_deliverables_are_attributed_to_the_group_that_marked_them(
        tmp_path):
    """Otherwise the human's sign-off list would show every sub-group's
    internal parts as things they are being asked to vouch for."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.deliv")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    mine = _goal(conn, p, "mine", status="proved")
    theirs = _goal(conn, p, "theirs", status="proved")
    _mark(conn, p, mine, top)
    _mark(conn, p, theirs, sub)
    conn.commit()
    assert [r["id"] for r in db.deliverables(conn, problem=p,
                                             group_id=top)] == [mine]
    assert [r["id"] for r in db.deliverables(conn, problem=p,
                                             group_id=sub)] == [theirs]
    assert len(db.deliverables(conn, problem=p)) == 2   # unscoped is all


def test_a_sub_group_ingest_delivers_without_touching_the_terminal(
        tmp_path):
    """Everything the problem-level Ingest does is terminal semantics —
    the human pause, the harvest, the snapshot, the FSM edge. A group
    handing its charter up must touch none of it."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.subingest")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    out = _commit(conn, tmp_path,
                  [S.Decision(kind="Delegate", brief="settle claim A")],
                  p, top)[0]
    sub = int(groups.children(conn, top)[0]["id"])
    brick = _goal(conn, p, "brick", status="proved")
    _mark(conn, p, brick, sub)
    conn.execute("DELETE FROM queue")
    conn.commit()

    assert _verify(conn, S.Decision(kind="Ingest"), p, sub) == ""
    _commit(conn, tmp_path, [S.Decision(kind="Ingest")], p, sub,
            trigger="inject_batch_done")

    assert groups.get(conn, sub)["status"] == "delivered"
    row = conn.execute(
        "SELECT ingested_at, state, ingest_signoff_pending FROM problems"
        " WHERE name = ?", (p,)).fetchone()
    assert row["ingested_at"] is None            # not the problem's exit
    assert row["state"] == "active"
    assert not row["ingest_signoff_pending"]     # no human was paused
    assert conn.execute(
        "SELECT COUNT(*) FROM queue WHERE kind = 'Librarian'"
    ).fetchone()[0] == 0                         # no harvest
    # ...and the parent was woken by the ordinary batch-done relay.
    assert conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()["outcome"] == "success"
    assert (str(top), "Group") in _seats(conn)


def test_a_delivering_sub_group_exits_a_parked_root_without_an_inject_tax(
        tmp_path):
    """For three months no group ever exited marks+Ingest-only: the
    stalled-root gate counted only dispatch kinds as action, so all 13
    delivered groups (measured 2026-08-15) carried a companion Inject
    out the door — claude-era groups paid in spare real bricks, codex's
    settled micro-groups had to invent compliance experiments, one of
    them a mis-aimed attack on the parked root itself. The owner never
    intended the tax (ruling 2026-08-15): a sub-group's Ingest wakes
    the parent, the daemon does not idle."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.taxfree")
    _goal(conn, p, "main", origin="root", status="shelved")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [S.Decision(kind="Delegate", brief="claim A")],
            p, top)
    sub = int(groups.children(conn, top)[0]["id"])
    brick = _goal(conn, p, "brick", status="proved")
    _mark(conn, p, brick, sub)
    conn.commit()
    err = S.verify_decisions([S.Decision(kind="Ingest")], conn,
                             problem=p, group_id=sub, workspace=tmp_path)
    assert err == "", err


def test_mark_and_ingest_in_one_batch_is_a_legal_exit(tmp_path):
    """THE CATCH-22 (grp 422 rev 438, ten rounds, 2026-08-16): an
    anchorless group whose charter was already settled could neither
    mark-only (parked-root gate: the batch delivers nothing) nor
    mark+Ingest (this gate: the same-batch mark was not yet a row). A
    claude-era strategist stated the mechanism verbatim and its judge
    prosecuted it as an unsourced guess — it was true (rev 346). Marks
    listed BEFORE the Ingest now count: commit processes in declared
    order, so they are persisted by the time the Ingest commits."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.markingest")
    _goal(conn, p, "main", origin="root", status="shelved")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief(), reason="cannot prove in-house nor pace through AHEAD")], p, top)
    sub = int(groups.children(conn, top)[0]["id"])
    brick = _goal(conn, p, "brick", status="proved")
    conn.execute("UPDATE goals SET is_deliverable = 0 WHERE id = ?", (brick,))
    conn.commit()
    mark = S.Decision(kind="MarkDeliverable", target_id=brick,
                      reason="the charter's claim")
    ingest = S.Decision(kind="Ingest")
    err = S.verify_decisions([mark, ingest], conn, problem=p,
                             group_id=sub, workspace=tmp_path)
    assert err == "", err
    # Order carries the semantics: an Ingest listed before its mark
    # would commit against a marked set that does not exist yet.
    err = S.verify_decisions([ingest, mark], conn, problem=p,
                             group_id=sub, workspace=tmp_path)
    assert "BEFORE the Ingest" in err


def test_a_top_group_ingest_under_a_parked_root_bounces_off_the_root_gate(
        tmp_path):
    """The exemption is for DELIVERIES only. The top group's Ingest
    still requires the proved root — and because that per-decision gate
    runs before the cross-decision one, the message it gets is the
    accurate one (prove the root), not the stalled-root lecture."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.topbounce")
    _goal(conn, p, "main", origin="root", status="shelved")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    err = S.verify_decisions([S.Decision(kind="Ingest")], conn,
                             problem=p, group_id=top, workspace=tmp_path)
    assert "must be proved" in err
    assert "leaves the daemon idle" not in err


def test_ingest_is_not_a_dispatch_kind():
    """The malignant position for the 2026-08-15 fix: adding Ingest to
    BATCH_DECISION_KINDS instead of the gate-local check would let a
    delivery satisfy the >=1-experiment rule and claim a batch_id. The
    exemption must stay local to the stalled-root gate."""
    assert "Ingest" not in db.BATCH_DECISION_KINDS


def test_a_sub_group_cannot_deliver_a_charter_it_did_not_settle(tmp_path):
    """The same gate the top group gets, one level down: its charter is
    the claim it owes and its anchor is its root goal."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.subgate")
    top = groups.ensure_top_group(conn, p)
    g = _goal(conn, p, "anchor")
    conn.commit()
    S = _S()
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief="own it", target_id=g)],
            p, top)
    anchored = int(groups.children(conn, top)[0]["id"])
    assert "anchor" in _verify(conn, S.Decision(kind="Ingest"), p, anchored)
    conn.execute("UPDATE goals SET status = 'proved' WHERE id = ?", (g,))
    assert _verify(conn, S.Decision(kind="Ingest"), p, anchored) == ""
    # The anchorless shape is gated on its OWN marked deliverables.
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief="prose only")], p, top)
    bare = [int(r["id"]) for r in groups.children(conn, top)][-1]
    assert "MarkDeliverable" in _verify(
        conn, S.Decision(kind="Ingest"), p, bare)


def test_a_mark_is_shareable_across_groups(tmp_path):
    """A mark is not first-come-first-served (owner ruling 2026-08-17).

    `is_deliverable` is problem-global but the Ingest gate counts a
    group's OWN MarkDeliverable rows — so the old blanket "already
    marked" rejection let group A mark a brick and strand group B: B
    could never record that the same proved result settles ITS charter,
    and its exit stayed blocked. Cross-crediting is the AND/OR design
    working (420 closed 425 because an independent route proved its
    certificate). Only a re-mark by the SAME group stays refused — that
    is the FSM §3.2 no-op."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.sharedmark")
    _goal(conn, p, "main", origin="root", status="shelved")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("a"), reason="cannot prove in-house nor pace through AHEAD")], p, top)
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("b"), reason="cannot prove in-house nor pace through AHEAD")], p, top)
    ga, gb = [int(r["id"]) for r in groups.children(conn, top)][:2]
    brick = _goal(conn, p, "shared_brick", status="proved")
    conn.execute("UPDATE goals SET is_deliverable = 0 WHERE id = ?",
                 (brick,))
    conn.commit()
    _mark(conn, p, brick, ga)          # group A claims it first
    conn.commit()
    mark = S.Decision(kind="MarkDeliverable", target_id=brick,
                      reason="the same proved result settles my charter")
    # B records its own mark — and exits on it in the same batch.
    err = S.verify_decisions([mark, S.Decision(kind="Ingest")], conn,
                             problem=p, group_id=gb, workspace=tmp_path)
    assert err == "", err
    # A re-marking its own mark is still the no-op.
    err2 = S.verify_decisions([mark], conn, problem=p, group_id=ga,
                              workspace=tmp_path)
    assert "YOUR group" in err2
    # Committed, the mark is attributed to B and B's gate sees it.
    _commit(conn, tmp_path, [mark], p, gb)
    assert any(int(r["id"]) == brick
               for r in db.deliverables(conn, problem=p, group_id=gb))


# ---------------------------------------------------------------------
# Independent-review regressions (2026-08-02)
# ---------------------------------------------------------------------

def test_a_delegate_only_batch_is_a_real_action(tmp_path):
    """The scenario the design leans on — a fresh problem whose FIRST
    batch delegates a burden instead of working the frozen root — was
    the one the anti-idle gate rejected: it counted only `Inject`.
    (Two Delegates since the 2026-08-19 fan rule: a batch's Delegates
    must leave >=2 active sub-groups; the anti-idle invariant this test
    pins is unchanged.)"""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.delegonly")
    top = groups.ensure_top_group(conn, p)
    _goal(conn, p, "main", origin="root", status="frozen")
    conn.commit()
    S = _S()
    err = S.verify_decisions(
        [S.Decision(kind="Delegate", brief=_proposal_brief(), reason="cannot prove in-house nor pace through AHEAD"),
         S.Decision(kind="Delegate", brief=_proposal_brief("claim B"), reason="the independent sibling case")], conn,
        problem=p, group_id=top)
    assert err == "", err


def test_the_sub_group_actually_receives_its_charter(tmp_path):
    """The Context tells a sub-group its charter is in `charter.md`. It
    has to be there — otherwise the judge reviews against the charter
    while the author works from the problem's goal."""
    from Tooling.agent import phase2_context as ctx
    from Tooling.state import intent as _intent
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.charterfile")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="settle the growth bound")
    conn.commit()
    attempts = tmp_path / "att"
    attempts.mkdir()
    (tmp_path / "Problems" / p).mkdir(parents=True, exist_ok=True)
    ctx.compile_strategist_context(
        conn, problem=p, trigger_kind="routine", attempts_dir=attempts,
        workspace=tmp_path,
        intent=_intent.ProblemIntent(problem=p),
        group_id=sub)
    assert (attempts / "charter.md").exists()
    assert "settle the growth bound" in (
        attempts / "charter.md").read_text(encoding="utf-8")


def test_the_stall_warning_follows_the_group(tmp_path):
    """T4 detects per group; the warning must too, or a stalled
    sub-group is woken, sees nothing, Noops, is rejected, and T4 fires
    again — the P13 livelock, rebuilt."""
    from Tooling.agent import phase2_context as ctx
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.stallsec")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [
        S.Decision(kind="Delegate", brief="busy"),
        S.Decision(kind="Delegate", brief="stuck"),
    ], p, top)
    busy, stuck = (int(r["id"]) for r in groups.children(conn, top))
    g = _goal(conn, p, "live")
    conn.execute("UPDATE goals SET detached = 1 WHERE id = ?", (g,))
    _decision(conn, p, group_id=busy, produced_goal_id=g)
    conn.execute("DELETE FROM queue")
    conn.commit()
    assert ctx._section_stall_warning(conn, p, stuck) != []
    assert ctx._section_stall_warning(conn, p, busy) == []


def test_the_ingest_hint_never_cites_the_problem_root_to_a_sub_group(
        tmp_path):
    """A rooted problem's sub-groups were told on every wake that Ingest
    was unavailable, so they never delivered and their parents waited
    forever."""
    from Tooling.agent import phase2_context as ctx
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.ingesthint")
    top = groups.ensure_top_group(conn, p)
    _goal(conn, p, "main", origin="root", status="attempting")
    bare = groups.open_group(conn, problem=p, parent_group_id=top,
                             charter="prose only")
    anchor = _goal(conn, p, "anchor", status="attempting")
    anchored = groups.open_group(conn, problem=p, parent_group_id=top,
                                 charter="own it", anchor_goal_id=anchor)
    conn.commit()
    assert ctx._section_ingest_gate(conn, p, top) != []      # root not proved
    assert ctx._section_ingest_gate(conn, p, bare) == []     # not its gate
    hint = "\n".join(ctx._section_ingest_gate(conn, p, anchored))
    assert f"g{anchor}" in hint and "root" not in hint


def test_sibling_commits_do_not_stamp_each_others_rows(tmp_path):
    """group_id is written by each INSERT. A post-pass range UPDATE over
    'rows newer than my snapshot' would cross-stamp the moment two
    groups of one problem commit concurrently — the concurrency the
    per-group seat exists to buy."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.stamprace")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    b = groups.open_group(conn, problem=p, parent_group_id=top, charter="B")
    conn.commit()
    S = _S()
    # Interleave: B's rows land between A's snapshot and A's post-pass.
    before = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM strategist_decisions"
    ).fetchone()[0]
    _commit(conn, tmp_path, [S.Decision(kind="Noop", reason="b")], p, b)
    _commit(conn, tmp_path, [S.Decision(kind="Noop", reason="a")], p, a)
    rows = conn.execute(
        "SELECT group_id, reason FROM strategist_decisions"
        " WHERE id > ? ORDER BY id", (before,)).fetchall()
    assert [(int(r["group_id"]), r["reason"]) for r in rows] == [
        (b, "b"), (a, "a")]


def test_a_group_keyed_queue_row_resolves_to_its_own_problem(tmp_path):
    """Read as a goal id it would name whatever problem THAT goal
    belongs to, scoping an infra retry to an unrelated problem."""
    from Tooling.core.dispatcher import _problem_of_target
    conn = _conn(tmp_path)
    other = _problem(conn, "Test.other")
    _goal(conn, other, "decoy")            # takes goal id 1
    p = _problem(conn, "Test.mine")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    assert _problem_of_target(conn, str(top), "Group") == p
    assert _problem_of_target(conn, "99999", "Group") is None


def test_one_groups_commit_does_not_acknowledge_anothers_batch(tmp_path):
    """The ack ratchet is per group. Shared, a sibling's commit hides a
    completed batch and the advance-forcing wake is simply skipped."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.ack")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(conn, problem=p, parent_group_id=top, charter="A")
    b = groups.open_group(conn, problem=p, parent_group_id=top, charter="B")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, batch_id, outcome,"
        " payload, created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Inject', ?, 'bA', 'success', '{}',"
        " '2030-01-01', '2030-01-01')", (p, a))
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [S.Decision(kind="Noop", reason="x")], p, b)
    assert db.unacknowledged_inject_batches(conn, p, a) == ["bA"]


def test_the_parent_sees_what_came_back(tmp_path):
    """The delivered bricks and the post-mortem reached the Strategist
    only as a daemon log line — the parent was woken and could not see
    which bricks it may now cite, nor why a charter came back."""
    from Tooling.agent import phase2_context as ctx
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.material")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [
        S.Decision(kind="Delegate", brief="claim A"),
        S.Decision(kind="Delegate", brief="claim B"),
    ], p, top)
    good, bad = (int(r["id"]) for r in groups.children(conn, top))
    brick = _goal(conn, p, "brick", status="proved")
    _mark(conn, p, brick, good)
    conn.execute("DELETE FROM queue")
    conn.commit()
    _commit(conn, tmp_path, [S.Decision(kind="Ingest")], p, good,
            trigger="inject_batch_done")
    _commit(conn, tmp_path,
            [S.Decision(kind="ReturnToParent",
                        reason="the valuation step is circular",
                        payload={"flavour": "amend",
                                 "proposed_charter": "the weaker bound"})],
            p, bad, trigger="inject_batch_done")

    body = "\n".join(ctx._section_inject_batch_outcomes(
        conn, p, group_id=top))
    assert "`brick`" in body                    # citable now
    assert "amend" in body
    assert "valuation step is circular" in body
    assert "the weaker bound" in body


def test_a_delivered_groups_programme_rides_up_as_a_companion(tmp_path):
    """RS-D — bricks are the WHAT; the child's final passed Programme
    rev is the WHY, and the parent gets it whole as a lazy companion
    (`PROGRAMME_G<id>.md`), never truncated inline."""
    from Tooling.agent import phase2_context as ctx
    from Tooling.state import programme
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.upward")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [S.Decision(kind="Delegate", brief="claim A")],
            p, top)
    child = int(groups.children(conn, top)[0]["id"])
    body_text = ("## Focus\nthe claim\n\n## Proof\nbecause the lattice"
                 " argument closes it\n\n## Roadmap\n1. done\n")
    programme.record_pass(conn, p, body_text, {}, [], 1, None,
                          group_id=child)
    brick = _goal(conn, p, "brick", status="proved")
    _mark(conn, p, brick, child)
    conn.execute("DELETE FROM queue")
    conn.commit()
    _commit(conn, tmp_path, [S.Decision(kind="Ingest")], p, child,
            trigger="inject_batch_done")

    attempts = tmp_path / ".attempts" / "wake"
    attempts.mkdir(parents=True)
    body = "\n".join(ctx._section_inject_batch_outcomes(
        conn, p, group_id=top, attempts_dir=attempts))
    name = f"PROGRAMME_G{child}.md"
    assert name in body                          # pointer line inline
    companion = (attempts / name).read_text(encoding="utf-8")
    assert "the lattice argument closes it" in companion
    # Worker-facing renders pass no attempts_dir — no pointer, no file.
    bare = "\n".join(ctx._section_inject_batch_outcomes(
        conn, p, group_id=top))
    assert name not in bare


def test_a_waiting_parents_routine_clock_is_frozen(tmp_path):
    """Operator ruling 2026-08-03: a group with a live child group is
    WAITING — it delegated the work, so a routine wake there audits
    nothing. Its periodic clock must not come due while any child is
    active; the child's own clock is unaffected."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.freeze")
    top = groups.ensure_top_group(conn, p)
    child = groups.open_group(conn, problem=p, parent_group_id=top,
                              charter="C")
    conn.commit()
    due = {int(r["id"]) for r in db.groups_needing_t1(
        conn, max_age_sec=0.0)}
    assert top not in due          # waiting parent: frozen
    assert child in due            # working child: its own cadence


def test_child_settling_restarts_the_parents_cadence(tmp_path):
    """The freeze releases through the one door: when the last child
    reaches a terminal status, the parent's `last_routine_at` restarts —
    the waiting hours never read as overdue, so no routine fires on top
    of the batch-done relay the settling already enqueues."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.thaw")
    top = groups.ensure_top_group(conn, p)
    child = groups.open_group(conn, problem=p, parent_group_id=top,
                              charter="C")
    conn.execute("UPDATE groups SET last_routine_at = '2020-01-01'"
                 " WHERE id = ?", (top,))
    conn.commit()
    groups.set_status(conn, child, "delivered", event="group_delivered")
    conn.commit()
    due = {int(r["id"]) for r in db.groups_needing_t1(
        conn, max_age_sec=3600.0)}
    assert top not in due          # cadence restarted, not overdue
    ts = conn.execute("SELECT last_routine_at FROM groups WHERE id = ?",
                      (top,)).fetchone()[0]
    assert ts > "2020-01-01"


def test_promoting_a_parked_goal_to_an_anchor_is_a_declared_edge(tmp_path):
    """"This goal keeps failing — give it a group" is the documented
    rescue entry point, and the states it starts from are the parked
    ones. Under CI's strict transitions an undeclared edge raises."""
    import os
    from Tooling.state import transitions as _t
    assert ("shelved", "attempting") in _t.GOAL_EDGES
    assert ("frozen", "attempting") in _t.GOAL_EDGES
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.promote")
    top = groups.ensure_top_group(conn, p)
    g = _goal(conn, p, "parked", status="shelved")
    conn.commit()
    old = os.environ.get("ASTERISM_STRICT_TRANSITIONS")
    os.environ["ASTERISM_STRICT_TRANSITIONS"] = "1"
    try:
        _commit(conn, tmp_path,
                [_S().Decision(kind="Delegate", brief="own it",
                               target_id=g)], p, top)
    finally:
        if old is None:
            os.environ.pop("ASTERISM_STRICT_TRANSITIONS", None)
        else:
            os.environ["ASTERISM_STRICT_TRANSITIONS"] = old
    assert db.get_goal(conn, g)["status"] == "attempting"


def test_the_reconciler_routes_a_review_to_the_same_group_as_the_cascade(
        tmp_path):
    """Two routes to two different homes for one event is the shape this
    file has paid for three times."""
    from Tooling.core.dispatcher import reconcile_stuck_states
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.route")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    g = _goal(conn, p, "mine", status="pending_strategist_review")
    conn.execute("UPDATE goals SET detached = 1 WHERE id = ?", (g,))
    _decision(conn, p, group_id=sub, produced_goal_id=g)
    conn.commit()
    reconcile_stuck_states(conn, running=set())
    assert (str(sub), "Group") in _seats(conn)
    assert (str(top), "Group") not in _seats(conn)


# ---------------------------------------------------------------------
# CloseGroup, and the one return that cannot wait for its batch
# ---------------------------------------------------------------------

def test_a_refutation_wakes_the_parent_without_waiting_for_the_batch(
        tmp_path):
    """`refuted` means a step of the PARENT's Proof is kernel-false. Its
    siblings from the same batch keep that batch open, so the ordinary
    relay would leave the parent asleep for up to a routine interval
    while they work on an invalidated premise."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.fastwake")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [
        S.Decision(kind="Delegate", brief="claim A"),
        S.Decision(kind="Delegate", brief="claim B"),
    ], p, top)
    a, b = (int(r["id"]) for r in groups.children(conn, top))
    neg = _goal(conn, p, "neg", status="proved")
    conn.execute("DELETE FROM queue")
    conn.commit()

    # B is still active, so the batch is NOT complete.
    _commit(conn, tmp_path,
            [S.Decision(kind="ReturnToParent", reason="counterexample",
                        target_id=neg,
                        payload={"flavour": "refuted"})],
            p, a, trigger="inject_batch_done")
    assert groups.get(conn, b)["status"] == "active"
    assert (str(top), "Group") in _seats(conn)


@pytest.mark.parametrize("flavour", ["amend", "exhausted"])
def test_a_soft_return_still_rides_the_batch(tmp_path, flavour):
    """"This line did not work" is exactly what the batch report is for
    — only a refutation earns the interrupt."""
    conn = _conn(tmp_path)
    p = _problem(conn, f"Test.soft{flavour}")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [
        S.Decision(kind="Delegate", brief="claim A"),
        S.Decision(kind="Delegate", brief="claim B"),
    ], p, top)
    a, _b = (int(r["id"]) for r in groups.children(conn, top))
    conn.execute("DELETE FROM queue")
    conn.commit()
    payload = {"flavour": flavour}
    if flavour == "amend":
        payload["proposed_charter"] = "a weaker claim A"
    _commit(conn, tmp_path,
            [S.Decision(kind="ReturnToParent", reason="died at step 3",
                        payload=payload)],
            p, a, trigger="inject_batch_done")
    assert _seats(conn) == set()


def test_a_parent_can_retire_a_child_whose_line_it_no_longer_needs(
        tmp_path):
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.close")
    top = groups.ensure_top_group(conn, p)
    g = _goal(conn, p, "anchor")
    conn.commit()
    S = _S()
    out = _commit(conn, tmp_path,
                  [S.Decision(kind="Delegate", brief="own it",
                              target_id=g)], p, top)[0]
    kid = int(groups.children(conn, top)[0]["id"])
    conn.execute("DELETE FROM queue")
    conn.commit()

    _commit(conn, tmp_path, [
        S.Decision(kind="CloseGroup",
                   reason="rev 4 routes around this entirely",
                   payload={"target_group_id": kid})], p, top)

    assert groups.get(conn, kid)["status"] == "closed"
    assert conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()["outcome"] == "failed:closed"
    assert db.get_goal(conn, g)["status"] == "shelved"
    assert db.has_active_inflight_inject(conn, p) is False


def test_closing_reaches_only_your_own_children(tmp_path):
    """A grandchild belongs to ITS parent; reaching past one level would
    let a group cancel work it never commissioned and cannot judge."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.closescope")
    top = groups.ensure_top_group(conn, p)
    mid = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="A")
    leaf = groups.open_group(conn, problem=p, parent_group_id=mid,
                             charter="A1")
    conn.commit()
    S = _S()
    d = S.Decision(kind="CloseGroup", reason="r",
                   payload={"target_group_id": leaf})
    assert "not yours to close" in _verify(conn, d, p, top)
    assert _verify(conn, d, p, mid) == ""
    # ...and a group already finished has nothing to close.
    groups.set_status(conn, leaf, "returned")
    assert "already reached" in _verify(conn, d, p, mid)


def test_the_parent_can_see_what_it_is_waiting_on(tmp_path):
    """`CloseGroup` needs a group id to name, and the parent had no
    surface listing its live children at all — the batch scoreboard only
    shows finished work. The section that carries the verb carries the
    list, and both disappear when there is nothing to close."""
    from Tooling.agent import phase2_context as ctx
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.inflight")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    assert ctx._section_groups_in_flight(conn, p, top) == []
    S = _S()
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief="settle the p-adic bound")],
            p, top)
    kid = int(groups.children(conn, top)[0]["id"])
    body = "\n".join(ctx._section_groups_in_flight(conn, p, top))
    assert f"group {kid}" in body
    assert "settle the p-adic bound" in body
    assert "CloseGroup" in body
    # A finished child drops off, and with the last one the section goes.
    groups.set_status(conn, kid, "delivered")
    assert ctx._section_groups_in_flight(conn, p, top) == []
    # A childless sub-group never sees the verb either.
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="x")
    assert ctx._section_groups_in_flight(conn, p, sub) == []


def test_retiring_work_is_not_progress(tmp_path):
    """`CloseGroup` is deliberately NOT a dispatch kind: retiring a
    child neither satisfies the parked-root gate nor rides the batch
    cycle, so a stuck parent cannot close its child and call that an
    advance. (The per-batch ≥1-experiment quota retired 2026-08-16 —
    the state-based gates carry the dead-air invariant — but the
    kind-classification it relied on stays pinned.)"""
    from Tooling.state import db
    S = _S()
    assert "CloseGroup" not in db.BATCH_DECISION_KINDS
    assert "CloseGroup" not in S._PACKAGE_EXEMPT_KINDS


# ---------------------------------------------------------------------
# v35 migration
# ---------------------------------------------------------------------

#: The v34 shape of the three tables v35 rebuilds — decision_kind without
#: the two new kinds, target_kind without 'Group'.
_V34_TABLES = """
-- `groups` goes FIRST: dropping it runs the ON DELETE SET NULL action on
-- strategist_decisions.group_id, which needs that table to still exist.
DROP TABLE IF EXISTS groups;
DROP TABLE IF EXISTS strategist_decisions;
DROP TABLE IF EXISTS queue;
DROP TABLE IF EXISTS pipelines;
DROP TABLE IF EXISTS programme_revisions;
CREATE TABLE programme_revisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    problem    TEXT NOT NULL REFERENCES problems(name),
    rev        INTEGER NOT NULL,
    body       TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('passed', 'rejected')),
    verdict    TEXT,
    dialogue   TEXT,
    rounds     INTEGER NOT NULL DEFAULT 0,
    batch_id   TEXT,
    created_at TEXT NOT NULL,
    discard_reason TEXT NULL
);
CREATE UNIQUE INDEX ux_programme_passed_rev
    ON programme_revisions(problem, rev) WHERE status = 'passed';
CREATE TABLE strategist_decisions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    problem             TEXT NOT NULL REFERENCES problems(name),
    triggered_at_tick   INTEGER NOT NULL,
    trigger_kind        TEXT NOT NULL
                            CHECK(trigger_kind IN
                                  ('first_launch','pending_review','routine',
                                   'inject_batch_done','audit')),
    decision_kind       TEXT NOT NULL
                            CHECK(decision_kind IN
                                  ('Inject','ConfirmShelve','Reopen',
                                   'EmitDirective','InitializeDefs',
                                   'RequestUserAmend','Noop','MarkDeliverable',
                                   'Ingest','FetchPaper','AttemptDisproof')),
    target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
    brief               TEXT NULL DEFAULT NULL,
    reason              TEXT NULL DEFAULT NULL,
    payload             TEXT NOT NULL DEFAULT '{}',
    batch_id            TEXT NULL DEFAULT NULL,
    produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id),
    produced_strategy_id INTEGER NULL DEFAULT NULL REFERENCES strategies(id),
    outcome             TEXT NULL DEFAULT NULL,
    outcome_detail      TEXT NULL DEFAULT NULL,
    produced_kind       TEXT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE TABLE queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL
                    CHECK(kind IN ('Builder','Backward','Verify',
                                   'Strategist','Forward','Librarian',
                                   'Scholar','Formalizer')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL DEFAULT 'Goal'
                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
    priority    INTEGER NOT NULL DEFAULT 0,
    decision_id INTEGER NULL DEFAULT NULL REFERENCES strategist_decisions(id),
    problem     TEXT NOT NULL DEFAULT '',
    payload     TEXT,
    owner_pid   INTEGER,
    leased_at   TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_queue_priority ON queue(priority DESC, id ASC);
CREATE TABLE pipelines (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL
                    CHECK(kind IN ('Builder','Backward','Verify',
                                   'Strategist','Forward','Librarian',
                                   'Scholar','Formalizer')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL
                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    outcome     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NOT NULL
);
CREATE INDEX idx_pipelines_status ON pipelines(status);
"""


def _v34_db(tmp_path):
    """A DB that looks like it was written before v35."""
    conn = _conn(tmp_path, "v34.db")
    conn.executescript(_V34_TABLES)
    conn.execute("PRAGMA user_version = 34")
    for name in ("Test.a", "Test.b"):
        _problem(conn, name)
    conn.execute(
        "UPDATE problems SET last_routine_at = 'R1' WHERE name = 'Test.a'")
    for name in ("Test.a", "Test.b"):
        # Raw insert: the v34 table has no group_id column yet.
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, payload, created_at, updated_at)"
            " VALUES (?, 0, 'routine', 'Inject', '{}', 't', 't')", (name,))
    conn.execute(
        "INSERT INTO queue (kind, target_id, target_kind, problem, created_at)"
        " VALUES ('Strategist', 'Test.a', 'Problem', 'Test.a', 't')")
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('p1', 'Strategist', 'Test.a', 'Problem', 'succeeded',"
        " 'ok', 't', 't')")
    conn.execute(
        "INSERT INTO programme_revisions (problem, rev, body, status,"
        " rounds, created_at) VALUES ('Test.a', 1, '# T', 'passed', 0, 't')")
    conn.commit()
    return conn


def test_v35_migrates_a_v34_db_without_losing_rows(tmp_path):
    conn = _v34_db(tmp_path)
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("strategist_decisions", "queue", "pipelines",
                        "programme_revisions")}
    db_migrations.apply(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 46
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in before}
    assert before == after
    # The pre-existing index survived the rebuild.
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index'"
        " AND name='idx_queue_priority'").fetchone() is not None


def test_init_schema_upgrades_a_v34_db_in_place(tmp_path):
    """The path production actually takes, and the one every other
    migration test here missed by calling `db_migrations.apply` directly.

    `init_schema` runs SCHEMA *before* the migration chain. On an
    existing DB `CREATE TABLE IF NOT EXISTS strategist_decisions` is a
    no-op, so any SCHEMA statement naming a column that only a migration
    adds kills the whole script — which is what an index on
    `strategist_decisions(group_id)` in SCHEMA did to the live v34 DB
    (2026-08-02). Indexes on a table SCHEMA itself creates are fine; that
    is the distinction this pins.
    """
    conn = _v34_db(tmp_path)
    db.init_schema(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 46
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(strategist_decisions)")}
    assert {"group_id", "produced_group_id"} <= cols
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index'"
        " AND name='idx_sd_group'").fetchone() is not None
    assert groups.top_group(conn, "Test.a") is not None


def test_v35_backfills_one_top_group_per_problem_with_its_clocks(tmp_path):
    conn = _v34_db(tmp_path)
    db_migrations.apply(conn)
    assert conn.execute(
        "SELECT COUNT(*) FROM groups WHERE parent_group_id IS NULL"
    ).fetchone()[0] == 2
    assert groups.top_group(conn, "Test.a")["last_routine_at"] == "R1"
    # Every pre-v35 row now belongs to its OWN problem's top group.
    assert conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions d JOIN groups g"
        "  ON g.id = d.group_id WHERE g.problem != d.problem"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions WHERE group_id IS NULL"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM programme_revisions WHERE group_id IS NULL"
    ).fetchone()[0] == 0


def test_v35_widens_the_three_checks(tmp_path):
    conn = _v34_db(tmp_path)
    db_migrations.apply(conn)
    top = groups.top_group(conn, "Test.a")["id"]
    sub = groups.open_group(conn, problem="Test.a", parent_group_id=top,
                            charter="claim A")
    for kind in ("Delegate", "ReturnToParent"):
        _decision(conn, "Test.a", group_id=sub, kind=kind)
    conn.execute(
        "INSERT INTO queue (kind, target_id, target_kind, problem,"
        " created_at) VALUES ('Strategist', ?, 'Group', 'Test.a', 't')",
        (str(sub),))
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('p2', 'Strategist', ?, 'Group', 'succeeded', 'ok', 't', 't')",
        (str(sub),))
    conn.commit()
    # The inserts above only prove "no IntegrityError was raised" — which is
    # also what a CHECK that was DROPPED rather than WIDENED would give us.
    # Assert the rows landed, then assert the constraint is still a
    # constraint (widen-not-drop, mirroring test_v19/test_v20).
    assert {r[0] for r in conn.execute(
        "SELECT decision_kind FROM strategist_decisions WHERE group_id = ?",
        (sub,))} == {"Delegate", "ReturnToParent"}
    assert conn.execute(
        "SELECT COUNT(*) FROM queue WHERE target_kind = 'Group'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM pipelines WHERE target_kind = 'Group'"
    ).fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        _decision(conn, "Test.a", group_id=sub, kind="NotADecisionKind")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO queue (kind, target_id, target_kind, problem,"
            " created_at) VALUES ('Strategist', '1', 'Herd', 'Test.a', 't')")
    conn.rollback()


def test_v35_rekeys_the_programme_chain_index_to_the_group(tmp_path):
    """Each group owns its own rev numbering from 1, so two groups may
    both hold a passed rev 1 — which the problem-keyed v31 index forbade."""
    conn = _v34_db(tmp_path)
    db_migrations.apply(conn)
    top = groups.top_group(conn, "Test.a")["id"]
    sub = groups.open_group(conn, problem="Test.a", parent_group_id=top,
                            charter="claim A")
    conn.execute(
        "INSERT INTO programme_revisions (problem, rev, body, status,"
        " rounds, created_at, group_id)"
        " VALUES ('Test.a', 1, '# sub', 'passed', 0, 't', ?)", (sub,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO programme_revisions (problem, rev, body, status,"
            " rounds, created_at, group_id)"
            " VALUES ('Test.a', 1, '# dup', 'passed', 0, 't', ?)", (sub,))


def test_v35_is_idempotent(tmp_path):
    conn = _v34_db(tmp_path)
    db_migrations.apply(conn)
    snapshot = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("strategist_decisions", "queue", "pipelines",
                          "programme_revisions", "groups")}
    db_migrations.apply(conn)
    assert snapshot == {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in snapshot}


def test_v35_refuses_to_guess_when_the_target_kind_check_drifted(tmp_path):
    """A widening that cannot find what it expects must fail loud rather
    than rebuild a table from a guessed shape (CLAUDE.md: rather fail
    loudly than route around)."""
    conn = _v34_db(tmp_path)
    conn.executescript(
        "DROP TABLE queue;"
        " CREATE TABLE queue (id INTEGER PRIMARY KEY, kind TEXT,"
        " target_id TEXT, target_kind TEXT CHECK(target_kind IN ('Goal')),"
        " problem TEXT, created_at TEXT);")
    with pytest.raises(RuntimeError, match="cannot widen"):
        db_migrations.apply(conn)


# ---------------------------------------------------------------------
# FSM (v35 follow-up) — declared edges, same law as the other entities
# ---------------------------------------------------------------------

def test_group_edges_are_exactly_the_three_terminal_verbs():
    """`active` is the only non-terminal state and it is left exactly once.

    Pinned as a set, not a count: a fourth edge is a design change that
    must be argued, and re-entry into `active` is the one shape the table
    exists to forbid — `reconcile_settled_inject_outcomes` reads every
    non-'active' status as settled and the terminal write wakes the
    parent, so a resurrected group runs on behind a parent already told
    it finished."""
    from Tooling.state import transitions
    assert transitions.GROUP_EDGES == frozenset({
        ("active", "delivered"),
        ("active", "returned"),
        ("active", "closed"),
    })
    assert not [e for e in transitions.GROUP_EDGES if e[1] == "active"]


@pytest.mark.parametrize("first,second", [
    ("delivered", "closed"),    # parent retires a group that already left
    ("returned", "delivered"),
    ("closed", "returned"),
])
def test_a_terminal_group_cannot_move_again(tmp_path, monkeypatch, first,
                                            second):
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")
    from Tooling.state import transitions
    conn = _conn(tmp_path)
    p = _problem(conn)
    top = groups.ensure_top_group(conn, p)
    gid = groups.open_group(conn, problem=p, parent_group_id=top, charter="c")
    groups.set_status(conn, gid, first, event=f"group_{first}")
    with pytest.raises(transitions.IllegalTransition):
        groups.set_status(conn, gid, second, event=f"group_{second}")
    assert groups.get(conn, gid)["status"] == first


def test_group_resurrection_is_rejected(tmp_path, monkeypatch):
    """The shape with a live victim: `delivered` already filled the
    parent's `Delegate` outcome and woke it, so re-activating the child
    leaves the parent believing the burden is settled."""
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")
    from Tooling.state import transitions
    conn = _conn(tmp_path)
    p = _problem(conn)
    top = groups.ensure_top_group(conn, p)
    gid = groups.open_group(conn, problem=p, parent_group_id=top, charter="c")
    groups.set_status(conn, gid, "delivered", event="group_delivered")
    with pytest.raises(transitions.IllegalTransition):
        groups.set_status(conn, gid, "active", event="group_delivered")


def test_group_status_write_stays_on_the_one_door(tmp_path):
    """No module outside the store may UPDATE groups.status — the check
    lives in `set_status`, so a second writer is a silent bypass of the
    FSM (the reason goals/strategies grew a chokepoint lint)."""
    import re as _re
    from pathlib import Path as _P
    root = _P(__file__).resolve().parent.parent / "Tooling"
    pat = _re.compile(r"UPDATE\s+groups\s+SET[^\"']*\bstatus\s*=",
                      _re.I | _re.S)
    offenders = [
        str(f.relative_to(root)) for f in root.rglob("*.py")
        if f.name != "groups.py" and pat.search(f.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"groups.status written outside the store: {offenders}"


def test_stacked_charter_headings_are_stamped_with_their_group(tmp_path):
    """Charters are agent prose sharing a template: two charters in one
    charter.md both said `## The claim to settle` (measured 2026-08-15),
    and a section ask can only ever name one of them. The stacked
    context — ancestors and returned charters — gets `[group N]`
    stamped into its headings; this group's OWN charter keeps its
    headings verbatim, because those are the natural addresses. A `#`
    inside a code fence is code and stays untouched."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.charterstamp")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(
        conn, problem=p, parent_group_id=top,
        charter="## The claim to settle\nA's claim\n"
                "```\n# not a heading\n```")
    b = groups.open_group(
        conn, problem=p, parent_group_id=a,
        charter="## The claim to settle\nB's claim")
    conn.commit()
    txt = groups.charter_digest(conn, p, b)
    assert "## The claim to settle\nB's claim" in txt, "own charter verbatim"
    assert f"## [group {a}] The claim to settle" in txt
    assert "# not a heading" in txt
    assert f"# [group {a}] not a heading" not in txt


def test_stacked_ancestors_carry_claims_not_delegation_prose(tmp_path):
    """2026-08-18 (context diet #3): a depth-10 chain stacked every
    ancestor's full `## Why a project` + `## Inheritance` into
    charter.md — 37.4KB against a 1.5KB own charter, the slice's
    second-largest inspect-truncation source. Ancestors keep their
    CLAIM (wherever its heading is — dropping is by section NAME, not
    position); the delegation prose is the delegation's business. The
    group's OWN charter stays verbatim."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.charterdiet")
    top = groups.ensure_top_group(conn, p)
    a = groups.open_group(
        conn, problem=p, parent_group_id=top,
        charter="# Charter\n\nA's claim to settle\n\n"
                "## Why a project\nbecause the AHEAD cannot carry it\n\n"
                "## Inheritance\ncite brick_x\n\n"
                "## The exit\nkernel-check the bound")
    b = groups.open_group(
        conn, problem=p, parent_group_id=a,
        charter="B's claim\n\n## Why a project\nB's own reasons\n\n"
                "## Inheritance\ncite brick_y")
    conn.commit()
    txt = groups.charter_digest(conn, p, b)
    # own charter verbatim — Why/Inheritance included
    assert "B's own reasons" in txt and "cite brick_y" in txt
    # ancestor keeps its claim and its non-delegation sections...
    assert "A's claim to settle" in txt
    assert "kernel-check the bound" in txt
    # ...but not the delegation prose
    assert "because the AHEAD cannot carry it" not in txt
    assert "cite brick_x" not in txt
    assert "CLAIM only" in txt


def test_a_delivery_always_reaches_a_group_that_can_act_on_it(tmp_path):
    """The wake went to the group that AUTHORED the Delegate, and the
    dispatcher DROPS a Strategist row whose group is terminal (correctly
    — a delivered group must not run another batch). So a child
    delivering into a parent that already left was not delayed, it was
    deleted: the delivery reached nobody and its bricks were owned by
    nobody. Two mechanisms each right, blinding each other.

    Reachable today: nothing stops a parent from Closing/Ingesting while
    a child is active, and union_closed had two such pairs live when an
    independent verifier found this (2026-08-16). Pre-08-15 the child's
    exit batch was forced to carry an Inject, so work stayed dispatched
    and the loss was invisible."""
    from Tooling.core import dispatcher as _disp
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.orphanwake")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path, [S.Decision(kind="Delegate",
                                        brief=_proposal_brief("mid"),
                                        reason="cannot prove in-house nor pace through AHEAD")], p, top)
    mid = int(groups.children(conn, top)[0]["id"])
    _commit(conn, tmp_path, [S.Decision(kind="Delegate",
                                        brief=_proposal_brief("kid"),
                                        reason="cannot prove in-house nor pace through AHEAD")], p, mid)
    kid = int(groups.children(conn, mid)[0]["id"])

    # A parent that is ALREADY terminal with a live child. The cascade
    # (below) stops this state being created from here on, but every
    # tree built before it exists in it — union_closed had two such
    # pairs live the day both were written — so the relay must still
    # find a live addressee on its own.
    conn.execute("UPDATE groups SET status = 'delivered' WHERE id = ?",
                 (mid,))
    conn.commit()

    conn.execute("DELETE FROM queue")
    brick_k = _goal(conn, p, "kid_brick", status="proved")
    _mark(conn, p, brick_k, kid)
    conn.commit()
    _commit(conn, tmp_path, [S.Decision(kind="Ingest")], p, kid,
            trigger="inject_batch_done")

    queued = [(str(r["target_id"]), str(r["target_kind"])) for r in
              conn.execute("SELECT target_id, target_kind FROM queue"
                           " WHERE kind = 'Strategist'")]
    live = [q for q in queued
            if not _disp._row_is_stale(conn, q[0], "Strategist",
                                                  q[1])]
    assert live, (
        f"the delivery woke nobody: queued={queued}, all dropped as stale")
    # …and specifically it was REDIRECTED: the Delegate row that opened
    # `kid` names `mid`, which is terminal, so addressing it verbatim is
    # what produced the dropped wake.
    assert int(conn.execute(
        "SELECT group_id FROM strategist_decisions WHERE produced_group_id=?",
        (kid,)).fetchone()[0]) == mid
    assert (str(top), "Group") in live


def test_retiring_a_charter_retires_the_work_it_delegated(tmp_path):
    """Goals have cascaded downward since the beginning; groups never
    did, and `_commit_close_group` retired exactly ONE level — so a
    grandchild kept working a charter its grandparent had withdrawn,
    with nothing anywhere to tell it.

    Measured on union_closed 2026-08-16: group 420 closed 425 because
    the certificate it wanted was "now kernel-proved by the independent
    s24581 route"; 425's child 427 never heard, and three hours later
    opened five sub-projects to binary-split a 2^21 mask space, which
    opened their own. Twenty-two of the next thirty-eight bricks served
    the withdrawn charter."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.cascade")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("mid"), reason="cannot prove in-house nor pace through AHEAD")], p, top)
    mid = int(groups.children(conn, top)[0]["id"])
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("kid"), reason="cannot prove in-house nor pace through AHEAD")], p, mid)
    kid = int(groups.children(conn, mid)[0]["id"])
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("grandkid"), reason="cannot prove in-house nor pace through AHEAD")],
            p, kid)
    grand = int(groups.children(conn, kid)[0]["id"])

    _commit(conn, tmp_path,
            [S.Decision(kind="CloseGroup", reason="another route settled it",
                        payload={"target_group_id": mid})], p, top)

    for g in (mid, kid, grand):
        assert groups.get(conn, g)["status"] == "closed", (
            f"group {g} kept working a charter its ancestor withdrew")
    # The opening `Delegate` of every retired group settles, or a
    # NULL outcome would suppress the stall detector forever.
    unsettled = conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions"
        " WHERE decision_kind = 'Delegate' AND outcome IS NULL"
        " AND produced_group_id IN (?, ?, ?)", (mid, kid, grand)).fetchone()[0]
    assert unsettled == 0


def test_a_cascade_closed_rescue_group_parks_its_anchor(tmp_path):
    """The direct `CloseGroup` shelved its target's anchor; the ancestor
    cascade closed descendants WITHOUT touching theirs — an `attempting`
    anchor stayed parked-alive under a closed group, never dispatched
    again (BFS skips `attempting`) and with no shelve record for
    citation-revival (acceptance pass, 2026-08-17). The parking lives in
    `set_status` now, so every closing path — direct, cascade, startup
    sweep — goes through the one door."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.cascade3")
    top = groups.ensure_top_group(conn, p)
    anchor = _goal(conn, p, "rescue_target", status="attempting")
    mid = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="mid line")
    kid = groups.open_group(conn, problem=p, parent_group_id=mid,
                            charter="rescue it", anchor_goal_id=anchor)
    conn.commit()
    groups.set_status(conn, mid, "closed", event="group_closed")
    conn.commit()
    assert groups.get(conn, kid)["status"] == "closed"
    row = conn.execute("SELECT status FROM goals WHERE id = ?",
                       (anchor,)).fetchone()
    assert str(row["status"]) == "shelved", (
        "the cascade left the anchor parked-alive under a closed group")


def test_a_delivering_group_takes_its_live_sub_projects_with_it(tmp_path):
    """Same law, the other verb: a group that has delivered has no use
    for bricks its children have not landed yet, and no consumer for
    them either."""
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.cascade2")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("mid"), reason="cannot prove in-house nor pace through AHEAD")], p, top)
    mid = int(groups.children(conn, top)[0]["id"])
    _commit(conn, tmp_path,
            [S.Decision(kind="Delegate", brief=_proposal_brief("kid"), reason="cannot prove in-house nor pace through AHEAD")], p, mid)
    kid = int(groups.children(conn, mid)[0]["id"])
    brick = _goal(conn, p, "mid_brick", status="proved")
    _mark(conn, p, brick, mid)
    conn.commit()
    _commit(conn, tmp_path, [S.Decision(kind="Ingest")], p, mid,
            trigger="inject_batch_done")
    assert groups.get(conn, mid)["status"] == "delivered"
    assert groups.get(conn, kid)["status"] == "closed"
