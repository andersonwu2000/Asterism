from __future__ import annotations

import sqlite3

from .core import now, scope_sql
from .goals import (
    propagate_inject_outcome_from_goal,
    propagate_inject_outcome_from_strategy,
)
from .pipelines import is_in_queue
from .problems import _BATCH_KINDS_SQL, propagate_inject_outcome_from_group
from .queue import enqueue


# ---------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------

def insert_strategy(conn: sqlite3.Connection, *, goal_id: int,
                    lean_path: str, created_by: str,
                    proposal_md: str = "", scratch_path: str = "") -> int:
    """Insert a new strategy. `lean_path` is the parent goal's target;
    `scratch_path` is this strategy's standalone patch module path.
    `scratch_path` may be left empty here and UPDATE'd via
    `update_strategy_scratch_path` once the sid is known and paths
    derived from it have been computed."""
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, ?, ?, 'proposed', ?, ?, ?)",
        (goal_id, lean_path, scratch_path, proposal_md, created_by, now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_strategy_scratch_path(conn: sqlite3.Connection, strategy_id: int,
                                 scratch_path: str) -> None:
    conn.execute(
        "UPDATE strategies SET scratch_path = ? WHERE id = ?",
        (scratch_path, strategy_id),
    )
    conn.commit()


def mark_other_strategies_superseded(conn: sqlite3.Connection, *,
                                     goal_id: int, winner_id: int) -> int:
    """When one strategy wins Verify, mark all other live strategies of
    the same goal as 'superseded'. Returns the number of strategies
    affected. In-flight workers on those strategies' sub-goals will
    cascade as no-op once goal is proved.

    Iterates per-row through `update_strategy_status` so the inject-
    outcome propagation hook fires for each superseded strategy — a
    bulk UPDATE would silently skip the per-row hook and leave any
    associated Inject(Backward/Builder) decisions un-resolved.
    """
    rows = conn.execute(
        "SELECT id FROM strategies"
        " WHERE goal_id = ? AND id != ? AND status = 'proposed'",
        (goal_id, winner_id),
    ).fetchall()
    for r in rows:
        update_strategy_status(conn, int(r["id"]), "superseded")
    return len(rows)


def link_subgoal(conn: sqlite3.Connection, *, strategy_id: int,
                 subgoal_id: int, position: int,
                 link_kind: str = "minted") -> None:
    """`link_kind='minted'` for sub-goals this strategy created;
    `'cited'` for pre-existing siblings it reuses (auto-link / cite-wait
    edges). See the strategy_subgoals DDL comment for which readers
    traverse which."""
    conn.execute(
        "INSERT INTO strategy_subgoals"
        " (strategy_id, subgoal_id, position, link_kind)"
        " VALUES (?, ?, ?, ?)",
        (strategy_id, subgoal_id, position, link_kind),
    )
    conn.commit()


def update_strategy_status(conn: sqlite3.Connection, strategy_id: int,
                           status: str) -> None:
    conn.execute(
        "UPDATE strategies SET status = ? WHERE id = ?",
        (status, strategy_id),
    )
    conn.commit()
    # When a strategy reaches a terminal status, propagate the outcome
    # back to any Inject(Backward/Builder) decision that produced it
    # and fire the batch-done Strategist wake-up if its batch is now
    # fully resolved. Mirrors the goal-side handling in
    # `_set_goal_terminal_and_propagate`. No-op for non-terminal
    # transitions and for strategies not tied to an Inject decision.
    from .. import transitions
    if status in transitions.STRATEGY_TERMINALS:
        d = propagate_inject_outcome_from_strategy(conn, strategy_id)
        if d is not None:
            maybe_enqueue_inject_batch_done(conn, d)
    elif status == "stalled":
        # 'stalled' is terminal-for-propagation but a PARKED state, not a
        # completion. Fill the producing Inject's outcome so the in-flight-
        # batch clause stops suppressing T4 — but do NOT fire
        # inject_batch_done. Whether a parked collapse warrants a Strategist
        # wake is T4's call (`is_problem_stalled`): if sibling Injects left
        # alive alternatives the problem is not stalled and no wake is
        # owed; if nothing is alive T4 fires. Unconditionally waking here
        # (as 'dead'/'succeeded' do) re-plans work the prior Strategist run
        # already pivoted on — the duplicate-wake this status was added to
        # kill. Reopen of a subgoal flips the strategy back to 'proposed'.
        propagate_inject_outcome_from_strategy(conn, strategy_id)


def maybe_enqueue_inject_batch_done(conn: sqlite3.Connection,
                                    decision_id: int) -> None:
    """If `decision_id` belongs to an Inject batch (batch_id non-NULL)
    AND every sibling row in the batch now has `outcome` filled, fire
    a single 'inject_batch_done' Strategist trigger on this problem.

    Idempotent via the queue dedup inside the helper: a duplicate
    Strategist trigger for the same problem is silently dropped. Solo
    Inject (batch_id NULL) is a no-op.

    Lives in db.py (not dispatcher.py) so that
    `update_strategy_status` can call it without a backward import
    when wiring strategy-terminal propagation; dispatcher.py
    re-exports under its previous private name for tests that
    referenced it.
    """
    row = conn.execute(
        "SELECT batch_id, problem, group_id FROM strategist_decisions"
        " WHERE id = ?", (decision_id,),
    ).fetchone()
    if row is None or row["batch_id"] is None:
        return
    batch_id = str(row["batch_id"])
    problem = str(row["problem"])
    pending = conn.execute(
        "SELECT COUNT(*) AS n FROM strategist_decisions"
        " WHERE batch_id = ? AND outcome IS NULL",
        (batch_id,),
    ).fetchone()
    if int(pending["n"]) > 0:
        return
    # v35 — the wake goes to the group that AUTHORED the batch, not to
    # the problem: a sibling group's batch completing is none of this
    # group's business. Pre-v35 rows (group_id NULL) fall back to the
    # problem's top group, which is what they always meant.
    from .. import groups as _groups
    gid = row["group_id"]
    if gid is None:
        gid = _groups.ensure_top_group(conn, problem)
    else:
        # …and to a group that can still ACT on it. The dispatcher drops
        # a Strategist row whose group is terminal (correctly), so a wake
        # addressed to a parent that already left is not delayed, it is
        # DELETED — the child's delivery reaches nobody. Two mechanisms
        # each right, blinding each other; reachable today, since a
        # parent may Close/Ingest/Return while a child still works
        # (2026-08-16, two such pairs live on union_closed).
        me = _groups.get(conn, int(gid))
        if me is not None:
            live = _groups._nearest_active(conn, problem, me)
            if live is not None:
                gid = int(live["id"])
    # Dedup on BOTH keys while legacy problem-keyed rows can still be in
    # the queue — either one already covers this wake.
    if is_in_queue(conn, target_id=str(int(gid)), kind="Strategist"):
        return
    if is_in_queue(conn, target_id=problem, kind="Strategist"):
        return
    # Priority 20 — same band as T2 pending_review; batch completion is
    # an event-driven follow-up that supersedes routine T1 wall-clock.
    enqueue(conn, kind="Strategist", target_id=str(int(gid)),
            problem=problem, target_kind="Group", priority=20)


def reconcile_settled_inject_outcomes(
    conn: sqlite3.Connection, *, scope: str | None = None,
) -> int:
    """Resolve NULL-outcome Inject batch decisions whose produced work has
    SETTLED, so a permanently-NULL outcome can no longer suppress the T4
    stall trigger (`problems_stalled`) or block `inject_batch_done`.

    Complements `null_inject_redispatch_specs` (worker DIED with no
    artifact → re-dispatch): this is the opposite case — the work exists
    and has settled, only the outcome propagation never fired. Settled,
    by inject kind:

      * Forward (no `produced_strategy_id`): `produced_goal_id` reached a
        HARD-terminal goal status (proved / disproved — a park is
        reopenable and does NOT settle) but goal-side propagation never
        ran (the transition predated the hook or took a path that
        bypassed it) → re-run `propagate_inject_outcome_from_goal`.
      * Backward / Builder: `produced_strategy_id` reached a terminal
        strategy status → re-run `propagate_inject_outcome_from_strategy`;
        OR the strategy is still 'proposed' yet has ≥1 subgoal and ZERO
        alive ones (all proved / shelved — the canonical DEADLOCK: a
        SOFT-shelved subgoal kept the strategy 'proposed', but
        `produced_goal_id`=target only terminates at problem end, so the
        NULL outcome suppressed T4 → permanent wedge).

        BACKSTOP role (Phase 11): the PRIMARY path now flips such a parent
        strategy to its terminal status at shelve-time
        (`_maybe_stall_parent_strategies`), so this branch rarely fires.
        When it does (a soft-shelve site that bypassed the hook), drive the
        strategy terminal via `update_strategy_status`: 'succeeded' iff every
        subgoal proved (a missed verify) → wakes to assemble; else 'stalled'
        (≥1 soft-shelved, reopenable) → fills the outcome WITHOUT waking.
        A parked-collapse wake is T4's call (`is_problem_stalled`), NOT an
        unconditional `inject_batch_done` — waking here re-plans work a prior
        Strategist run already pivoted on (the duplicate-wake the 'stalled'
        status was introduced to kill). The strategy stays reopenable: a
        subgoal Reopen flips 'stalled' → 'proposed'.

    Fires `maybe_enqueue_inject_batch_done` only via `update_strategy_status`
    for genuine completions ('succeeded'/'superseded'/'dead'); 'stalled'
    fills the outcome silently. Returns the count resolved. Idempotent
    (every fill is `outcome IS NULL`-guarded). In-flight safe: a 'proposed'
    strategy with any alive subgoal is genuinely in flight and left
    untouched."""
    sql = (
        "SELECT sd.id, sd.produced_goal_id, sd.produced_strategy_id,"
        "       sd.produced_group_id, g.status AS goal_status,"
        "       s.status AS strat_status, gr.status AS group_status"
        " FROM strategist_decisions sd"
        " LEFT JOIN goals g ON g.id = sd.produced_goal_id"
        " LEFT JOIN strategies s ON s.id = sd.produced_strategy_id"
        " LEFT JOIN groups gr ON gr.id = sd.produced_group_id"
        " WHERE sd.decision_kind IN " + _BATCH_KINDS_SQL +
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
    )
    _sc, args = scope_sql(scope, "sd.problem")
    if _sc:
        sql += f" AND {_sc}"
    from .. import transitions
    rows = list(conn.execute(sql, args))
    resolved = 0
    for r in rows:
        did = int(r["id"])
        sid = r["produced_strategy_id"]
        filled: int | None = None
        if sid is not None:
            sstat = (str(r["strat_status"])
                     if r["strat_status"] is not None else None)
            if sstat in transitions.STRATEGY_TERMINALS:
                filled = propagate_inject_outcome_from_strategy(
                    conn, int(sid))
            elif sstat == "proposed":
                sub = conn.execute(
                    "SELECT g2.status AS st, COUNT(*) AS n"
                    " FROM strategy_subgoals ss"
                    " JOIN goals g2 ON g2.id = ss.subgoal_id"
                    " WHERE ss.strategy_id = ? GROUP BY g2.status",
                    (int(sid),),
                ).fetchall()
                comp = {str(x["st"]): int(x["n"]) for x in sub}
                total = sum(comp.values())
                alive = (comp.get("open", 0) + comp.get("attempting", 0)
                         + comp.get("pending_strategist_review", 0))
                if total > 0 and alive == 0:
                    # BACKSTOP only: the primary path flips the parent
                    # strategy to its terminal status at shelve-time
                    # (`_maybe_stall_parent_strategies`). If a soft-shelve
                    # site was missed, drive the strategy terminal here so
                    # status + inject outcome stay consistent. 'succeeded'
                    # (all proved — a missed verify) wakes to assemble;
                    # 'stalled' (>=1 soft-shelved, reopenable) fills the
                    # outcome WITHOUT waking — the parked-collapse wake is
                    # T4's call, not an unconditional inject_batch_done.
                    # update_strategy_status performs both the propagation
                    # and the (success-only) batch-done enqueue.
                    new_status = ("succeeded"
                                  if comp.get("proved", 0) == total
                                  else "stalled")
                    update_strategy_status(conn, int(sid), new_status)
                    resolved += 1
                    continue
        elif r["produced_goal_id"] is not None and \
                str(r["goal_status"]) in transitions.GOAL_HARD_TERMINALS:
            # `shelved` intentionally excluded — reopenable/parked, not a
            # settled inject (see propagate_inject_outcome_from_goal). The
            # stall predicate's active-check governs T4 suppression instead.
            filled = propagate_inject_outcome_from_goal(
                conn, int(r["produced_goal_id"]))
        elif r["produced_group_id"] is not None and \
                str(r["group_status"]) in ("delivered", "returned", "closed"):
            # v35 — a Delegate whose group finished but whose outcome never
            # propagated. Every group terminal is HARD (no reopenable case,
            # unlike a shelved goal), so the whole non-'active' set settles.
            filled = propagate_inject_outcome_from_group(
                conn, int(r["produced_group_id"]))
        if filled is not None:
            maybe_enqueue_inject_batch_done(conn, filled)
            resolved += 1
    if resolved:
        print(f"[reconcile] resolved {resolved} settled NULL-outcome "
              f"batch decision(s)", flush=True)
    return resolved


def decision_infra_deaths(conn: sqlite3.Connection,
                          decision_id: int) -> int:
    """How many INFRA deaths the worker answering this decision has
    already cost it."""
    row = conn.execute(
        "SELECT infra_deaths FROM strategist_decisions WHERE id = ?",
        (int(decision_id),)).fetchone()
    return int(row["infra_deaths"]) if row is not None else 0


def record_decision_infra_death(conn: sqlite3.Connection,
                                decision_id: int) -> int:
    """Charge one infra death to this decision; return the new total.

    `cascade_one` is the ONE caller, and that is what makes the count
    honest: it sees every worker ending exactly once, a normal return
    and a thrown exception alike. A pipeline counting its own deaths
    would miss the second kind and double the first."""
    conn.execute(
        "UPDATE strategist_decisions"
        " SET infra_deaths = infra_deaths + 1, updated_at = ?"
        " WHERE id = ?", (now(), int(decision_id)))
    conn.commit()
    return decision_infra_deaths(conn, decision_id)


def reconcile_spent_theorize_outcomes(conn: sqlite3.Connection, *,
                                      scope: "str | None" = None) -> int:
    """Settle every `Theorize` whose GROUP has left — the complement of
    `null_theorize_redispatch_specs`, and the same division of labour
    this file's reconciler above has with the Inject redispatch: one side
    revives what still has a worker to run, the other closes what can
    never get one.

    A retired group's request is SPENT: the pop-time door refuses to
    spawn on it (`_row_is_stale`, the Theorist arm), and no other road
    fills the outcome — the pipeline settles its own row on both of ITS
    roads, but only if it runs. Left NULL it goes on suppressing the
    group's wakes forever, which is precisely the wedge
    `_theorize_in_flight` documents as impossible for this kind. It is
    also what makes the redispatch helper's group filter safe: without
    this, skipping a retired group would trade a re-enqueue loop for a
    permanent NULL.

    Returns the count settled. Idempotent (`outcome IS NULL`-guarded)."""
    sql = (
        "SELECT sd.id, gr.status FROM strategist_decisions sd"
        " JOIN groups gr ON gr.id = sd.group_id"
        " WHERE sd.decision_kind = 'Theorize' AND sd.outcome IS NULL"
        "   AND gr.status <> 'active'"
    )
    _sc, args = scope_sql(scope, "sd.problem")
    if _sc:
        sql += f" AND {_sc}"
    from .. import transitions
    settled = 0
    for r in list(conn.execute(sql, args)):
        transitions._record_inject_decision_outcome(
            conn, int(r["id"]), "failed", "group_retired",
            detail=("the group that asked left the tree"
                    f" ({str(r['status'])}) before the theory layer"
                    " answered"))
        maybe_enqueue_inject_batch_done(conn, int(r["id"]))
        settled += 1
    if settled:
        print(f"[theorist] settled {settled} spent theory request(s) "
              f"— the group that asked has left", flush=True)
    return settled


def delete_strategy(conn: sqlite3.Connection, strategy_id: int) -> None:
    """Remove a strategy row outright.

    #101 — When a pipeline fails before the agent did any real work
    (quota_exhausted / spawn_fast_fail / missing_dep / gateway_unreachable
    / transient_timeout), the strategy row is an empty shell: no
    proposal_md, no scratch_path, no strategy_subgoals link. Marking it
    `dead` would leave forensic noise (the SG run accumulated 8587 such
    rows). Delete instead — the row never reflected real agent output.

    Caller guarantees no `strategy_subgoals` rows exist (FK is enforced
    by PRAGMA foreign_keys=ON; infra failures occur before
    `_backward_parse_and_commit` would `link_subgoal`). dead_attempts
    has no FK to strategies, so historical dead_attempts referencing
    a deleted strategy_id stay readable."""
    conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    conn.commit()


def strategies_ready_for_verify(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Strategies whose all sub-goals are proved AND whose own parent goal
    is still alive (not already proved by a sibling strategy). The
    parent-alive check prevents Verify thrashing when an OR sibling has
    already won the goal — without it bfs_refill keeps re-enqueueing
    the doomed Verify forever.

    A 0-subgoal strategy (Phase 6.5 Backward leaf-bypass — agent wrote a
    complete proof in patch.lean with no decomposition) is also ready:
    the NOT EXISTS clause is vacuously true when no strategy_subgoals
    rows exist for that strategy.
    """
    return list(conn.execute(
        "SELECT s.* FROM strategies s "
        "JOIN goals g ON g.id = s.goal_id "
        "WHERE s.status = 'proposed' "
        "  AND g.status NOT IN ('proved','shelved') "
        "  AND s.scratch_path != '' "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM strategy_subgoals ss"
        "    JOIN goals sg ON sg.id = ss.subgoal_id"
        "    WHERE ss.strategy_id = s.id AND sg.status != 'proved'"
        "  )"
        # Deterministic order so per-goal Verify serialization (the
        # per-goal-bfs cap in bfs_refill) picks the same sibling on
        # each tick — without this, sqlite's natural rowid order is
        # nominal but documented-as-undefined.
        " ORDER BY s.id"
    ))


