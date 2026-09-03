"""Commit (side-effect stage): `CommitOutcome`, every `_commit_*`
per-kind handler, and the `commit_decisions` / `commit_decision` /
`_commit_one` dispatch on top of them.

Split out of `strategist.py` 2026-08-28 (Phase B, B1) unchanged.
`_authoring_group` / `_group_retired_status` are imported back from
`verify.py`, their owning module: this module's own handlers consume
the same group-retired race-guard `verify.py`'s functions already
established.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ...core import dispatcher as _dispatcher
from ...state import db, transitions
from ...state import groups as _groups

from .model import Decision, _as_bool
from .verify import _authoring_group, _group_retired_status


# ---------------------------------------------------------------------
# Commit (side-effect stage)
# ---------------------------------------------------------------------

@dataclass
class CommitOutcome:
    """What commit_decision did — for the caller (run_strategist) to
    record into the pipeline's PipelineResult and dead_attempt rows.

    `decision_row_id`: id of the FIRST inserted strategist_decisions
      row in the batch (for callers that need a single canonical id).
      Full row id list in `batch_decision_row_ids`.
    `enqueued_forward`: True iff the commit emitted >= 1 mint Inject
      queue entry.
    `batch_id`: always non-None when the committed decision was Inject
      (every Inject — including N=1 — is a batch under the unified
      Phase 2.5 schema); None for non-Inject decision kinds.
    `batch_decision_row_ids`: row ids in `briefs` list order (length N
      for Inject; empty for non-Inject kinds).
    `final_outcome`: 'committed' (decision applied) / 'awaiting_human'
      (RequestUserAmend wrote .proposed_<file> + INSERT row, dispatcher
      blocks problem until operator resolves) / 'noop'.
    """
    decision_row_id: int
    enqueued_forward: bool = False
    final_outcome: str = "committed"
    batch_id: str | None = None
    batch_decision_row_ids: list[int] = field(default_factory=list)


#: Who authored the row. 'strategist' is every machine path; 'human' is
#: a command from `state/commands.py` (human_interface_design.md §3.2) —
#: a SEMANTIC field, not an audit label: the parked / revival / cascade
#: predicates each read it.
ACTOR_STRATEGIST = "strategist"
ACTOR_HUMAN = "human"

#: The dispatch band a person's Inject joins. The Strategist's own
#: Inject enqueues at 10, ahead of BFS's 2 — that is the machine
#: promoting its own next experiment. A human Inject "只進佇列、不插隊"
#: (§1.3, owner ruling 2026-09-02): it takes the ordinary band, so it
#: neither outranks the goals BFS already queued nor sinks below them.
_HUMAN_INJECT_PRIORITY = 2


def _commit_inject_batch(decision: Decision, conn: sqlite3.Connection,
                         *, problem: str, tick: int,
                         trigger_kind: str,
                         inject_batch_id: str | None = None,
                         step_index: int = 0,
                         batch_size: int = 1,
                         actor: str = ACTOR_STRATEGIST,
                         group_id: "int | None" = None) -> CommitOutcome:
    """Commit one Strategist Inject decision. Dispatches to the
    pipeline-specific helper.

    Batch semantics (unified across pipeline kinds): every Inject row
    carries a `batch_id`. The framework fires Strategist with
    `inject_batch_done` once every decision in the batch has reached
    a terminal outcome.

      - Forward outcome fills when the produced lemma reaches a
        terminal goal status (proved / disproved).
      - Backward outcome fills when the produced strategy reaches
        a terminal status (succeeded / dead / superseded).
      - Builder outcome fills when the target goal reaches terminal
        (Builder writes the proof directly into the goal's stub).

    Multi-decision callers pass `inject_batch_id` to share one UUID
    across the whole batch — including across pipeline kinds — so a
    single wake-up coalesces all completions.
    """
    # Shape-derived (update_plan_2026_07 #1): no target → mint a new
    # brick; target present → redispatch the goal to the Formalizer.
    if decision.target_id is None:
        return _commit_inject_forward(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, batch_id_override=inject_batch_id,
            step_index=step_index, batch_size=batch_size,
            actor=actor, group_id=group_id)
    return _commit_inject_redispatch(
        decision, conn, problem=problem, tick=tick,
        trigger_kind=trigger_kind, pipeline="Formalizer",
        batch_id_override=inject_batch_id,
        step_index=step_index, batch_size=batch_size,
        actor=actor, group_id=group_id)


def _commit_inject_forward(decision: Decision, conn: sqlite3.Connection,
                           *, problem: str, tick: int,
                           trigger_kind: str,
                           batch_id_override: str | None = None,
                           step_index: int = 0,
                           batch_size: int = 1,
                           actor: str = ACTOR_STRATEGIST,
                           group_id: "int | None" = None) -> CommitOutcome:
    """Mint variant — 1 brief → 1 row + 1 Formalizer enqueue
    (target_kind=Problem).

    `batch_id_override` lets a multi-decision call share one batch_id
    across all N mint Inject decisions so cascade fires a single
    `inject_batch_done` once every produced lemma terminates. Solo
    (single-decision) calls leave it None and get a fresh batch_id.
    """
    brief = decision.brief.strip()
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()
    row_payload = {
        "pipeline": "Formalizer",
        "step_index": step_index,
        "batch_size": batch_size,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief,"
        " reason, payload, batch_id, outcome, actor, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', ?, NULL, ?, ?, ?, ?, NULL, ?, ?, ?)",
        (problem, tick, trigger_kind, group_id, brief,
         decision.reason, json.dumps(row_payload, ensure_ascii=False),
         batch_id, actor, ts, ts),
    )
    row_id = int(cur.lastrowid)
    db.enqueue(
        conn, kind="Formalizer", target_id=problem,
        target_kind="Problem",
        priority=_HUMAN_INJECT_PRIORITY if actor == ACTOR_HUMAN else 10,
        decision_id=row_id, problem=problem,
    )
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=True,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def _commit_inject_redispatch(decision: Decision, conn: sqlite3.Connection,
                              *, problem: str, tick: int,
                              trigger_kind: str,
                              pipeline: str,
                              batch_id_override: str | None = None,
                              step_index: int = 0,
                              batch_size: int = 1,
                              actor: str = ACTOR_STRATEGIST,
                              group_id: "int | None" = None,
                              ) -> CommitOutcome:
    """Backward / Builder variant — 1 row + 1 enqueue on target goal.

    `brief` carries the agent's hint for the redispatch.

    Every Inject row carries a `batch_id` (a fresh UUID for solo
    commits, shared across the batch when multiple decisions commit
    together) so the framework can fire `inject_batch_done` once the
    batch's last decision reaches terminal — mirroring Forward.

    `produced_goal_id = target_id`: lets the goal-side propagation
    fill outcome when the target reaches a terminal goal status
    (Builder's intent is to prove the goal directly, so this is the
    canonical completion signal for Builder). For Backward the
    worker additionally sets `produced_strategy_id` after reserving
    its strategy id; outcome fills via whichever path resolves first
    (idempotent via the `outcome IS NULL` guard), so a Backward
    Inject whose injected strategy dies via cascade still surfaces a
    wake-up even while the target goal stays 'attempting' under a
    sibling.
    """
    target_id = int(decision.target_id)
    brief = decision.brief.strip()
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()
    row_payload = {
        "pipeline": pipeline,
        "step_index": step_index,
        "batch_size": batch_size,
        "target_goal_id": target_id,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief,"
        " reason, payload, batch_id, produced_goal_id, produced_kind,"
        " outcome, actor, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', ?, ?, ?, ?, ?, ?, ?, 'redispatch',"
        " NULL, ?, ?, ?)",
        (problem, tick, trigger_kind, group_id, target_id,
         brief, decision.reason,
         json.dumps(row_payload, ensure_ascii=False),
         batch_id, target_id, actor, ts, ts),
    )
    row_id = int(cur.lastrowid)

    # Force-reopen target so BFS / inject dispatch can run on it.
    # Auto-detach if the upward chain has died — same path Strategist
    # Reopen takes. `disproved` stays IN this list on purpose after
    # 2026-09-04: `verify_decision` now refuses a STRATEGIST Inject on
    # one, so the only Inject that still reaches here with that status
    # is a PERSON's (the human command path deliberately skips the
    # verifier, state/commands.py) — which is exactly the operator
    # repair the surviving ("disproved","open") edge is for.
    g = db.get_goal(conn, target_id)
    if g and str(g["status"]) in ("shelved", "pending_strategist_review",
                                   "frozen", "disproved"):
        transitions.apply_goal_transition(
            conn, target_id, "open", event="strategist_reopen")
        if _dispatcher._has_dead_strategy_in_chain(conn, target_id):
            db.set_goal_detached(conn, target_id, True)
        # Un-stall the upward chain (Phase 11): a parent strategy PARKED
        # as 'stalled' because this goal was its last settled sub-goal
        # returns to 'proposed', so the alive-DAG conducts through it again
        # and BFS can reach the just-reopened goal — otherwise it stays
        # orphaned. ('proposed' is non-terminal → no inject-outcome
        # re-propagation; the prior 'failed:stalled' record stands, the
        # fresh redispatch Inject below tracks the revived attempt.)
        for s in conn.execute(
            "SELECT s.id FROM strategies s"
            " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
            " WHERE ss.subgoal_id = ? AND s.status = 'stalled'",
            (target_id,),
        ).fetchall():
            transitions.apply_strategy_transition(
                conn, int(s["id"]), "proposed", event="strategist_unstall")

    # entry_kind pinning retired with the Formalizer merge: bfs_refill
    # and Inject now enqueue the SAME kind, so the in_flight(gid, kind)
    # guard structurally prevents the parallel-pipeline race the old
    # pin worked around (LU lu_step_assembly 2026-05-28).
    db.enqueue(
        conn, kind=pipeline, target_id=str(target_id),
        target_kind="Goal",
        priority=_HUMAN_INJECT_PRIORITY if actor == ACTOR_HUMAN else 10,
        decision_id=row_id, problem=problem,
    )
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def _commit_delegate(decision: Decision, conn: sqlite3.Connection,
                     *, problem: str, tick: int, trigger_kind: str,
                     group_id: "int | None",
                     batch_id_override: str | None = None,
                     step_index: int = 0,
                     batch_size: int = 1,
                     actor: str = ACTOR_STRATEGIST) -> CommitOutcome:
    """Open a sub-group and hand it the charter (v35).

    The row rides the same batch as this wake's Injects, and its
    `produced_group_id` is the batch's THIRD artifact form: the outcome
    fills when the group reaches a terminal status, so a batch that
    dispatched both a Formalizer and a group wakes the parent only once
    BOTH are done.

    Two shapes:
      * no target — the main one. A burden delegated while writing the
        Proof; the group starts from prose and mints its own bricks,
        exactly like a pure-NL problem.
      * `target_goal_id` — the rescue shape. The goal becomes the
        group's ANCHOR and goes `attempting`: not dispatchable by BFS,
        but alive, which is what lets the parent stay quiet (§5 of the
        design doc).

    Unlike an Inject, no worker is enqueued — the group's executor is
    its own Strategist seat. That seat IS queued here rather than left
    to the routine clock: a fresh group's clock is NULL, which the T1
    selector reads as "due one full interval after daemon start", and a
    just-delegated burden should not wait up to two hours to begin.
    """
    parent = _authoring_group(conn, problem, group_id)
    if parent is None:                       # verify already rejected this
        raise RuntimeError(f"Delegate on {problem!r} has no authoring group")
    charter = str(decision.brief).strip()
    target = (int(decision.target_id)
              if decision.target_id is not None else None)
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()

    # Copy-on-open (2026-08-11): conventions no longer walk the ancestor
    # chain, so this snapshot is the only way a footgun learned up here
    # reaches a group opened now. Taken at open time and never refreshed
    # — the child owns the subject from its first `## Conventions` on.
    from ...state import programme as _programme
    new_gid = _groups.open_group(
        conn, problem=problem, parent_group_id=int(parent["id"]),
        charter=charter, anchor_goal_id=target,
        conventions_seed=_programme.conventions_for_group(
            conn, problem, int(parent["id"])))
    row_payload = {
        "step_index": step_index,
        "batch_size": batch_size,
        "group_id": new_gid,
    }
    if target is not None:
        row_payload["target_goal_id"] = target
    # Guidance hand-off (2026-08-19 reshape): lives on THIS audit row;
    # the child's context reads it back through `groups.opened_by` —
    # no schema change, and it never touches the judged charter.
    if decision.payload.get("brief"):
        row_payload["brief"] = str(decision.payload["brief"])
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief, reason,"
        " payload, batch_id, produced_group_id, produced_kind, outcome,"
        " actor, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Delegate', ?, ?, ?, ?, ?, ?, ?, 'group',"
        " NULL, ?, ?, ?)",
        (problem, tick, trigger_kind, int(parent["id"]), target, charter,
         decision.reason, json.dumps(row_payload, ensure_ascii=False),
         batch_id, new_gid, actor, ts, ts),
    )
    row_id = int(cur.lastrowid)
    conn.execute("UPDATE groups SET opened_by = ? WHERE id = ?",
                 (row_id, new_gid))
    if target is not None:
        # `attempting` — alive (so the parent's wait is legal) but not
        # dispatchable by BFS. See the status table in the design doc:
        # `frozen` and `shelved` are both PARKED and would let T4 wake
        # the parent on every tick.
        g = db.get_goal(conn, target)
        if g is not None and str(g["status"]) != "attempting":
            transitions.apply_goal_transition(
                conn, target, "attempting", event="delegate_anchor")
    _dispatcher._enqueue_strategist(conn, new_gid, problem, priority=10)
    conn.commit()
    print(f"[delegate] group {new_gid} opened under {parent['id']} "
          f"({problem}): {charter[:80]}", flush=True)
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def _commit_return_to_parent(decision: Decision, conn: sqlite3.Connection,
                             *, problem: str, tick: int,
                             trigger_kind: str,
                             group_id: "int | None",
                             actor: str = ACTOR_STRATEGIST) -> CommitOutcome:
    """Hand the charter back up (v35).

    Setting the group's status to 'returned' is what fills the parent's
    `Delegate` outcome and completes its batch — the parent is woken by
    the ordinary batch-done relay, not by anything special here.

    The anchor of a rescue-shape group goes back to `shelved`: parked,
    revivable, and its cascade parks the failed subtree with it. The
    parent decides what happens next; that is the whole point of handing
    it back rather than deciding alone.
    """
    me = _authoring_group(conn, problem, group_id)
    if me is None or _groups.is_top(me):     # verify already rejected this
        raise RuntimeError(
            f"ReturnToParent on {problem!r} has no parent group")
    flavour = str(decision.payload.get("flavour"))
    ts = db.now()
    payload = dict(decision.payload)
    payload["group_id"] = int(me["id"])
    payload["charter"] = str(me["charter"])
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, reason,"
        " payload, produced_group_id, outcome, outcome_detail,"
        " actor, created_at, updated_at)"
        " VALUES (?, ?, ?, 'ReturnToParent', ?, ?, ?, ?, ?, 'committed',"
        " ?, ?, ?, ?)",
        (problem, tick, trigger_kind, int(me["id"]),
         decision.target_id, decision.reason,
         json.dumps(payload, ensure_ascii=False), int(me["id"]),
         flavour, actor, ts, ts),
    )
    row_id = int(cur.lastrowid)
    anchor = me["anchor_goal_id"]
    if anchor is not None:
        g = db.get_goal(conn, int(anchor))
        if g is not None and str(g["status"]) in (
                "open", "attempting", "pending_strategist_review", "frozen"):
            transitions._set_goal_terminal_and_propagate(
                conn, int(anchor), "shelved")
            transitions._propagate_shelve(conn, int(anchor))
    # Terminal status LAST: it fills the parent's Delegate outcome and
    # may fire the batch-done wake, so everything the parent will read
    # must already be written.
    _groups.set_status(conn, int(me["id"]), "returned",
                       event="group_returned")
    if flavour == "refuted":
        # A refutation cannot wait for the batch. `refuted` means a step
        # of the PARENT's Proof is now kernel-false, so every sibling
        # still running under that Proof is working on an invalidated
        # premise — and siblings dispatched in the same batch keep the
        # batch open, so the ordinary relay would leave the parent
        # asleep for up to a full routine interval. Same reasoning, and
        # the same priority band, as a `pending_strategist_review`
        # escalation. Not pumpable: every refutation costs a
        # kernel-checked negation brick.
        parent_id = int(me["parent_group_id"])
        if not db.is_in_queue(conn, target_id=str(parent_id),
                              kind="Strategist"):
            db.enqueue(conn, kind="Strategist", target_id=str(parent_id),
                       target_kind="Group", priority=20, problem=problem)
            print(f"[return] refutation — woke parent group {parent_id} "
                  f"immediately (batch not waited on)", flush=True)
    conn.commit()
    print(f"[return] group {me['id']} returned to {me['parent_group_id']} "
          f"({problem}, {flavour}): {str(decision.reason or '')[:80]}",
          flush=True)
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
    )


def _commit_close_group(decision: Decision, conn: sqlite3.Connection,
                        *, problem: str, tick: int, trigger_kind: str,
                        group_id: "int | None",
                        actor: str = ACTOR_STRATEGIST) -> CommitOutcome:
    """Retire a child group (v35). The reverse of `Delegate`.

    A parent's Programme is alive: its route changes, and a burden it
    delegated three revisions ago can stop mattering. Without this the
    only way to stop that group is to wait for it to hit its own wall
    and hand the charter back — the tokens in between buy nothing.

    Reaching `closed` fills the opening `Delegate` outcome, so the
    parent's batch completes through the ordinary relay. The child's
    seat stops on its own: `groups_needing_t1` and `groups_stalled` both
    select `status = 'active'` only. Workers already in flight finish
    and write; nothing is torn out from under them.
    """
    me = _authoring_group(conn, problem, group_id)
    target = int(decision.payload["target_group_id"])
    kid = _groups.get(conn, target)
    if me is None or kid is None:            # verify already rejected this
        raise RuntimeError(f"CloseGroup({target}) on {problem!r} is invalid")
    ts = db.now()
    payload = dict(decision.payload)
    payload["charter"] = str(kid["charter"])
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, reason, payload,"
        " produced_group_id, outcome, actor, created_at, updated_at)"
        " VALUES (?, ?, ?, 'CloseGroup', ?, ?, ?, ?, 'committed', ?, ?, ?)",
        (problem, tick, trigger_kind, int(me["id"]), decision.reason,
         json.dumps(payload, ensure_ascii=False), target, actor, ts, ts),
    )
    row_id = int(cur.lastrowid)
    # The anchor-shelve lives inside `set_status` now (one spelling for
    # the direct close, the ancestor cascade and the startup sweep).
    _groups.set_status(conn, target, "closed", event="group_closed")
    conn.commit()
    print(f"[close] group {target} retired by {me['id']} ({problem}): "
          f"{str(decision.reason or '')[:80]}", flush=True)
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
    )


def commit_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str, tick: int, trigger_kind: str,
                     workspace: Path,
                     group_id: "int | None" = None,
                     actor: str = ACTOR_STRATEGIST,
                     delivered_batches: "list[str] | None" = None,
                     ) -> list[CommitOutcome]:
    """Execute a multi-decision batch in declared order.

    `actor` names who decided (§3.2). It defaults to the Strategist, so
    every existing caller is unchanged; `state/commands.py` passes
    'human' and this is the ONLY way a human row is written — the
    appliers are shared so a person's command has the same side effects,
    the same batch bookkeeping and the same audit shape as the machine's.

    Caller must have already passed `verify_decisions`. All decisions
    commit; per-kind side effects fire individually. The transaction
    boundary is per-decision (each per-kind helper calls
    `conn.commit()`); a mid-batch raise leaves earlier rows committed,
    which mirrors the existing single-decision contract — verify is
    expected to catch every user-error case, so any raise here
    indicates a framework bug to investigate, not graceful recovery
    territory.

    Inject batching is unified across pipeline kinds: every Inject
    decision in `decisions` shares one `batch_id`, so the cascade
    fires `inject_batch_done` exactly once — when the LAST of the
    Forward / Backward / Builder injects reaches terminal. Each kind
    has its own completion signal (see `_commit_inject_batch`).

    `delivered_batches` is the batch roster the wake's Context actually
    carried; the clock bump below may swallow only those and the ones
    this batch acts on (`batch_ack`). Omitted (a direct caller, a test,
    a human command) it reads as "everything was delivered" — the
    pre-2026-09-03 behaviour.

    Returns one CommitOutcome per decision (same order).
    """
    # A retired charter accepts no new batch — the any-caller backstop
    # behind `run_strategist`'s round-boundary and pre-commit doors.
    # Raising (not dropping) is deliberate: every sanctioned path checks
    # first, so reaching here retired means an unguarded caller.
    _retired = _group_retired_status(conn, problem, group_id)
    if _retired is not None:
        raise ValueError(
            f"commit_decisions: group {group_id} is {_retired} — a "
            "retired charter accepts no new batch (check "
            "_group_retired_status before committing)")
    # v35 — stamp every row this batch writes with its AUTHORING group.
    # Done as one post-pass keyed on "rows that did not exist before",
    # rather than threading the id through a dozen per-kind INSERTs: a
    # new decision kind then cannot be added and silently forget it, and
    # rows written by nested helpers are covered too.
    _before = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM strategist_decisions"
    ).fetchone()[0]
    inject_batch_id: str | None = None
    # v35 — `Delegate` counts: a batch whose only experiment is a delegated
    # burden must still get a batch_id, or nothing ever wakes the parent
    # when the child group finishes. `db.BATCH_DECISION_KINDS` is the one
    # definition of "rides the batch cycle".
    n_inject = sum(1 for d in decisions
                   if d.kind in db.BATCH_DECISION_KINDS)
    if n_inject:
        inject_batch_id = uuid.uuid4().hex
    # Real per-step indices: the audit payload's step_index was hardcoded
    # 0 for every row, so `## Completed Inject batches` labelled all
    # steps "step 0" and the Strategist couldn't line outcomes up with
    # its briefs (feedback 2026-07-04, repeated).
    out: list[CommitOutcome] = []
    step = 0
    for d in decisions:
        idx = step
        if d.kind in db.BATCH_DECISION_KINDS:
            step += 1
        out.append(_commit_one(
            d, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, workspace=workspace,
            inject_batch_id=inject_batch_id,
            inject_step_index=idx, inject_batch_size=n_inject,
            actor=actor, group_id=group_id))
    # Wake-clock touch — ONE point for the whole batch (task #119).
    # When each per-kind path touched last_strategist_at itself, the
    # early-return paths (Inject / FetchPaper) never
    # learned about the ROUTINE clock: a pure-Inject routine batch left
    # last_routine_at NULL, T1 read "never routine'd", and a fresh
    # routine wake was enqueued the instant the previous one finished —
    # a strategist pump (b6_1 leg 6, 2026-07-25). A mid-batch raise
    # skips the touch: an un-acknowledged batch must not advance either
    # clock.
    from ...state import groups as _groups
    gid = group_id if group_id is not None else \
        _groups.ensure_top_group(conn, problem)
    # Every per-kind INSERT writes `group_id` itself. This is the
    # exhaustiveness CHECK, not the writer: a blind range UPDATE over
    # "rows newer than my snapshot" is wrong the moment two groups of
    # the same problem commit concurrently — which is exactly the
    # concurrency the per-group seat just bought — because each would
    # stamp the other's rows and every downstream reading (ownership,
    # stall, deliverables) would follow the wrong group. Fail loud
    # instead: a decision kind that forgets is a framework bug.
    unstamped = conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions"
        " WHERE id > ? AND problem = ? AND group_id IS NULL",
        (int(_before), problem)).fetchone()[0]
    if unstamped:
        raise RuntimeError(
            f"{unstamped} decision row(s) committed without a group_id "
            f"on {problem!r} — a per-kind INSERT missed it")
    # The wake's clocks advance here and nowhere else. `touch_clocks` was
    # the admin turn's opt-out — an admin commit that advanced them would
    # let a wake whose math half failed read as "strategist ran",
    # starving the retry pressure. With one turn there is no half to
    # fail separately, so the flag went with the split (2026-08-11).
    #
    # A HUMAN command is not a wake (§3.3): these clocks meter the
    # MACHINE's cadence — T1 reads `last_strategist_at` as "the seat ran
    # this recently" — so a person's command restamping them would push
    # the next routine out by up to a full interval, silently buying the
    # machine quiet with the human's action.
    if actor != ACTOR_HUMAN:
        # …and the bump is not allowed to swallow a batch this wake
        # never received and never acted on (2026-09-03). Runs FIRST:
        # it reads the pre-bump unacknowledged set.
        from . import batch_ack
        batch_ack.settle(conn, problem=problem, group_id=int(gid),
                         delivered=delivered_batches,
                         landed_row_ids=[o.decision_row_id for o in out])
        db.update_problem_last_strategist_at(conn, problem)
        _groups.touch_strategist(conn, int(gid),
                                 routine=(trigger_kind == "routine"))
        if trigger_kind == "routine":
            db.update_problem_last_routine_at(conn, problem)
    if trigger_kind == "routine_fired":
        # The action wake's batch stands: the audit it answered is acted
        # on (verify already required a decision per fired root).
        from . import audit as _audit
        pending = _audit.pending_fired_verdict(conn, int(gid))
        if pending is not None:
            _audit.mark_acted(conn, int(pending["id"]))
    conn.commit()
    return out


def commit_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str, tick: int, trigger_kind: str,
                    workspace: Path,
                    group_id: "int | None" = None,
                    actor: str = ACTOR_STRATEGIST) -> CommitOutcome:
    """Single-decision wrapper around `commit_decisions`. Preserved
    so existing callers (single-decision tests, anyone hand-driving
    one decision) keep their CommitOutcome-returning contract.
    """
    return commit_decisions(
        [decision], conn, problem=problem, tick=tick,
        trigger_kind=trigger_kind, workspace=workspace,
        group_id=group_id, actor=actor,
    )[0]


def _commit_ingest(conn: sqlite3.Connection, *, problem: str,
                   workspace: Path,
                   group_id: "int | None" = None,
                   report: "str | None" = None) -> None:
    """Execute a Strategist `Ingest` decision's side effect (anchor+claim
    Phase 4).

    The sign-off pause and the Library decision are separate axes
    (2026-07-18 gate retirement): `signoff: false` (machine setting,
    benchmark adapters only) × `library.require_signoff` config decide
    pause-vs-direct; `library:` decides harvest only. A paused problem
    sets `ingest_signoff_pending` and waits for `asterism
    approve-ingest` (→ enqueue Librarian iff library) or `reject-ingest`
    (→ back to proving); direct ingest harvests iff the standing
    `library` flag. The old coupling (library:false silently skipped
    the human gate) let any opt-out producer bypass sign-off.

    Phase 6 — Ingest is the problem's ONLY terminal: this commit stamps
    `problems.ingested_at`, which drives the T1/T4 liveness predicates,
    the stale-row drop, the Librarian selfstart eligibility and the
    daemon exit check. `reject-ingest` and the rollback auto-revoke
    clear the stamp (back to the live path). The old root-proved-auto
    Librarian trigger in `verify.root_integrity_gate` is retired —
    harvest is strictly Ingest-driven now."""
    from ...core import config as _config
    from ...state import intent as _intent
    # v35 — a SUB-group's Ingest is a DELIVERY UPWARD, not a terminal.
    # Everything below this branch is problem-terminal semantics: the
    # human sign-off pause, the Library harvest, the regression
    # milestone, the review snapshot, `problems.ingested_at` and the
    # problem FSM edge. A group handing its charter back up must touch
    # none of them — it would pause the whole problem for a human, or
    # publish a snapshot of a tree that is still being built.
    #
    # What it does instead is one write: reaching 'delivered' fills the
    # parent's `Delegate` outcome, which completes the parent's batch
    # and wakes it through the ordinary relay. The bricks this group
    # marked are then the parent's to cite.
    me = _authoring_group(conn, problem, group_id)
    if me is not None and not _groups.is_top(me):
        _groups.set_status(conn, int(me["id"]), "delivered",
                           event="group_delivered")
        conn.commit()
        marked = db.deliverables(conn, problem=problem,
                                 group_id=int(me["id"]))
        print(f"[strategist] Ingest({problem}): group {me['id']} "
              f"delivered {len(marked)} brick(s) to group "
              f"{me['parent_group_id']}", flush=True)
        return
    # The human-readable report (HID §1.2 / §3.4) — stored and rendered
    # here, on the PROBLEM-terminal path only. A sub-group's Ingest
    # returned above: it is a delivery upward, and `problems.ingest_report`
    # is one column per problem, so asking a group that closed nothing for
    # a reader's report would be a gate naming an action it cannot take.
    # Absent report → nothing written, no failure (the prompt is staged).
    if str(report or "").strip():
        from ...state import report as _report
        _report.record(conn, problem, report)
        try:
            _report.render(conn, problem, db.problem_dir(workspace, problem))
        except OSError as e:
            print(f"[strategist] REPORT.md render failed: {e}", flush=True)
    # Tripwire, not a gate (operator ruling 2026-08-02 — log only, the
    # human is not asked). `ingested_at` is what `groups_stalled` and
    # `is_group_stalled` filter on, so the instant the TOP group Ingests,
    # every still-`active` sub-group stops being woken: no T4, no error,
    # nothing. Whether the right rule is wait / auto-close / refuse is a
    # design question deliberately left open until a real group tree has
    # run — but the framework must not do it in silence, and this line is
    # the evidence that decision will be made from.
    if me is not None:
        live = _groups.children(conn, int(me["id"]), active_only=True)
        if live:
            print(f"[ingest-orphans] {problem}: top-group Ingest with "
                  f"{len(live)} sub-group(s) still active "
                  f"({', '.join(str(g['id']) for g in live)}) — they stop "
                  f"being woken once `ingested_at` is stamped",
                  flush=True)
    # Decide the sign-off gate BEFORE publishing the terminal stamp.
    # `ingested_at` + a clear flag is what the Librarian selfstart path
    # reads as "approved, go" — so the flag must land in the same
    # transaction as the stamp. The pre-fix order stamped first and set
    # the flag AFTER store_review_snapshot, whose gateway warm-up is a
    # 30s+ window on a cold/stale gateway; the dispatcher tick inside
    # that window auto-started the harvest chain past the human gate
    # (observed 2026-07-06, Logic.toy_list_reverse: dedupe→migrate ran
    # before "paused for human sign-off" printed).
    # A disproved root (owner ruling 2026-08-30): the terminal is
    # `refuted`, stamped like any terminal (`ingested_at` is what the
    # liveness predicates read), with nothing to harvest and no sign-off
    # pause — a kernel disproof is a result, not a claim awaiting a
    # human.
    root = conn.execute(
        "SELECT status FROM goals WHERE problem = ? AND origin = 'root'"
        " LIMIT 1", (problem,)).fetchone()
    if root is not None and str(root["status"]) == "disproved":
        from ...state import transitions as _transitions
        from ...state import regress as _regress
        db.set_problem_ingested(conn, problem)
        _transitions.apply_problem_transition(
            conn, problem, "refuted", event="ingest_refuted")
        conn.commit()
        _regress.record_terminal(workspace, problem=problem,
                                 terminal="refuted",
                                 deliverables=len(db.deliverables(conn, problem)))
        print(f"[strategist] Ingest({problem}): root disproved — the "
              f"problem closes as refuted", flush=True)
        return

    harvest = True
    signoff_optout = False
    harvest_skip_msg = ""
    pintent = _intent.read(conn, problem)
    if pintent is None:
        # Unreadable intent: no harvest, but DO pause — failing into
        # the human gate is the safe direction.
        harvest = False
        harvest_skip_msg = (f"[strategist] Ingest({problem}): intent "
                            f"unreadable (no problems row); no harvest")
    else:
        signoff_optout = not pintent.signoff
    if harvest and not pintent.library:
        harvest = False
        harvest_skip_msg = (f"[strategist] Ingest({problem}): "
                            f"library:false — opted out of Library; "
                            f"no harvest")
    require_signoff = (not signoff_optout) and _as_bool(_config.get(
        "library.require_signoff", default=True, workspace=workspace))

    # Terminal stamp + gate flag: one atomic publication. Even when the
    # problem opts out of harvest the Strategist's terminal judgment
    # stands; only the harvest side-effects vary.
    db.set_problem_ingested(conn, problem)
    from ...state import transitions as _transitions
    if require_signoff:
        db.set_ingest_signoff_pending(conn, problem, True)
        _transitions.apply_problem_transition(
            conn, problem, "ingest_signoff", event="ingest_committed")
    else:
        _transitions.apply_problem_transition(
            conn, problem, "ingested", event="ingest_direct")
    conn.commit()

    # Slow best-effort work AFTER the gate is closed.
    # Regression manifest (task #8): the milestone auto-records itself —
    # tracked JSONL, best-effort, never blocks the Ingest.
    from ...state import regress as _regress
    # Auditability (frontmatter dissolve): the effective machine
    # settings ride the milestone line — the axiom-whitelist history
    # stays reconstructible from git even though the yaml stopped
    # changing. Best-effort like the rest of the record.
    settings_snapshot = None
    if pintent is not None:
        settings_snapshot = {
            "axioms_whitelist": _intent.effective_axioms(
                pintent, problem=problem),
            "forbidden_lemmas": list(pintent.forbidden_lemmas),
            "library": bool(pintent.library),
            "signoff": bool(pintent.signoff),
        }
    _regress.record_terminal(
        workspace, problem=problem, terminal="ingested",
        deliverables=len(db.deliverables(conn, problem)),
        settings=settings_snapshot)
    # Review snapshot (frontend charter §5-4): compute the anchor+claim
    # closure NOW, while the gateway is warm from the proving run — the
    # sign-off surfaces (CLI default, serve API) then read the stored
    # JSON instead of paying a 30s+ cold gateway per view. Best-effort:
    # a failure degrades readers to live compute, never blocks Ingest.
    from ...quality import review as _review
    _review.store_review_snapshot(conn, workspace, problem)

    if require_signoff:
        # The Library decision is (re)made at the signature; the current
        # flag is just the standing default, so a false flag is worth a
        # note but never skips the pause.
        if not harvest:
            print(harvest_skip_msg, flush=True)
        print(f"[strategist] Ingest({problem}): paused for human sign-off — "
              f"`asterism approve-ingest {problem}` to harvest, "
              f"`asterism reject-ingest {problem} --reason ...` to keep "
              f"proving", flush=True)
    elif not harvest:
        print(harvest_skip_msg, flush=True)
    else:
        db.enqueue(conn, kind="Librarian", target_id=problem,
                   target_kind="Problem", priority=0, problem=problem)
        print(f"[strategist] Ingest({problem}): direct ingest — enqueued "
              f"Librarian", flush=True)


def _commit_one(decision: Decision, conn: sqlite3.Connection,
                *, problem: str, tick: int, trigger_kind: str,
                workspace: Path,
                inject_batch_id: str | None,
                inject_step_index: int = 0,
                inject_batch_size: int = 1,
                actor: str = ACTOR_STRATEGIST,
                group_id: "int | None" = None) -> CommitOutcome:
    """Execute one decision's side effects + INSERT audit row.

    Caller must have already passed `verify_decision`. This is the
    write-path; errors here indicate a bug (or a race with another
    Strategist commit), not user error. `inject_batch_id` is
    threaded through to `_commit_inject_batch` so every Inject
    decision in the same `commit_decisions` call shares one batch
    UUID (Forward / Backward / Builder mixed; see `commit_decisions`).
    """
    k = decision.kind
    outcome = "committed"
    enqueued_forward = False
    if group_id is None:
        group_id = _groups.ensure_top_group(conn, problem)

    if k == "Inject":
        return _commit_inject_batch(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind,
            inject_batch_id=inject_batch_id,
            step_index=inject_step_index,
            batch_size=inject_batch_size,
            actor=actor, group_id=group_id,
        )

    if k == "Delegate":
        return _commit_delegate(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, group_id=group_id,
            batch_id_override=inject_batch_id,
            step_index=inject_step_index,
            batch_size=inject_batch_size, actor=actor,
        )

    if k == "CloseGroup":
        return _commit_close_group(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, group_id=group_id, actor=actor,
        )

    if k == "ReturnToParent":
        return _commit_return_to_parent(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, group_id=group_id, actor=actor,
        )

    if k == "Noop":
        # No side effect beyond the audit row + last_strategist_at.
        pass

    elif k == "EmitDirective":
        # verify_decision rejects the retired kind before commit; reaching
        # here means a verify bypass — fail loudly, never write.
        raise RuntimeError(
            "EmitDirective is retired (Conventions section) but reached "
            "commit — a verify path let it through")

    elif k == "ConfirmShelve":
        gid = int(decision.target_id)  # type: ignore[arg-type]
        # No-op guard (BT 2026-05-29 g3380): a ConfirmShelve on a goal
        # that is already a hard terminal (proved / disproved) is
        # silently ignored — it does NOT bounce the batch back to the
        # Strategist for re-issue. The Strategist sometimes ConfirmShelves
        # a proved-but-superseded orphan (it has no clean "retire orphan"
        # verb); shelving it would regress a completed proof and break
        # `proved ⟺ subs proved`. The rest of the batch (paired Injects,
        # directives) commits normally. The dispatcher's
        # _set_goal_terminal_and_propagate carries the same guard as a
        # class-level backstop, but short-circuiting here also skips the
        # _propagate_shelve cascade and keeps the decision's outcome benign.
        _g = db.get_goal(conn, gid)
        if _g is not None and \
                str(_g["status"]) in transitions.GOAL_HARD_TERMINALS:
            print(f"[strategist] ConfirmShelve(g{gid}) no-op — goal already "
                  f"{_g['status']!r}; not downgrading a terminal goal",
                  flush=True)
        else:
            _dispatcher._set_goal_terminal_and_propagate(conn, gid, "shelved")
            _dispatcher._propagate_shelve(conn, gid)
        # Downward cascade removed: shelved is reopenable (split from
        # disproved), descendants of a shelved goal stay invisible to
        # BFS via the alive-set filter in `db.open_goals` regardless
        # of their own status — no behavior gain from flipping them.
        # Strategist's context view filters descendants of dead-strategy
        # chains
        # too (see `_section_active_goals`), so the surface area where
        # status drift could mislead Strategist is closed at the view
        # boundary, not the data boundary.

    elif k == "MarkDeliverable":
        # Synchronous: flag the Forward node top-level. `asterism review`
        # then computes + presents its anchor closure for human opt-out
        # review. Falls through to the shared audit-row INSERT (outcome
        # 'success').
        db.mark_deliverable(conn, int(decision.target_id))  # type: ignore[arg-type]


    elif k == "Ingest":
        # Terminal judgment → pause for human sign-off (unless the
        # problem's `signoff: false` machine setting or config opts
        # into direct ingest); harvest to Library iff `library:`.
        # Falls through to the audit INSERT.
        _commit_ingest(conn, problem=problem, workspace=workspace,
                       group_id=group_id,
                       report=decision.payload.get("report"))

    elif k == "RequestUserAmend":
        # Atomic three-step: tmp write -> INSERT row -> rename
        # (see docs/archive/design/phase2/pipelines.md §2.5).
        file = decision.payload["file"]
        target_path = db.problem_dir(workspace, problem) / f".proposed_{file}"
        body = str(decision.payload["proposed_body"])
        # Step 1: write to a temp file in the same directory then fsync.
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".proposed_{file}.", dir=str(target_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            # Step 2: INSERT audit row with outcome='awaiting_human'.
            # Step 3 (rename) happens below after the row is in place.
            # Stuffed into the row INSERT path below for atomicity.
        except Exception:
            # Best-effort cleanup of orphan tmp
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        # Stash for the post-INSERT rename below
        decision.payload["__tmp_path__"] = tmp_name
        decision.payload["__final_path__"] = str(target_path)
        outcome = "awaiting_human"

    else:
        raise RuntimeError(f"commit_decision: unhandled kind {k!r}")

    # INSERT audit row. brief and reason live in dedicated columns;
    # other structured params go in payload JSON (excluding the tmp
    # path bookkeeping for RequestUserAmend).
    #
    # `batch_id` is shared with the batch's Inject rows: when a
    # ConfirmShelve / Reopen / etc. ships in the same JSON decision
    # array as one or more Inject(s), it inherits the same UUID. The
    # `_section_pending_reopens` Context.md section uses this link to
    # surface a shelved goal ONLY when the Strategist-promised batch
    # of follow-up Injects has completed — instead of re-surfacing
    # the goal on every unrelated inject_batch_done wake (brouwer
    # 2026-05-22: g2771 ConfirmShelve'd 4× because Context.md kept
    # listing it on every wake regardless of who was woken). For
    # solo non-Inject batches (no paired Inject), inject_batch_id is
    # None and the column stays NULL, matching the pre-fix shape.
    payload_for_audit = {
        k: v for k, v in decision.payload.items()
        if not str(k).startswith("__")
    }
    # DB outcome ≠ caller signal (CommitOutcome.final_outcome). Inject
    # rows write NULL here (filled later by propagate_inject_outcome_
    # from_goal/strategy when produced_goal/strategy terminates) — but
    # Inject returns early via _commit_inject_batch and never reaches
    # this INSERT. Everything that lands here is a synchronous decision:
    # its side effect already executed above, so the row is terminal
    # at INSERT time. RequestUserAmend keeps 'awaiting_human' (terminal
    # from framework POV — blocked on operator). All other kinds
    # (ConfirmShelve/Reopen/EmitDirective/Noop) write 'success'.
    #
    # Pre-fix bug: this column wrote NULL for ConfirmShelve+friends.
    # Solo (batch_id=NULL) was harmless. Paired with Inject in same
    # batch (e.g. ConfirmShelve(G) + a mint Inject for the prereq), the
    # NULL outcome made `maybe_enqueue_inject_batch_done`'s pending
    # count never reach 0 (the batch stayed "incomplete" forever) and
    # the in-flight-inject suppression read the batch as live — so
    # Strategist never woke to fire the promised follow-up Reopen.
    # Observed jordan_normal_form 2026-05-23: ConfirmShelve(succ_glue)
    # paired with Inject of the index-layout brick chain; bricks proved,
    # batch_id stayed "incomplete" forever, the triggers stayed gated,
    # daemon idle. (As of 2026-06-15 the in-flight suppression is a
    # precise active-check — `has_active_inflight_inject` for T4,
    # `has_live_inflight_inject` for T0 / the Noop-guard — not a blanket
    # NULL-row test; but a NULL ConfirmShelve still stalls the batch
    # pending count, so synchronous decisions MUST write a non-NULL
    # outcome here.)
    if outcome == "awaiting_human":
        db_outcome: str | None = "awaiting_human"
    else:
        db_outcome = "success"
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief,"
        " reason, payload, batch_id, outcome, actor, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (problem, tick, trigger_kind, decision.kind, group_id,
         decision.target_id, decision.brief, decision.reason,
         json.dumps(payload_for_audit, ensure_ascii=False),
         inject_batch_id,
         db_outcome, actor,
         ts, ts),
    )
    decision_row_id = int(cur.lastrowid)

    # Post-INSERT side effects requiring the row id. Inject is handled
    # earlier via _commit_inject_batch (returns early); only
    # RequestUserAmend's atomic rename lives here.
    if k == "RequestUserAmend":
        # Atomic rename: temp -> .proposed_<file>. If this fails the
        # audit row is rolled back via the outer transaction.
        os.rename(decision.payload["__tmp_path__"],
                  decision.payload["__final_path__"])
        from ...state import transitions as _transitions
        _transitions.apply_problem_transition(
            conn, problem, "awaiting_human", event="amend_requested")

    # Wake clocks (last_strategist_at + the routine-only last_routine_at)
    # are touched ONCE per batch in `commit_decisions` — not here (task
    # #119: per-path touches let the early-return kinds miss the routine
    # clock).
    conn.commit()

    return CommitOutcome(
        decision_row_id=decision_row_id,
        enqueued_forward=enqueued_forward,
        final_outcome=outcome,
    )


