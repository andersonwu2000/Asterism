from __future__ import annotations

import json
import sqlite3

from .core import now, scope_sql
from .reach import ALIVE_CTE_PER_PROBLEM, open_goals


# ---------------------------------------------------------------------
# Phase 2 — problem-level Strategist state helpers
# ---------------------------------------------------------------------

def set_problem_bootstrap_done(conn: sqlite3.Connection, problem: str) -> None:
    """Mark a problem as past the T0 first-launch trigger. Set after
    Strategist's first commit on that problem (any decision kind)."""
    conn.execute(
        "UPDATE problems SET bootstrap_done = 1 WHERE name = ?",
        (problem,),
    )
    conn.commit()


def set_problem_ingested(conn: sqlite3.Connection, problem: str,
                         ingested: bool = True) -> None:
    """Phase 6 (v16) — set/clear the problem's TERMINAL state.

    Set (timestamped) by `_commit_ingest` when the Strategist commits the
    `Ingest` decision — the only exit trigger. Cleared by the rollback
    auto-revoke when a post-Ingest un-prove (rogue-sorryAx cascade)
    invalidates the terminal judgment, which puts the problem back on the
    live path (T1 / T4 / exit check all key off this column)."""
    conn.execute(
        "UPDATE problems SET ingested_at = ? WHERE name = ?",
        (now() if ingested else None, problem),
    )
    conn.commit()


def problem_ingested(conn: sqlite3.Connection, problem: str) -> bool:
    """Phase 6 — True iff the Strategist has committed the terminal
    `Ingest` on this problem (see `set_problem_ingested`)."""
    row = conn.execute(
        "SELECT ingested_at FROM problems WHERE name = ?",
        (problem,),
    ).fetchone()
    return row is not None and row["ingested_at"] is not None


def all_problems_ingested(conn: sqlite3.Connection,
                          scope: str | None = None) -> bool:
    """Phase 6 — True iff every problem in scope has reached the `Ingest`
    terminal state (and there is at least one problem in scope). The
    daemon exit check's replacement for `root_proved`: root-proved is a
    HARD prerequisite of Ingest when a root exists, but the terminal
    judgment itself (charter fully satisfied) is the Strategist's."""
    sql = "SELECT count(*) AS c FROM problems WHERE ingested_at IS NULL"
    tot = "SELECT count(*) AS t FROM problems"
    _sc, args = scope_sql(scope, "name")   # pattern OR explicit list
    if _sc:
        sql += f" AND {_sc}"
        tot += f" WHERE {_sc}"
    remaining = int(conn.execute(sql, args).fetchone()["c"])
    total = int(conn.execute(tot, args).fetchone()["t"])
    return total > 0 and remaining == 0


def set_problem_strategist_directive(conn: sqlite3.Connection,
                                     problem: str,
                                     directive: str | None) -> None:
    """Overwrite-on-write standing directive. EmitDirective /
    Reopen-with-directive sets non-empty text; passing None / empty
    clears it (the cascade reset path)."""
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = ?",
        (directive if directive else None, problem),
    )
    conn.commit()


def update_problem_last_strategist_at(conn: sqlite3.Connection,
                                      problem: str) -> None:
    """Touch the last-Strategist-commit timestamp. Called on every Strategist
    commit regardless of decision_kind / trigger_kind. (Event-driven; does
    NOT drive T1 — that reads `last_routine_at`.)"""
    conn.execute(
        "UPDATE problems SET last_strategist_at = ? WHERE name = ?",
        (now(), problem),
    )
    conn.commit()


def update_problem_last_routine_at(conn: sqlite3.Connection,
                                   problem: str) -> None:
    """Touch the ROUTINE-only clock that drives T1. Called ONLY on a
    `trigger_kind='routine'` Strategist commit, so the routine audit fires on
    its own fixed cadence instead of being reset by event-driven triggers."""
    conn.execute(
        "UPDATE problems SET last_routine_at = ? WHERE name = ?",
        (now(), problem),
    )
    conn.commit()


def unacknowledged_inject_batches(conn: sqlite3.Connection,
                                  problem: str,
                                  group_id: "int | None" = None
                                  ) -> list[str]:
    """Return batch_ids of Inject batches on this problem where every
    row's `outcome` is filled (batch fully terminated) AND the most
    recent row update is newer than the problem's last_strategist_at
    (i.e. Strategist hasn't seen this completion yet).

    Used by the dispatcher's trigger-derivation block to fire
    `inject_batch_done` Strategist invocations. Per Phase 2.5 §X,
    the acknowledgement ratchet is `last_strategist_at`: a Strategist
    commit advances it, so subsequent batch-done queries naturally
    deduplicate without a per-row `acked_at` column.

    NULL `last_strategist_at` (never had a Strategist commit) behaves as
    'all batches are unacknowledged' — coalesced to
    '1970-01-01T00:00:00' so SQL comparison works.

    v35 — with `group_id` both halves narrow to that group: the batches
    it authored, ratcheted on ITS clock. Left problem-wide, one group's
    commit acknowledges a sibling's completed batch on the sibling's
    behalf, and the batch-done wake that forces a real advance is simply
    skipped.

    2026-09-03 — the clock is no longer the whole answer. A batch that
    finished MID-DEBATE reached the author as a delta line, not as a
    report, and the commit's bump would swallow it; `strategist.
    batch_ack` marks such a batch `report_carried_at` and it stays
    unacknowledged until a wake actually delivers or acts on it. NULL
    (every legacy row, every batch a wake received normally) means the
    clock decides, exactly as before.

    `>=`, not `>`: both stamps come from `now()`, whose Windows
    resolution is coarse enough for a batch settling inside the commit's
    own tick to TIE — and a tie lost the strict comparison, so that
    batch's report reached no wake at all. Same granularity rule the
    decline window already carries ("a decline landing the same clock
    tick as the wake's own commit must not vanish",
    `phase2_context.outcomes._recent_decline_lines`): a boundary repeat
    costs one re-render, a swallowed report costs the outcomes.
    """
    sql = ("SELECT batch_id,"
           "       SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) AS pending,"
           "       MAX(report_carried_at) AS carried,"
           "       MAX(updated_at) AS last_update"
           " FROM strategist_decisions"
           " WHERE problem = ? AND batch_id IS NOT NULL")
    args: tuple = (problem,)
    if group_id is not None:
        sql += " AND (group_id = ? OR group_id IS NULL)"
        args = (problem, int(group_id))
    rows = conn.execute(
        sql + " GROUP BY batch_id HAVING pending = 0", args).fetchall()
    if not rows:
        return []
    if group_id is not None:
        lsa_row = conn.execute(
            "SELECT COALESCE(last_strategist_at,"
            " '1970-01-01T00:00:00+00:00') AS lsa FROM groups WHERE id = ?",
            (int(group_id),)).fetchone()
    else:
        lsa_row = conn.execute(
            "SELECT COALESCE(last_strategist_at,"
            " '1970-01-01T00:00:00+00:00') AS lsa FROM problems"
            " WHERE name = ?", (problem,)).fetchone()
    lsa = str(lsa_row["lsa"]) if lsa_row else '1970-01-01T00:00:00+00:00'
    return [str(r["batch_id"]) for r in rows
            if r["carried"] is not None or str(r["last_update"]) >= lsa]


# Phase 6 — `problems_needing_t0` (root `frozen` → first_launch wake) is
# RETIRED along with the T0 trigger and the first_launch prompt. A fresh
# problem (frozen root, or no goals at all in pure-NL mode) has no
# dispatchable work and no committed Ingest, so it IS structurally stalled:
# the T4 stall trigger wakes the Strategist immediately and the wake runs
# under the `inject_batch_done` prompt (the "empty batch done" reading),
# whose mandatory-advance rule forces the first Inject. T1's
# NULL-`last_routine_at` = ancient rule remains the slow-path backstop.


def problems_needing_t1(conn: sqlite3.Connection, *,
                        max_age_sec: float,
                        scope: str | None = None,
                        since_iso: str | None = None,
                        ) -> list[str]:
    """Return problem names whose ROUTINE clock (`last_routine_at`) is older
    than `max_age_sec`. Excludes problems already at the `Ingest` terminal
    state (`ingested_at` set — Phase 6: problem liveness is the Strategist's
    terminal judgment, not the root goal's status; a proved-root problem
    whose Ingest hasn't been committed is still LIVE and still audited).

    Two deliberate departures from the event-driven triggers (T0 / T2), so the
    routine audit fires on its own fixed running-time cadence — its
    methodological job (periodic full-tree survey) is distinct from reacting
    to a shelve or a batch completion, and must not be starved by a busy event
    stream (stokes 2026-06-12: 0 routine over 5h):

      1. Reads `last_routine_at` (bumped ONLY by a routine commit), not
         `last_strategist_at` (bumped by every commit). So pending_review /
         inject_batch_done commits do NOT reset the routine clock.
      2. NO in-flight-batch suppression (T0 keeps it; routine does not) — the
         routine audit is independent of batch resolution.

    `since_iso` (daemon start, ISO): the clock baseline is
    `max(last_routine_at, since_iso)`, so paused/down time does not count
    toward the interval — a long pause doesn't make routine fire immediately
    on restart; it waits `max_age_sec` of running time. NULL last_routine_at
    is "ancient" (never routine'd), so the first routine fires `max_age_sec`
    after startup."""
    # SQLite julianday() yields fractional days; convert max_age_sec to days.
    max_age_days = max_age_sec / 86400.0
    # Clock baseline: later of last_routine_at (or epoch, if never routine'd)
    # and the daemon start, so paused/down time is excluded.
    if since_iso is not None:
        baseline_sql = ("max(julianday(coalesce(p.last_routine_at,"
                        " '1970-01-01')), julianday(?))")
        args: list = [since_iso, max_age_days]
    else:
        baseline_sql = "julianday(coalesce(p.last_routine_at, '1970-01-01'))"
        args = [max_age_days]
    sql = (
        "SELECT p.name"
        " FROM problems p"
        " WHERE p.ingested_at IS NULL"
        f"   AND julianday('now') - {baseline_sql} > ?"
    )
    _sc, _sa = scope_sql(scope, "p.name")
    if _sc:
        sql += f" AND {_sc}"
        args.extend(_sa)
    sql += " ORDER BY p.name"
    return [str(r["name"]) for r in conn.execute(sql, tuple(args))]


def groups_needing_t1(conn: sqlite3.Connection, *,
                      max_age_sec: float,
                      scope: str | None = None,
                      since_iso: str | None = None,
                      ) -> list[sqlite3.Row]:
    """The per-GROUP routine clock (v35) — the seat source T1 dispatches
    from. Returns `groups` rows (id, problem) whose `last_routine_at` is
    older than `max_age_sec` of RUNNING time.

    Same two departures as the problem-level original it replaces (read
    the routine-only clock, no in-flight suppression) and the same
    `since_iso` running-time baseline; see `problems_needing_t1` for why
    each exists. What changes is the KEY: every group runs its own
    cadence, which is what lets sibling groups work concurrently instead
    of taking turns at one problem-wide seat.

    Filters: the problem must not be at its Ingest terminal, and the
    group itself must still be `active` — a delivered / returned / closed
    group has no work and must not hold a seat.

    A group with a live child group IT DELEGATED is WAITING, and a
    waiting group's periodic clock is FROZEN (operator ruling
    2026-08-03): the parent delegated the work, so a routine there audits
    nothing and burns a fable wake — three children working seven hours
    used to buy the parent three empty routines. Event wakes
    (pending_review, the batch-done relay when the delegate settles) are
    untouched; on the last child's terminal transition
    `groups.set_status` restarts the parent's cadence so the frozen time
    never counts as overdue.

    A child the OWNER opened does not freeze it (owner ruling
    2026-09-03, the same ruling `_NOT_HUMAN_OPENED` carries): a person's
    Delegate hands over no line, so the parent's own audit cadence is
    still owed. Group 691 of Combinatorics.union_closed had not run a
    routine since 2026-09-02T21:52Z for exactly this reason. A child
    whose `opened_by` row is missing (the pre-v35 backfill, a
    hand-written row) keeps freezing the parent — the safe direction for
    a suppressor, as on `_group_clause`.

    While only top groups exist this returns exactly one row per problem
    that `problems_needing_t1` would have named, so the switch is
    behaviour-preserving.
    """
    max_age_days = max_age_sec / 86400.0
    if since_iso is not None:
        baseline_sql = ("max(julianday(coalesce(g.last_routine_at,"
                        " '1970-01-01')), julianday(?))")
        args: list = [since_iso, max_age_days]
    else:
        baseline_sql = "julianday(coalesce(g.last_routine_at, '1970-01-01'))"
        args = [max_age_days]
    sql = (
        "SELECT g.id, g.problem"
        " FROM groups g JOIN problems p ON p.name = g.problem"
        " WHERE p.ingested_at IS NULL AND g.status = 'active'"
        "   AND NOT EXISTS (SELECT 1 FROM groups ch"
        "                   LEFT JOIN strategist_decisions sd"
        "                     ON sd.id = ch.opened_by"
        "                   WHERE ch.parent_group_id = g.id"
        "                     AND ch.status = 'active'"
        + _NOT_HUMAN_OPENED + ")"
        f"   AND julianday('now') - {baseline_sql} > ?"
    )
    _sc, _sa = scope_sql(scope, "g.problem")
    if _sc:
        sql += f" AND {_sc}"
        args.extend(_sa)
    sql += " ORDER BY g.problem, g.id"
    return list(conn.execute(sql, tuple(args)))


def group_routine_due(conn: sqlite3.Connection, group_id: int, *,
                      max_age_sec: float,
                      since_iso: str | None = None) -> bool:
    """Is THIS group's routine clock due? The wake-side counterpart of
    `groups_needing_t1` (which selects across all groups), used by the
    spawn to classify its own trigger."""
    return any(int(r["id"]) == int(group_id) for r in groups_needing_t1(
        conn, max_age_sec=max_age_sec, since_iso=since_iso))


def problems_with_pending_review(conn: sqlite3.Connection, *,
                                 scope: str | None = None
                                 ) -> list[str]:
    """Return problem names with at least one goal in
    `pending_strategist_review` and no committed Ingest. Phase 6: the old
    root-status exclusion (proved / disproved roots dropped) is replaced by
    the problem terminal state — a proved-root problem still needs review
    wakes (the Strategist has to judge the review AND eventually commit
    Ingest); a `shelved` root never suppressed reviews (the ConfirmShelve+
    Inject endgame parks the root while bricks shelve to review — excluding
    it orphaned P13 `per_chart_stokes_generic` 2026-06-14).

    The per-tick stuck-state reconciler (`reconcile_stuck_states`) enqueues a
    Strategist for each so a pending review never orphans when the cascade-
    time fast-path enqueue (`_enqueue_strategist_review`) is deduped / lost /
    not restored at restart — the lost-wakeup that left P13 goals stuck
    (2026-06-13) and wedged Banach-Tarski g3246 for 30+ min (2026-05-27). The
    spawn-time `_derive_strategist_trigger` then sees the pending goal and
    runs a `pending_review` wake.

    No in-flight-batch suppression (unlike T0/T1): a pending review and an
    unacknowledged Inject batch are not mutually exclusive — `_derive_
    strategist_trigger` orders them (batch first), and the caller's per-root
    Strategist dedup prevents a double-enqueue."""
    sql = (
        "SELECT DISTINCT p.name"
        " FROM problems p"
        " JOIN goals g_pend ON g_pend.problem = p.name"
        "   AND g_pend.status = 'pending_strategist_review'"
        " WHERE p.ingested_at IS NULL"
    )
    _sc, args = scope_sql(scope, "p.name")
    if _sc:
        sql += f" AND {_sc}"
    sql += " ORDER BY p.name"
    return [str(r["name"]) for r in conn.execute(sql, args)]


def null_inject_redispatch_specs(conn: sqlite3.Connection, *,
                                 scope: str | None = None
                                 ) -> list[dict]:
    """Queue specs for every NULL-outcome Inject decision that still needs a
    worker (its produced artifact does not exist yet).

    Shared by startup `recovery` (re-enqueues all — clean slate) and the
    per-tick `reconcile_stuck_states` (re-enqueues only those with no
    in-flight worker). Encodes the produced-artifact guards so an Inject is
    NOT redispatched once its outcome will propagate from the artifact's
    terminal: a Forward that already registered its lemma (`produced_goal_id`
    set), or a Backward that already committed a strategy
    (`produced_strategy_id` set) — both are commit-time WORK ARTIFACTS, so
    their presence means the worker reached its product and the outcome will
    propagate from there. A BUILDER HAS NO SUCH ARTIFACT: it proves its
    target in place, and `produced_goal_id` is set to `=target` at commit as
    an outcome backlink, NOT a work-done signal — it is non-NULL from the
    very start. So a killed Builder must be judged by its TARGET'S status,
    not by `produced_goal_id` (the parked-target check below). Gating Builder
    on `produced_goal_id` is exactly what wedged P13 4284 (2026-06-15): every
    killed Builder was skipped forever (backlink set at commit) while
    `has_active_inflight_inject` counted it active → the Strategist was
    suppressed and the work was never resumed → permanent deadlock.
    ALSO skips a Backward/Builder whose TARGET goal is no longer awaiting a
    worker (parked/terminal — e.g. a return_to_parent that shelved the target
    without committing a strategy): its NULL outcome is permanent now that
    `shelved` no longer settles, but the work is parked, not missing —
    redispatching would re-spin it forever (P13 4284, 2026-06-15). A
    NULL-outcome Inject whose worker died on infra failure (no artifact,
    target still open/attempting) wedges the problem via the in-flight
    active-check (`has_active_inflight_inject`) — so it must be redispatched.

    `Delegate` is deliberately NOT included (v35): this function re-enqueues
    a WORKER, and a delegated burden has none — its executor is the group's
    own Strategist seat, so a lost seat is the seat mechanism's problem to
    recover, not a re-dispatch. Widening the filter here would queue a
    worker against a decision that never had one.

    Returns dicts: `{decision_id, problem, kind, target_id, target_kind}`."""
    sql = (
        "SELECT id, problem, payload, target_id, produced_goal_id,"
        " produced_strategy_id FROM strategist_decisions"
        " WHERE decision_kind = 'Inject' AND outcome IS NULL"
    )
    _sc, args = scope_sql(scope)
    if _sc:
        sql += f" AND {_sc}"
    specs: list[dict] = []
    for r in conn.execute(sql, args):
        try:
            payload = json.loads(r["payload"] or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}
        # Shape-derived (Formalizer merge, review 07-27 #2): the mode
        # lives in the decision's target shape, not the legacy payload
        # `pipeline` word — a 'Formalizer' payload hit the old "unknown
        # pipeline, skip silently" arm and goal-Inject recovery was
        # dropped. target_id NULL = mint; present = goal redispatch.
        # `pipeline` is kept ONLY to pick the legacy queue kind for
        # pre-merge rows (cooldown/flush key coherence).
        pipeline = payload.get("pipeline")
        if r["target_id"] is None:
            if r["produced_goal_id"] is not None:
                continue  # lemma landed; outcome propagates from goal
            specs.append({
                "decision_id": int(r["id"]), "problem": str(r["problem"]),
                "kind": ("Forward" if pipeline == "Forward"
                         else "Formalizer"),
                "target_id": str(r["problem"]),
                "target_kind": "Problem",
            })
        else:
            # Superseded by a LATER inject on the same target: the Strategist
            # re-decided this goal (e.g. Builder #924 then Backward #926 on
            # 4284 — a Builder→Backward routing switch). Only the LATEST inject
            # per target is the live intent; an older one (ANY kind) is now
            # obsolete. Redispatching it resurrects a stale, often wrong-kind
            # attempt carrying a stale brief (P13 4284 2026-06-15: stale Builder
            # #924 re-launched alongside the new Backward #926 — the better the
            # Strategist routes, the more this bites). Forward targets the
            # PROBLEM (target_id NULL, handled above) — each is a distinct
            # lemma, never superseded this way.
            if conn.execute(
                "SELECT 1 FROM strategist_decisions WHERE decision_kind = 'Inject'"
                " AND target_id = ? AND id > ? LIMIT 1",
                (int(r["target_id"]), int(r["id"])),
            ).fetchone() is not None:
                continue
            if (pipeline in ("Backward", "Formalizer", None)
                    and r["produced_strategy_id"] is not None):
                continue  # strategy committed; outcome from strategy terminal
            # NB: NO produced_goal_id guard for legacy Builder — it proves
            # in place, so produced_goal_id is a commit-time backlink
            # (=target), not a work-done artifact (see docstring); those
            # rows are judged solely by the target's status below.
            # Target no longer awaiting a worker (parked / terminal): the
            # worker already RAN and parked it (e.g. a Backward
            # return_to_parent that committed no strategy → target shelved,
            # or pending_strategist_review awaiting a Strategist verdict).
            # Its NULL outcome is now permanent (shelved no longer settles —
            # see propagate_inject_outcome_from_goal), but the work is NOT
            # missing, so redispatching would re-spin the parked goal forever
            # (the P13 4284 disease, here via the redispatch path). Only
            # redispatch a target that genuinely still awaits a worker.
            tgt = conn.execute(
                "SELECT status FROM goals WHERE id = ?",
                (int(r["target_id"]),),
            ).fetchone()
            if tgt is None or str(tgt["status"]) not in ("open", "attempting"):
                continue
            specs.append({
                "decision_id": int(r["id"]), "problem": str(r["problem"]),
                "kind": (pipeline if pipeline in ("Backward", "Builder")
                         else "Formalizer"),
                "target_id": str(int(r["target_id"])),
                "target_kind": "Goal",
            })

    # Per target, the goal branch above already kept only the LATEST
    # inject (older ones — any kind — were skipped as superseded), so
    # `specs` carries at most one goal-targeted redispatch per goal plus
    # the per-lemma mint specs. This subsumes the earlier per-(target,kind)
    # collapse and additionally handles cross-kind supersession (Builder→
    # Backward), which that collapse missed (P13 4284 double-dispatch,
    # 2026-06-15). Superseded NULL rows stay NULL here, harmlessly —
    # reconcile_settled_inject_outcomes settles them once the goal terminates.
    return specs


def queue_has_decision(conn: sqlite3.Connection, decision_id: int) -> bool:
    """True iff a queue row carries `decision_id` (Inject-authored dispatch).
    Used by `reconcile_stuck_states` to avoid re-enqueuing a NULL-outcome
    Inject whose worker is already queued."""
    row = conn.execute(
        "SELECT 1 FROM queue WHERE decision_id = ? LIMIT 1", (decision_id,),
    ).fetchone()
    return row is not None


_SUBTREE_CTE = (
    "WITH RECURSIVE sub(gid) AS ("
    "  VALUES(?)"
    "  UNION"
    "  SELECT ss.subgoal_id FROM strategies s"
    "   JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
    "   JOIN sub ON s.goal_id = sub.gid"
    "   WHERE s.status IN ('proposed','succeeded'))"
)


def _subtree_has_live_frontier(conn: sqlite3.Connection,
                               goal_id: int, *,
                               frontier: str = "stall") -> bool:
    """True iff the subtree rooted at `goal_id` — walked downward through
    'proposed'/'succeeded' strategies — contains a live frontier. TWO
    semantics, picked by `frontier` (2026-07-11, the T2 wake-pump
    livelock):

    - "stall" (T4 suppression): an `open` goal (BFS dispatches it) OR a
      `pending_strategist_review` goal (a T2 review is queued — T4 must
      not race T2). An `attempting` node contributes nothing by itself —
      its activity must bottom out in such a frontier (2026-07-09
      putnam_2025_b6 wedge).

    - "dispatch" (the Strategist anti-idle gate): only what moves
      WITHOUT a Strategist — an `open` goal (BFS) or a queued/leased
      worker on a subtree goal (queue row, target_kind='Goal'). Counting
      `pending_strategist_review` HERE would be self-referential: the
      queued handler that review is waiting for IS the strategist
      standing at the gate, so a walled tree read as "live" and
      EmitDirective-only batches passed forever (b6 2026-07-10,
      301-spawn wake pump).
    """
    if frontier == "stall":
        return conn.execute(
            _SUBTREE_CTE +
            " SELECT 1 FROM goals"
            " WHERE id IN (SELECT gid FROM sub)"
            "   AND status IN ('open','pending_strategist_review') LIMIT 1",
            (goal_id,),
        ).fetchone() is not None
    if frontier == "dispatch":
        return conn.execute(
            _SUBTREE_CTE +
            " SELECT 1 WHERE EXISTS ("
            "   SELECT 1 FROM goals"
            "   WHERE id IN (SELECT gid FROM sub) AND status = 'open')"
            " OR EXISTS ("
            "   SELECT 1 FROM queue q"
            "   WHERE q.target_kind = 'Goal'"
            "     AND CAST(q.target_id AS INTEGER) IN (SELECT gid FROM sub))",
            (goal_id,),
        ).fetchone() is not None
    raise ValueError(f"unknown frontier semantics {frontier!r}")


#: Decision kinds whose rows JOIN a batch (v35).
#:
#: The batch CYCLE itself is kind-blind: `maybe_enqueue_inject_batch_done`
#: counts unfinished siblings by `batch_id` alone, so a new kind rides it
#: for free as long as it is minted into the same batch and leaves
#: `outcome` NULL until its work terminates. What is NOT free are the
#: places that filter on the kind — this constant is their single
#: definition, so a future kind cannot land in two of them and be
#: forgotten in the third.
#:
#: `Delegate`'s produced work is a GROUP; `Inject`'s is a goal or a
#: strategy. `null_inject_redispatch_specs` deliberately does NOT use this
#: set: it re-enqueues a WORKER, and a Delegate has none — its executor is
#: the group's own Strategist seat.
BATCH_DECISION_KINDS = ("Inject", "Delegate")
_BATCH_KINDS_SQL = "(" + ", ".join(
    f"'{k}'" for k in BATCH_DECISION_KINDS) + ")"


def propagate_inject_outcome_from_group(
    conn: sqlite3.Connection, group_id: int,
) -> int | None:
    """When `group_id` reaches a terminal status, fill the outcome of the
    `Delegate` decision that opened it — the group analogue of
    `propagate_inject_outcome_from_goal` / `..._from_strategy`.

    Mapping: 'delivered' → 'success' (the charter came back settled and
    its bricks are the parent's to cite). 'returned' → 'failed:returned'
    (the group handed the charter back; WHICH flavour — refuted / amend /
    exhausted — is recorded on the `ReturnToParent` row, not compressed
    into this enum). 'closed' → 'failed:closed' (the parent retired it).
    'active' is not terminal and this is a no-op.

    Note there is no group analogue of `shelved`: a group is either
    working or done. That is why the mapping needs no reopenable case —
    reviving a settled charter means opening a new group.

    Returns the affected decision row id (caller may then fire
    `maybe_enqueue_inject_batch_done`), or None. Idempotent via the
    `outcome IS NULL` guard.
    """
    row = conn.execute(
        "SELECT id FROM strategist_decisions"
        " WHERE produced_group_id = ? AND outcome IS NULL",
        (int(group_id),)).fetchone()
    if row is None:
        return None
    g = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (int(group_id),)).fetchone()
    if g is None:
        return None
    status = str(g["status"])
    outcome = {"delivered": "success",
               "returned": "failed:returned",
               "closed": "failed:closed"}.get(status)
    if outcome is None:
        return None
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (outcome, now(), int(row["id"])))
    return int(row["id"])


def _group_clause(group_id: "int | None") -> str:
    """Narrow a batch-decision scan to one AUTHORING group (v35). Empty
    when no group is named, so the problem-wide readers are unchanged.

    An UNATTRIBUTED row (`group_id IS NULL` — a hand-written row, or one
    from before the v35 backfill) counts for every group. These
    predicates all SUPPRESS a wake, and the safe direction for a
    suppressor is to over-suppress: a missed stall is picked up by the
    routine clock, while a false stall wakes an agent that has nothing
    to do — the livelock class this file has paid for three times."""
    return "" if group_id is None else         "   AND (sd.group_id = ? OR sd.group_id IS NULL)"


def _group_args(problem: str, group_id: "int | None") -> tuple:
    return (problem,) if group_id is None else (problem, int(group_id))


# WHOSE LINE THE CHILD IS ON. A `Delegate` the Strategist files hands
# the parent's own line to the child — the parent stops there, and that
# is why an active produced group counts as the parent's in-flight work.
# A `Delegate` a PERSON files (HID §3.2, `state/commands.py`, actor
# 'human') hands over nothing: the owner opened a line BESIDE the
# parent's, and the parent still owes its own (owner ruling 2026-09-03).
#
# Counting the person's group as the parent's work froze the parent
# outright: top group 691 of Combinatorics.union_closed went idle at
# 05:13Z on 2026-09-03, its batch-done wake refused and its T4 stall
# rescue suppressed, because cond-4 of `is_group_stalled` read decision
# 5736 — the owner's Delegate, produced group 693 active — as work group
# 691 was waiting on.
#
# The DELIVERY direction is untouched: the child's terminal transition
# fills this row's outcome and wakes the parent exactly as a machine
# Delegate's does (`groups.set_status` → `propagate_inject_outcome_from_
# group` → `maybe_enqueue_inject_batch_done`). What changes is only the
# waiting.
_NOT_HUMAN_OPENED = " AND COALESCE(sd.actor, '') <> 'human'"


def has_active_inflight_inject(conn: sqlite3.Connection, problem: str, *,
                               group_id: "int | None" = None) -> bool:
    """True iff `problem` has a NULL-outcome batch decision whose produced
    work is still genuinely ACTIVE:

      * `produced_goal_id`     → goal `open`, or `attempting` WITH a live
        dispatch frontier in its subtree (`_subtree_has_live_frontier`), OR
      * `produced_strategy_id` → strategy 'proposed' with >=1 subgoal that
        is open / pending_strategist_review, or attempting with a live
        frontier, OR
      * `produced_group_id`    → a discussion group still 'active' (v35).

    The group arm is what lets a parent group stay QUIET while its child
    works. A delegated burden with no anchor goal has neither of the other
    two artifacts, so without this arm the opening decision reads as
    "produced work inactive" and T4 wakes the parent on every tick while
    the child is mid-flight.

    A bare status check is enough for a group, unlike the `attempting`
    case above (which had to start recursing after the 2026-07-09 b6
    wedge): a goal can sit `attempting` over an entirely parked subtree,
    but there is no parked group status. An 'active' group always has its
    own routine clock, so it always has a next wake — and if its subtree
    collapses, its OWN T4 fires. From the parent's side that is correctly
    still in flight.

    …unless the OWNER opened it (`_NOT_HUMAN_OPENED`): a person's
    Delegate does not hand the parent's line to the child, so the child
    working is not the parent waiting.

    The precise notion of "an inject batch is still in flight", shared by the
    stall predicate (`is_problem_stalled` condition 4) and the T0 first_launch
    suppression (`problems_needing_t0`). REPLACES the old blanket "any
    NULL-outcome batch row exists" test that both used: once `shelved` stopped
    settling its inject (it is reopenable / parked — see
    `propagate_inject_outcome_from_goal`), a shelved-produced inject stays NULL
    forever, so the blanket test would suppress T0/T4 forever (a permanent
    wedge — the Phase 11 disease). Only ACTIVE produced work counts as
    in-flight; a freshly-committed inject is additionally covered by its
    enqueued worker (queue row) in the stall predicate's condition 3.

    2026-07-09 (putnam_2025_b6 silent idle): a bare `status='attempting'`
    check was status-SHALLOW — a Forward-Inject's produced goal sat
    `attempting` while its entire subtree was parked (strategies all
    dead/'stalled', zero open, nothing queued), so cond-4 suppressed T4
    forever while the park machinery waited for a Strategist that could
    never wake (mutual deadlock; 12 such NULL rows corpus-wide). Both
    branches now recurse: `attempting` counts only with a live frontier.
    This only LOOSENS suppression — every previously-inactive state stays
    inactive."""
    for row in conn.execute(
        "SELECT g.id AS gid, g.status AS st FROM strategist_decisions sd"
        " JOIN goals g ON g.id = sd.produced_goal_id"
        " WHERE sd.problem = ? AND sd.decision_kind IN " + _BATCH_KINDS_SQL +
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        + _group_clause(group_id),
        _group_args(problem, group_id),
    ).fetchall():
        st = str(row["st"])
        if st == "open":
            return True
        if st == "attempting" and _subtree_has_live_frontier(
                conn, int(row["gid"])):
            return True
    for row in conn.execute(
        "SELECT g.id AS gid, g.status AS st FROM strategist_decisions sd"
        " JOIN strategies s ON s.id = sd.produced_strategy_id"
        " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        " JOIN goals g ON g.id = ss.subgoal_id"
        " WHERE sd.problem = ? AND sd.decision_kind IN " + _BATCH_KINDS_SQL +
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        "   AND s.status = 'proposed'" + _group_clause(group_id),
        _group_args(problem, group_id),
    ).fetchall():
        st = str(row["st"])
        if st in ("open", "pending_strategist_review"):
            return True
        if st == "attempting" and _subtree_has_live_frontier(
                conn, int(row["gid"])):
            return True
    return conn.execute(
        "SELECT 1 FROM strategist_decisions sd"
        " JOIN groups gr ON gr.id = sd.produced_group_id"
        " WHERE sd.problem = ? AND sd.decision_kind IN " + _BATCH_KINDS_SQL +
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        "   AND gr.status = 'active'" + _NOT_HUMAN_OPENED
        + _group_clause(group_id) + " LIMIT 1",
        _group_args(problem, group_id),
    ).fetchone() is not None


def has_live_inflight_inject(conn: sqlite3.Connection, problem: str, *,
                             group_id: "int | None" = None) -> bool:
    """True iff `problem` has a NULL-outcome Inject decision that is still
    LIVE in the sense the Strategist anti-idle gate needs: something will
    move WITHOUT a Strategist wake.

      * `produced_goal_id` AND `produced_strategy_id` both NULL → live.
        The worker is still PRODUCING (a Forward before lemma
        registration) — this is the original reason this predicate is
        broader than the stall-side active-check, and it must survive
        every narrowing (suppression sites calling this have no
        in-flight-worker visibility).
      * produced goal / proposed strategy's subgoals → live iff their
        subtree has a "dispatch" frontier (`_subtree_has_live_frontier`):
        an `open` goal (BFS dispatches) or a queued worker (queue row).

    2026-07-11 (b6 wake-pump livelock): the old blanket "NULL and not
    shelved-produced" test was SELF-REFERENTIAL at the gate — injects
    whose produced goals sat `pending_strategist_review` (or `attempting`
    over a fully-parked subtree) counted as live, so the very goals that
    pump T2 review wakes also opened the gate's escape hatch, and
    EmitDirective-only batches passed forever (301 spawns / 2.05M output
    tokens in 5h). A goal waiting on the Strategist is NOT "something
    that moves without you" when the reader IS the Strategist. The
    third recurrence of the P13 "two predicates disagree on one state"
    disease (4284 spin → cond-4 deadlock → this); the alignment is now
    pinned by test_stall_false_active.py's invariant tests.

    v35 — an ACTIVE discussion group is live here too, and it is the one
    case where "moves without a Strategist wake" has to be read as
    "without THIS Strategist's wake": a delegated group moves by its OWN
    seat and its OWN routine clock. Without this arm a parent that
    correctly delegated everything would have its `Noop` rejected on a
    blocked root and be forced to invent work beside the burden it just
    handed off. Note the group arm cannot ride the `gid IS NULL AND sid
    IS NULL` branch above — that branch means "a worker is still
    producing", which is a different claim that happens to give the same
    answer today and would silently stop doing so the moment a Delegate
    carried an anchor.

    And the group arm reads THIS seat's own delegations only
    (`_NOT_HUMAN_OPENED`): a group the OWNER opened moves without this
    Strategist, but it did not take this Strategist's burden with it, so
    it is not an escape hatch for a `Noop` here."""
    if conn.execute(
        "SELECT 1 FROM strategist_decisions sd"
        " JOIN groups gr ON gr.id = sd.produced_group_id"
        " WHERE sd.problem = ? AND sd.decision_kind IN " + _BATCH_KINDS_SQL +
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        "   AND gr.status = 'active'" + _NOT_HUMAN_OPENED
        + _group_clause(group_id) + " LIMIT 1",
        _group_args(problem, group_id),
    ).fetchone() is not None:
        return True
    for row in conn.execute(
        "SELECT sd.produced_goal_id AS gid,"
        "       sd.produced_strategy_id AS sid"
        " FROM strategist_decisions sd"
        " WHERE sd.problem = ? AND sd.decision_kind = 'Inject'"
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        + _group_clause(group_id),
        _group_args(problem, group_id),
    ).fetchall():
        if row["gid"] is None and row["sid"] is None:
            return True  # worker still producing — nothing to recurse on
        if row["gid"] is not None and _subtree_has_live_frontier(
                conn, int(row["gid"]), frontier="dispatch"):
            return True
        if row["sid"] is not None:
            for sub in conn.execute(
                "SELECT ss.subgoal_id AS gid FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " WHERE s.id = ? AND s.status = 'proposed'",
                (int(row["sid"]),),
            ).fetchall():
                if _subtree_has_live_frontier(
                        conn, int(sub["gid"]), frontier="dispatch"):
                    return True
    return False


# ------------------------------------------- a batch step's two states
#
# `outcome IS NULL` says "nobody has written a result", and that is TWO
# states, not one: a worker is still computing, or the Strategist PARKED
# the product and no worker exists any more. The second is by design —
# `shelved` stopped settling an inject on 2026-06-15 (P13 4284: settling
# it re-fired `inject_batch_done` on every park), and a 'stalled'
# strategy reaches the same shape. So every reader that spelled "in
# flight" as `outcome IS NULL` told the Strategist its own parked goal
# was still running: SP7 2026-09-03 listed batches `e9cbf9d9` → g10712
# and `576886b8` → g10719 as "Still running … do not re-dispatch them"
# with zero live pipelines, and the Strategist re-parked g10712 twice
# (revs 23 and 25) citing "exact batch e9cbf9d9 remains in flight".
#
# The structured signal is the produced work, the same one the stall
# predicates read. These helpers are the single place that spells it.

def _subtree_has_running_worker(conn: sqlite3.Connection,
                                goal_id: int) -> bool:
    """An unfinished `pipelines` row over this subtree — a worker
    PROCESS is alive on one of its goals or on a strategy of one.

    Complements `_subtree_has_live_frontier`, whose queue arm reads
    `target_kind='Goal'` rows only: a Verify running against a strategy
    of an `attempting` goal has no goal-kind row to be found by."""
    return conn.execute(
        _SUBTREE_CTE +
        " SELECT 1 FROM pipelines p WHERE p.finished_at IS NULL"
        "   AND ((p.target_kind = 'Goal'"
        "         AND CAST(p.target_id AS INTEGER) IN (SELECT gid FROM sub))"
        "     OR (p.target_kind = 'Strategy'"
        "         AND CAST(p.target_id AS INTEGER) IN ("
        "               SELECT s.id FROM strategies s"
        "                WHERE s.goal_id IN (SELECT gid FROM sub))))"
        " LIMIT 1", (goal_id,)).fetchone() is not None


def _produced_goal_is_live(conn: sqlite3.Connection, goal_id: int) -> bool:
    """Work is moving on this produced goal without a Strategist: an
    `open` node BFS will dispatch, a queued/leased worker, or a running
    pipeline — anywhere in its subtree, the goal itself included."""
    return (_subtree_has_live_frontier(conn, goal_id, frontier="dispatch")
            or _subtree_has_running_worker(conn, goal_id))


def _step_is_running(conn: sqlite3.Connection, row: sqlite3.Row) -> bool:
    """Is this outcome-NULL batch step's work actually MOVING?

    Deliberately generous in one direction only: a step that has
    produced nothing yet counts as running, because the worker has not
    reached its artifact and there is nothing to read (the same arm
    `has_live_inflight_inject` opens with; a worker that died there is
    recovered by `null_inject_redispatch_specs`, not by this reader)."""
    gid, sid = row["produced_goal_id"], row["produced_strategy_id"]
    grp = row["produced_group_id"]
    if gid is None and sid is None and grp is None:
        return True
    if queue_has_decision(conn, int(row["id"])):
        return True
    if grp is not None:
        g = conn.execute("SELECT status FROM groups WHERE id = ?",
                         (int(grp),)).fetchone()
        if g is not None and str(g["status"]) == "active":
            return True
    if gid is not None and _produced_goal_is_live(conn, int(gid)):
        return True
    if sid is not None:
        if conn.execute(
            "SELECT 1 FROM pipelines WHERE target_kind = 'Strategy'"
            "   AND CAST(target_id AS INTEGER) = ? AND finished_at IS NULL"
            " LIMIT 1", (int(sid),)).fetchone() is not None:
            return True
        for sub in conn.execute(
            "SELECT ss.subgoal_id AS gid FROM strategies s"
            " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
            " WHERE s.id = ? AND s.status = 'proposed'", (int(sid),),
        ).fetchall():
            if _produced_goal_is_live(conn, int(sub["gid"])):
                return True
    return False


_OPEN_STEP_SQL = (
    "SELECT d.id, d.batch_id, d.group_id AS grp, d.decision_kind,"
    " d.brief, d.updated_at, d.actor, d.produced_goal_id,"
    " d.produced_strategy_id,"
    " d.produced_group_id, tg.slug AS target_slug,"
    " tg.status AS target_status, pg.slug AS produced_slug,"
    " pg.status AS goal_status, pg.updated_at AS produced_at,"
    " ps.status AS strategy_status, pgr.status AS group_status"
    " FROM strategist_decisions d"
    " LEFT JOIN goals tg ON tg.id = d.target_id"
    " LEFT JOIN goals pg ON pg.id = d.produced_goal_id"
    " LEFT JOIN strategies ps ON ps.id = d.produced_strategy_id"
    " LEFT JOIN groups pgr ON pgr.id = d.produced_group_id"
    " WHERE d.outcome IS NULL AND d.batch_id IS NOT NULL"
    "   AND d.decision_kind IN " + _BATCH_KINDS_SQL
)


def open_batch_steps(conn: sqlite3.Connection,
                     problem: str) -> "list[dict]":
    """Every batch step on `problem` whose `outcome` is still NULL, each
    classified `running` (work is moving without you) or PARKED (its
    product is shelved / stalled / closed — no worker exists and only
    the Strategist can move it).

    `human_delegate` is a THIRD reading of a running step, not a fourth
    state: the work moves, but it moves on the OWNER's line, not the
    reading group's (`_NOT_HUMAN_OPENED`). Kept as a flag rather than
    folded into `running` because the two surfaces need both halves —
    "it is not parked" and "it is not yours to wait for".

    Problem-wide on purpose: the batch surfaces show a group its own
    hashes and a COUNT of the others', so the caller filters on `grp`.
    Newest batch activity first, steps in commit order within a batch."""
    steps: "list[dict]" = []
    for r in conn.execute(_OPEN_STEP_SQL + " AND d.problem = ?"
                          " ORDER BY d.batch_id, d.id", (problem,)):
        if r["produced_goal_id"] is not None:
            ref = f"g{int(r['produced_goal_id'])}"
            status, at = r["goal_status"], r["produced_at"]
        elif r["produced_strategy_id"] is not None:
            ref = f"s{int(r['produced_strategy_id'])}"
            status, at = r["strategy_status"], None
        elif r["produced_group_id"] is not None:
            ref = f"group {int(r['produced_group_id'])}"
            status, at = r["group_status"], None
        else:
            ref = status = at = None
        steps.append({
            "decision_id": int(r["id"]), "batch_id": str(r["batch_id"]),
            "grp": r["grp"], "decision_kind": str(r["decision_kind"]),
            "brief": r["brief"], "target_slug": r["target_slug"],
            "target_status": r["target_status"],
            "produced_ref": ref, "produced_slug": r["produced_slug"],
            "produced_status": None if status is None else str(status),
            "produced_at": None if at is None else str(at),
            "updated_at": str(r["updated_at"] or ""),
            "running": _step_is_running(conn, r),
            "human_delegate": (r["produced_group_id"] is not None
                               and str(r["actor"] or "") == "human"),
        })
    steps.sort(key=lambda s: s["updated_at"], reverse=True)
    return steps


def batch_has_running_step(conn: sqlite3.Connection,
                           batch_id: str) -> bool:
    """True iff this batch still has a step whose work is MOVING — the
    promise-liveness test shared by `transitions._awaiting_promised_
    batch` and the pending-reopen section's complement. A batch whose
    remaining steps are all parked is as done as it will get without a
    Strategist decision."""
    for r in conn.execute(_OPEN_STEP_SQL + " AND d.batch_id = ?",
                          (str(batch_id),)):
        if _step_is_running(conn, r):
            return True
    return False


def goal_reviewed_at_current_attempts(conn: sqlite3.Connection,
                                      goal_id: int) -> bool:
    """True iff a strategist decision already targeted `goal_id` since its
    last recorded attempt — i.e. the over-budget T2 review for THIS
    attempts value has been answered. The bfs over-threshold guard uses
    this to send a goal to review ONCE per attempts value instead of
    re-escalating every tick after the Strategist answered (e.g. with a
    Reopen that keeps the goal alive but changes nothing bfs can see —
    b6 2026-07-10 wake pump, fuel line #2). Derived entirely from
    decision history + dead_attempts timestamps: zero new state, immune
    to daemon restarts (an in-memory flag would re-escalate once per
    restart). Fails toward SKIPPING the escalation (quiet hold), never
    toward re-spamming."""
    return conn.execute(
        "SELECT 1 FROM strategist_decisions"
        " WHERE target_id = ?"
        "   AND created_at >= COALESCE("
        "     (SELECT MAX(ts) FROM dead_attempts"
        "       WHERE target_id = ? AND target_kind = 'Goal'), '')"
        " LIMIT 1",
        (int(goal_id), int(goal_id)),
    ).fetchone() is not None


def is_human_parked(conn: sqlite3.Connection, goal_id: int) -> bool:
    """True iff a PERSON's last word on this goal was a ConfirmShelve
    (human_interface_design.md §3.2).

    Read on its own by the readers that must treat the two parks
    differently rather than merely notice that the goal is parked: the
    citation gate rejects a cite of a human park (a machine park is a
    WAIT the citer can queue behind; a person's park promises nothing to
    wait for), and `is_confirm_shelve_parked` builds on it.
    """
    row = conn.execute(
        "SELECT decision_kind FROM strategist_decisions"
        " WHERE target_id = ? AND actor = 'human'"
        " ORDER BY id DESC LIMIT 1",
        (int(goal_id),),
    ).fetchone()
    return row is not None and str(row["decision_kind"]) == "ConfirmShelve"


def is_confirm_shelve_parked(conn: sqlite3.Connection, goal_id: int) -> bool:
    """True iff `goal_id` is shelved BECAUSE the Strategist ConfirmShelve'd it
    (a deliberate PARK pending an in-flight prereq batch), as opposed to being
    cascade-shelved (it lost its last live path when a sibling strategy died).

    The distinction matters for citation/reuse revival: a cascade-shelved goal
    is safe to reopen the moment something cites it (it just needs a fresh live
    path — the original agent_feedback T8 motivation). A ConfirmShelve-parked
    goal is NOT: the framework FORCES every ConfirmShelve to be paired with an
    Inject (strategist.py — "build the missing tool the shelved goal needed"),
    so it is parked precisely until its injected prerequisites prove and the
    Strategist re-engages it via inject_batch_done. Reopening it early (on an
    unrelated cite) re-dispatches it before its prereqs exist → it re-fails →
    re-shelves → a mini-spin, and short-circuits the Strategist-owned lifecycle.

    Signal (no extra column needed): ConfirmShelve writes a strategist_decisions
    row with target_id=goal; a later re-engagement — Inject(Backward/Builder,
    target=goal) or a legacy Reopen — also writes target_id=goal. So the goal is
    currently ConfirmShelve-parked iff the MOST-RECENT decision targeting it is a
    ConfirmShelve (a later targeting Inject/Reopen means it was un-parked; a
    subsequent cascade-shelve writes no row, leaving that Inject/Reopen as the
    latest → correctly read as NOT ConfirmShelve-parked). Forward reuse-repoints
    set produced_goal_id, not target_id, so they never count as un-parking.

    v48 (human_interface_design.md §3.2) — a HUMAN ConfirmShelve is a
    TERMINAL park, and the difference is not cosmetic. The machine's park
    is a WAIT: it is paired with an Inject and ends when the Strategist
    targets the goal again, which is exactly why a machine redispatch
    un-parks it. A person's park is the one legal "stop" in a framework
    whose whole design is that it never stops itself, and it carries no
    paired Inject to wait for — so a later MACHINE decision on the goal
    must not lift it. Only the human reverses the human: the rule below
    reads the latest decision BY THE HUMAN first, and falls through to
    the machine rule when the person's last word was not a park."""
    if is_human_parked(conn, goal_id):
        return True
    row = conn.execute(
        "SELECT decision_kind FROM strategist_decisions"
        " WHERE target_id = ? ORDER BY id DESC LIMIT 1",
        (int(goal_id),),
    ).fetchone()
    return row is not None and str(row["decision_kind"]) == "ConfirmShelve"


def is_problem_stalled(conn: sqlite3.Connection, problem: str, *,
                       running: "set[tuple] | None" = None) -> bool:
    """True iff `problem` is structurally STALLED:

      1. no committed `Ingest` (Phase 6: the terminal judgment is the
         Strategist's Ingest, not the root's status — a proved-root
         problem whose Ingest hasn't been committed is stalled-when-idle
         precisely so the Strategist wakes to commit it; a FRESH problem
         with nothing dispatchable yet is stalled precisely so the wake
         bootstraps the first Inject — first_launch's replacement),
      2. zero DISPATCHABLE open goals — open goals reachable from the
         root ∪ detached seed via 'proposed' / 'succeeded' strategies.
         An ORPHANED open goal (its strategy chain died) is NOT
         dispatchable, so it does NOT count; a raw `status='open'` probe
         would wrongly mask the stall.
      3. no in-flight Backward / Builder / Forward worker (queue + the
         optional in-memory `running` set).
      4. no NULL-outcome Inject whose produced work is still ACTIVE (an
         open/attempting produced goal, or a 'proposed' produced strategy
         with >=1 alive subgoal). This SUBSUMES the old blanket "any
         NULL-outcome inject batch suppresses" pre-filter that lived in
         `problems_stalled`. The narrower active-check is what lets a
         SHELVED-produced NULL inject (outcome stays NULL forever now that
         shelved no longer settles — see propagate_inject_outcome_from_goal)
         STOP suppressing T4; the blanket pre-filter would have wedged the
         problem forever instead (the Phase 11 disease).

    SINGLE SOURCE OF TRUTH for the stall signal, shared by
    `problems_stalled` (T4 enqueue) and `_section_stall_warning`
    (Strategist Context.md). The two MUST agree: if T4 fires a Strategist
    on a stall whose warning the Strategist's context then fails to
    surface, the Strategist Noop-confirms, the problem re-stalls, and T4
    re-fires → a Strategist livelock (P13 2026-06-13: the two had diverged
    on raw vs reachable open-goal counting — fixing one without the other
    turned a clean give-up into an EmitDirective spin). `running` is the
    dispatcher's live set; omit it (context-compile has none) for a
    queue-only in-flight check (harmless brief false-positive while a
    worker is mid-spawn)."""
    # 1. committed Ingest → terminal, never stalled. (This also covers the
    #    sign-off pause: `_commit_ingest` stamps `ingested_at` before the
    #    human approves, so T4 doesn't re-wake the Strategist into
    #    re-Ingesting while the pause is pending. `reject-ingest` clears
    #    the stamp, putting the problem back on the live path.)
    if problem_ingested(conn, problem):
        return False
    # 2. any DISPATCHABLE (alive-reachable) open goal → not stalled.
    # Phase 6 — shared seed (root ∪ detached): the old root-only copy
    # silently dropped detached Forward goals, so a problem whose only
    # open work was a sorry-bearing Forward goal read as stalled here
    # while `open_goals` happily dispatched it (latent divergence; root
    # always existed so it never fired — pure-NL makes it load-bearing).
    if conn.execute(
        f"WITH RECURSIVE {ALIVE_CTE_PER_PROBLEM}"
        " SELECT 1 FROM goals"
        " WHERE problem = ? AND status = 'open' AND id IN alive LIMIT 1",
        (problem, problem, problem),
    ).fetchone() is not None:
        return False
    # 3. any in-flight Backward / Builder / Forward worker (queue + running)
    #    — the QUIET guard, named + extracted (FSM P3): stalled ⇒ quiet,
    #    quiet alone is NOT stalled (dispatchable work may exist).
    if not problem_quiet(conn, problem, running=running):
        return False
    # 4. a NULL-outcome Inject whose produced work is genuinely ACTIVE keeps
    #    the problem in-flight (the batch is still resolving; inject_batch_done
    #    will wake Strategist). REPLACES the old blanket batch-suppression
    #    pre-filter — a NULL inject whose produced goal got SHELVED is parked,
    #    not in flight, and must NOT suppress T4 (else permanent wedge).
    if has_active_inflight_inject(conn, problem):
        return False
    return True


def is_group_stalled(conn: sqlite3.Connection, problem: str,
                     group_id: int, *,
                     running: "set[tuple] | None" = None) -> bool:
    """True iff THIS GROUP is structurally stalled (v35).

    The group-scoped mirror of `is_problem_stalled`, and it exists for a
    direction the parent-side quiet rule does not cover: when a CHILD
    group runs out of moves, the problem-wide predicate either says
    nothing (a sibling is busy, so the problem is not stalled) or wakes
    the wrong group. Every condition narrows to the group's own slice of
    the tree:

      1. the group is still `active` and its problem has not Ingested
         — a finished group is done, never stalled;
      2. zero DISPATCHABLE open goals in its slice (alive-reachable, so
         an orphan does not mask the stall — same reasoning as the
         problem-level condition 2);
      3. no in-flight worker on a goal in its slice;
      4. no NULL-outcome batch decision THIS group authored whose
         produced work is still active.

    With one group per problem this returns exactly what
    `is_problem_stalled` returns, which is what
    `test_group_stall_matches_problem_stall_when_alone` pins — the two
    must not drift, for the reason recorded on
    `has_active_inflight_inject`.
    """
    from .. import groups as _groups
    row = _groups.get(conn, int(group_id))
    if row is None or str(row["status"]) != _groups.ACTIVE:
        return False
    if problem_ingested(conn, problem):
        return False
    slice_ids = _groups.goal_ids_in_group(conn, problem, int(group_id))
    if slice_ids:
        marks = ",".join("?" * len(slice_ids))
        if conn.execute(
            f"WITH RECURSIVE {ALIVE_CTE_PER_PROBLEM}"
            f" SELECT 1 FROM goals"
            f" WHERE problem = ? AND status = 'open' AND id IN alive"
            f"   AND id IN ({marks}) LIMIT 1",
            (problem, problem, problem, *slice_ids),
        ).fetchone() is not None:
            return False
        if not _group_quiet(conn, slice_ids, running=running):
            return False
    # Mint jobs are problem-targeted (no goal id yet), so they cannot be
    # attributed to a slice — attribute them by the DECISION's group.
    if conn.execute(
        "SELECT 1 FROM queue q"
        " LEFT JOIN strategist_decisions d ON d.id = q.decision_id"
        " WHERE q.problem = ? AND q.kind IN ('Forward','Formalizer')"
        "   AND q.target_kind = 'Problem'"
        "   AND (d.group_id IS NULL OR d.group_id = ?) LIMIT 1",
        (problem, int(group_id)),
    ).fetchone() is not None:
        return False
    return not has_active_inflight_inject(conn, problem,
                                          group_id=int(group_id))


def _group_quiet(conn: sqlite3.Connection, goal_ids: "set[int]", *,
                 running: "set[tuple] | None" = None) -> bool:
    """`problem_quiet` narrowed to a set of goals (v35)."""
    if not goal_ids:
        return True
    marks = ",".join("?" * len(goal_ids))
    if conn.execute(
        f"SELECT 1 FROM queue WHERE target_kind = 'Goal'"
        f" AND kind IN ('Backward','Builder','Formalizer')"
        f" AND CAST(target_id AS INTEGER) IN ({marks}) LIMIT 1",
        tuple(goal_ids),
    ).fetchone() is not None:
        return False
    run = running or set()
    live = {str(t[0]) for t in run
            if len(t) >= 2 and t[1] in ("Backward", "Builder", "Formalizer")}
    return not any(str(g) in live for g in goal_ids)


def groups_stalled(conn: sqlite3.Connection, *,
                   scope: str | None = None,
                   running: "set[tuple] | None" = None
                   ) -> list[sqlite3.Row]:
    """Every active group matching the structural stall signal (v35)."""
    sql = ("SELECT g.id, g.problem FROM groups g"
           " JOIN problems p ON p.name = g.problem"
           " WHERE g.status = 'active' AND p.ingested_at IS NULL")
    _sc, args = scope_sql(scope, "g.problem")
    if _sc:
        sql += f" AND {_sc}"
    return [r for r in conn.execute(sql + " ORDER BY g.problem, g.id", args)
            if is_group_stalled(conn, str(r["problem"]), int(r["id"]),
                                running=running)]


def problem_quiet(conn: sqlite3.Connection, problem: str, *,
                  running: "set[tuple] | None" = None) -> bool:
    """Derived guard #2 of the problem FSM (design §4, formalized in
    P3 by operator ruling): True iff NO worker is in flight for
    `problem` (queue rows + the dispatcher's optional in-memory
    `running` set). This is `is_problem_stalled`'s condition 3,
    extracted so the wake-legality machinery and future readers name
    the same predicate. Formalizer merge: goal jobs ride kind
    'Formalizer' (target=goal id), mint jobs kind 'Formalizer' with
    target=problem name — both must count as in-flight (an in-flight
    mint read as a stall fired duplicate T4 wakes; review 07-27 #1).
    Legacy 'Backward'/'Builder'/'Forward' rows stay covered."""
    if conn.execute(
        "SELECT 1 FROM queue q"
        " JOIN goals g ON g.id = CAST(q.target_id AS INTEGER)"
        " WHERE g.problem = ? AND q.target_kind = 'Goal'"
        " AND q.kind IN ('Backward','Builder','Formalizer') LIMIT 1",
        (problem,),
    ).fetchone() is not None:
        return False
    if conn.execute(
        "SELECT 1 FROM queue WHERE target_id = ?"
        " AND kind IN ('Forward','Formalizer') LIMIT 1",
        (problem,),
    ).fetchone() is not None:
        return False
    run = running or set()
    if any(len(t) >= 2 and t[1] in ("Forward", "Formalizer")
           and t[0] == problem for t in run):
        return False
    bw_bu_ids = {t[0] for t in run
                 if len(t) >= 2 and t[1] in ("Backward", "Builder",
                                             "Formalizer")}
    if bw_bu_ids:
        placeholders = ",".join("?" * len(bw_bu_ids))
        if conn.execute(
            f"SELECT 1 FROM goals WHERE problem = ?"
            f" AND CAST(id AS TEXT) IN ({placeholders}) LIMIT 1",
            (problem, *bw_bu_ids),
        ).fetchone() is not None:
            return False
    return True


def problems_stalled(conn: sqlite3.Connection, *,
                     scope: str | None = None,
                     running: "set[tuple[str, str]] | None" = None,
                     ) -> list[str]:
    """Return problem names matching the structural stall signal:

      1. no committed Ingest (Phase 6 — the problem terminal state)
      2. zero `open_goals` reachable in scope (BFS has nothing to dispatch)
      3. no in-flight Backward / Builder / Forward worker on this problem
         (neither in the dispatcher's `running` set nor in the queue)
      4. no NULL-outcome Inject whose produced work is still ACTIVE

    Conditions 2-4 are evaluated by `is_problem_stalled` (the shared
    single-source predicate); the candidate SQL here only applies
    condition 1 (not-yet-ingested). When all four hold, the dispatcher
    can dispatch nothing on this
    problem until Strategist intervenes. Routine T1 fires every 60 min
    which is too slow (polar 2026-05-23: 174 min stall before budget
    exhaust). T4 trigger uses this signal to enqueue Strategist
    immediately. Pairs with `_section_stall_warning` in Strategist
    Context.md which re-checks the signal and surfaces a header so
    Strategist knows not to Noop. A FRESH problem (no dispatchable work
    yet) is deliberately stalled — the resulting wake bootstraps the
    first Inject (first_launch's Phase 6 replacement).

    `running`: caller's live in-memory set of (target_id, kind) tuples.
    Optional — when omitted the check uses queue rows only (may
    false-positive briefly while a worker is mid-spawn but not yet in
    the queue; the false-positive is harmless: Strategist enqueue is
    idempotent via `is_in_queue` dedup at the call site).
    """
    # Candidate pre-filter is not-yet-ingested ONLY. In-flight Inject
    # suppression is NO LONGER a blanket "any NULL-outcome batch row"
    # pre-filter here — that wedged the problem forever once `shelved`
    # stopped settling (a shelved-produced inject stays NULL forever).
    # It now lives in `is_problem_stalled` as a precise ACTIVE-check
    # (condition 4: suppress only while the inject's produced work is
    # open/attempting or a proposed strategy with an alive subgoal),
    # keeping T4 and `_section_stall_warning` in lockstep automatically.
    sql = (
        "SELECT p.name"
        " FROM problems p"
        " WHERE p.ingested_at IS NULL"
    )
    _sc, args = scope_sql(scope, "p.name")
    if _sc:
        sql += f" AND {_sc}"
    sql += " ORDER BY p.name"
    candidates = list(conn.execute(sql, args))
    if not candidates:
        return []

    # Per-candidate structural stall test via the shared single-source
    # predicate (keeps T4 and `_section_stall_warning` in lockstep). The
    # candidate SQL above only applied the not-yet-ingested pre-filter;
    # the in-flight-Inject active-check is condition 4 inside the predicate.
    run = running or set()
    return [str(r["name"]) for r in candidates
            if is_problem_stalled(conn, str(r["name"]), running=run)]


def problem_has_awaiting_human(conn: sqlite3.Connection, problem: str) -> bool:
    """True iff this problem has a `strategist_decisions` row with
    `outcome='awaiting_human'`. While true the dispatcher should pause
    all Strategist + Backward + Builder + Forward dispatch on this
    problem until operator resolves the row (handled in dispatcher's
    pop loop / strategist_triggers)."""
    try:
        row = conn.execute(
            "SELECT 1 FROM strategist_decisions"
            " WHERE problem = ? AND outcome = 'awaiting_human' LIMIT 1",
            (problem,),
        ).fetchone()
    except sqlite3.OperationalError:
        # Pre-Phase 2 schema (table missing).
        return False
    return row is not None


def scoped_problem_names(conn: sqlite3.Connection, scope: str) -> list[str]:
    """Distinct problem names that have at least one goal and match the
    SQL LIKE `scope` pattern. The dispatcher's periodic TREE.md refresh
    uses this so a `--scope` run only re-renders + atomic-replaces the
    in-scope trees each tick, instead of churning all ~281 problems'
    TREE.md — on Windows the rapid replace of unrelated trees raised
    transient WinError 5 sharing violations (caught, but noise)."""
    _sc, _sa = scope_sql(scope)
    return [str(r[0]) for r in conn.execute(
        f"SELECT DISTINCT problem FROM goals WHERE {_sc or '1'}"
        " ORDER BY problem", _sa)]


def dispatchable_open_goals(conn: sqlite3.Connection,
                            *, scope: str | None = None
                            ) -> list[sqlite3.Row]:
    """`open_goals(scope)` minus goals whose problem is paused on an
    unresolved `RequestUserAmend` (`outcome='awaiting_human'`).

    bfs_refill silently skips awaiting_human problems, so their open
    goals can make no progress this run. The dispatcher's idle-exit
    check uses this (not raw `open_goals`) so a scoped daemon whose only
    in-scope problem is paused EXITS with a report instead of livelocking
    forever — 2026-06-12 P12 (stokes_induced_orient) was paused on a
    Defs.lean amend, but the unscoped `open_goals` saw brouwer's unrelated
    open goal and never exited, burning the periodic tree-write each tick
    and reading as a multi-hour hang."""
    goals = open_goals(conn, scope=scope)
    if not goals:
        return []
    problems = {str(g["problem"]) for g in goals}
    paused = {p for p in problems if problem_has_awaiting_human(conn, p)}
    if not paused:
        return goals
    return [g for g in goals if str(g["problem"]) not in paused]


def increment_goal_attempts(conn: sqlite3.Connection, goal_id: int) -> int:
    conn.execute(
        "UPDATE goals SET attempts = attempts + 1, updated_at = ? WHERE id = ?",
        (now(), goal_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT attempts FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()
    return int(row["attempts"]) if row else 0


