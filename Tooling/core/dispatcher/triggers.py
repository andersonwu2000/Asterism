"""Strategist T0/T1 trigger machinery.

Carved move-only from the dispatcher monolith (B4, 2026-08-29); bodies are
verbatim — see git history of core/dispatcher.py for provenance.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import typing as _typing
import shutil
import sqlite3
from dataclasses import dataclass, field
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime
from pathlib import Path

from ... import agent, pipeline
from .. import config, fsutil, gateway_health, network_wait, quota, quota_wait
from ..admission import (ADMIT, DENY_KIND_BACKOFF, DENY_QUOTA,
                         DENY_TARGET_COOLED, admission)
from ...state import db, thresholds, transitions, tree
from ...state import intent as intent_mod
from ...state import failures as _failures
from ...state import groups as _groups
from ...quality import prune, verify


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def _ensure_top_groups(conn: sqlite3.Connection, *,
                       scope: str | None = None) -> None:
    """Every live problem has a top group — the v35 invariant every seat
    source depends on.

    A problem without one has NO Strategist seat at all (each trigger
    keys on a group) and the failure is silent. Both per-tick entry
    points call this, so no seat source is left depending on the other
    having run first: an ordering dependency whose breakage is invisible
    is the same shape as the bug it guards against.
    """
    sql = ("SELECT p.name FROM problems p"
           " WHERE p.ingested_at IS NULL AND NOT EXISTS ("
           "   SELECT 1 FROM groups g WHERE g.problem = p.name"
           "     AND g.parent_group_id IS NULL)")
    args: tuple = ()
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args = (scope,)
    rows = conn.execute(sql, args).fetchall()
    if not rows:
        return
    for r in rows:
        _groups.ensure_top_group(conn, str(r["name"]))
    conn.commit()


def _enqueue_strategist(conn: sqlite3.Connection, group_id: int,
                        problem: str, *, priority: int) -> None:
    """The ONE way a Strategist seat is queued (v35).

    Every trigger goes through here so the row shape stays in one place:
    the seat belongs to a GROUP (`target_kind='Group'`), while `problem`
    keeps the row scope-safe for pop / flush / recovery.

    Active groups only (2026-08-31): a seat for a closed/retired group
    is dead on arrival — the pop loop's settled-target skip deletes it
    and the trigger re-enqueues next tick (group 717: 5,393 skip lines
    in three hours). The chokepoint refuses instead."""
    row = conn.execute("SELECT status FROM groups WHERE id = ?",
                       (int(group_id),)).fetchone()
    if row is None or str(row["status"]) != "active":
        st = "gone" if row is None else str(row["status"])
        print(f"[trigger] no seat for group {group_id} ({problem}) — "
              f"group is {st}", flush=True)
        return
    db.enqueue(conn, kind="Strategist", target_id=str(group_id),
               target_kind="Group", priority=priority, problem=problem)


def _strategist_inflight(conn: sqlite3.Connection, group_id: int,
                         running: "set[tuple]") -> bool:
    """A Strategist for this GROUP is already running or queued.

    The serialization invariant is per group (v35), not per problem: a
    group mutates its OWN Programme, plan note and clocks, and its own
    slice of the goal tree, so two runs of the SAME group would race
    while two different groups are exactly the concurrency the tree
    exists to buy. Checks BOTH the in-memory `running` set (in-flight)
    AND the DB queue (pending); the cascade-time
    `_enqueue_strategist_review` checked only the queue, which is the gap
    `reconcile_stuck_states` closes.

    Running key is (target_id, kind, decision_id) with target_id the
    queue row's string; Strategist rows always have decision_id=None
    (never spawned from an Inject), so matching on (group id, kind)
    covers the invariant.

    (Pre-v35 rows are problem-keyed with target_kind='Problem'. They are
    resolved to the top group at pop time, so the only place that still
    sees the old key is `is_in_queue` — hence the second probe, which
    keeps a queued legacy row from being duplicated by a fresh one.)"""
    key = str(group_id)
    in_running = any(
        r[0] == key and r[1] == "Strategist" for r in running
    )
    if in_running or db.is_in_queue(conn, target_id=key, kind="Strategist"):
        return True
    row = conn.execute("SELECT problem FROM groups WHERE id = ?",
                       (int(group_id),)).fetchone()
    if row is None:
        return False
    problem = str(row["problem"])
    return (any(r[0] == problem and r[1] == "Strategist" for r in running)
            or db.is_in_queue(conn, target_id=problem, kind="Strategist"))


def reconcile_stuck_states(conn: sqlite3.Connection,
                           running: "set[tuple]",
                           *, scope: str | None = None) -> None:
    """Per-tick safety net for mid-run stuck states that no other reconciler
    re-triggers and that can persist in a LIVE daemon (not only across a
    crash, which `recover_at_startup` handles).

    Two classes, both confirmed reachable mid-run and unrecoverable without
    this (investigation 2026-06-13):

      1. `pending_strategist_review` goals whose cascade-time Strategist
         enqueue was deduped (L355 queue-only race), lost, or dropped — there
         is no restart recovery for these, so they orphan permanently (P13
         left 2/3 stuck; BT g3246 waited 30+ min for the accidental 120-min
         T1). Enqueue a Strategist; the spawn's `_derive_strategist_trigger`
         sees the pending goal and runs a `pending_review` wake.

      2. NULL-outcome Inject decisions whose worker died on infra failure
         with no artifact — this wedges the WHOLE problem (the in-flight-
         batch clause suppresses T0/T1/T4), recoverable otherwise only at
         restart. Re-enqueue the worker.

    Both are IN-FLIGHT GATED: an item whose worker is live (in `running`) or
    already queued is skipped, so this never double-dispatches. That gating
    is the only thing this adds over the startup-recovery logic it shares
    (`db.null_inject_redispatch_specs`), which runs against a clean slate."""
    _ensure_top_groups(conn, scope=scope)

    # 1 — pending_review: enqueue Strategist (spawn derives the trigger).
    from ...state import transitions as _transitions
    for prob in db.problems_with_pending_review(conn, scope=scope):
        if not _transitions.problem_accepts_wake(
                conn, prob, "pending_review"):
            continue
        if db.problem_has_awaiting_human(conn, prob):
            continue
        # v35 — route to the group that OWNS the pending goal, exactly as
        # the cascade-time path does. Two routes to two different homes
        # for one event is the shape this file has paid for three times:
        # the compensating path would seat the top group on a review only
        # a sub-group can answer.
        for r in conn.execute(
            "SELECT id FROM goals WHERE problem = ?"
            "   AND status = 'pending_strategist_review' ORDER BY id",
            (prob,),
        ).fetchall():
            owner = _groups.group_for_goal(conn, prob, int(r["id"]))
            gid = (int(owner["id"]) if owner is not None
                   else _groups.ensure_top_group(conn, prob))
            if _strategist_inflight(conn, gid, running):
                continue
            _enqueue_strategist(conn, gid, prob, priority=20)

    # 1.5 — settled NULL-outcome Inject decisions: the produced goal/
    # strategy already terminated (or a Backward inject's strategy is
    # 'proposed' but wedged with zero alive subgoals — a soft-shelved
    # subgoal awaiting a Reopen that this very NULL outcome blocks by
    # suppressing T4). Resolve the outcome so the batch completes, fires
    # inject_batch_done, and stops suppressing the stall trigger.
    # Complements step 2 below (worker died with no artifact → re-dispatch);
    # the two are disjoint by the produced goal/strategy state.
    db.reconcile_settled_inject_outcomes(conn, scope=scope)

    # 2 — NULL-outcome Inject: re-enqueue the worker, in-flight gated.
    for spec in db.null_inject_redispatch_specs(conn, scope=scope):
        did = spec["decision_id"]
        if any(len(r) > 2 and r[2] == did for r in running):
            continue  # a worker for this Inject is live this run
        if db.queue_has_decision(conn, did):
            continue  # already queued (e.g. cascade-time L967 re-enqueue)
        db.enqueue(conn, kind=spec["kind"], target_id=spec["target_id"],
                   target_kind=spec["target_kind"], priority=10,
                   decision_id=did, problem=spec["problem"])


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def strategist_triggers(conn: sqlite3.Connection,
                        running: set[tuple[str, str]],
                        *,
                        scope: str | None = None,
                        interval_min: float = 120.0,
                        daemon_start_iso: str | None = None,
                        suppress_stall: bool = False,
                        ) -> None:
    """T1 (routine) + T4 (stall) enqueues for the Strategist pipeline.

    `suppress_stall` (2026-08-30): a promotion is in the cold-build gate
    — its goal will flip on the next tick or roll back — so the state IS
    moving; the structural stall backstop must not read that pause as a
    deadlock and wake a Strategist for it.
    T2 (pending_review) is handled by `_enqueue_strategist_review` at
    cascade-time, not here.

    T1.5 (the separate epistemic-audit wake, v26) is RETIRED (user call
    2026-07-25): its belief-sweep duties are now phase 1 of every
    routine wake, so the routine clock is the only periodic seat
    source. Historic 'audit' trigger rows stay valid in the DB CHECK.

    Phase 6 — T0 (first_launch) is RETIRED: a fresh problem has no
    dispatchable work and no committed Ingest, so it is structurally
    STALLED and T4 wakes the Strategist immediately (the wake runs under
    the `inject_batch_done` prompt, whose mandatory-advance rule forces
    the first Inject). Priority stays: queue.priority just needs to put
    Strategist ahead of Backward (2) / Builder (5).

    T1 condition: `last_routine_at` (the routine-only clock, not reset by
                   event-driven triggers) older than `interval_min` minutes of
                   running time (paused/down time excluded via
                   `daemon_start_iso`), AND no committed Ingest.

    Per-problem dedup: skip enqueue if a Strategist (target=problem) is
    already running or already in the queue. The awaiting_human gate
    skips Strategist enqueue for problems whose human-input request
    hasn't been resolved.

    Called from `dispatcher.run` once per tick alongside `bfs_refill`.
    """
    max_age_sec = interval_min * 60.0
    _ensure_top_groups(conn, scope=scope)

    # Wake legality (FSM P3): every seat source consults the ONE matrix
    # — a non-'active' problem (awaiting_human / ingest_signoff /
    # ingested / revoked) takes no seats. The legacy per-carrier guards
    # (awaiting check, ingested exclusion) stay as belt during the
    # dual-write window.
    from ...state import transitions as _transitions

    # T1 — routine wake. v35: the clock is per GROUP (`groups_needing_t1`),
    # so sibling groups keep their own cadence instead of taking turns at
    # one problem-wide seat. With only top groups this yields exactly the
    # problems the old per-problem selector named.
    for row in db.groups_needing_t1(
        conn, scope=scope, max_age_sec=max_age_sec,
        since_iso=daemon_start_iso,
    ):
        prob = str(row["problem"])
        gid = int(row["id"])
        if not _transitions.problem_accepts_wake(conn, prob, "routine"):
            continue
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, gid, running):
            continue
        _enqueue_strategist(conn, gid, prob, priority=10)

    # T1.6 — a FIRED routine audit nobody has acted on (2026-08-30):
    # persistent state, seated like an unacknowledged batch. The
    # findings must not wait for the next routine clock.
    _scope_sql = "" if scope is None else " AND problem LIKE ?"
    _scope_args: tuple = () if scope is None else (scope,)
    for row in conn.execute(
            "SELECT DISTINCT group_id, problem FROM routine_verdicts"
            " WHERE fired = 1 AND acted_at IS NULL" + _scope_sql,
            _scope_args).fetchall():
        prob = str(row["problem"])
        gid = int(row["group_id"])
        _g = conn.execute("SELECT status FROM groups WHERE id = ?",
                          (gid,)).fetchone()
        if _g is None or str(_g["status"]) != "active":
            # The audited group died after the audit (closed/retired):
            # the findings have no seat to land on — stamp the verdict
            # acted so this source extinguishes instead of re-seating
            # every tick forever (2026-08-31, group 717).
            conn.execute(
                "UPDATE routine_verdicts SET acted_at = ?"
                " WHERE group_id = ? AND fired = 1 AND acted_at IS NULL",
                (db.now(), gid))
            conn.commit()
            print(f"[trigger] fired verdict for group {gid} ({prob}) "
                  f"extinguished — group no longer active", flush=True)
            continue
        if not _transitions.problem_accepts_wake(conn, prob,
                                                 "inject_batch_done"):
            continue
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, gid, running):
            continue
        _enqueue_strategist(conn, gid, prob, priority=15)

    # T4 — structural stall trigger.
    # Fires when a problem has no open goals (BFS has nothing to
    # dispatch), no in-flight Backward/Builder/Forward worker, and
    # the root is not yet proved. Captures the failure mode polar
    # 2026-05-23 hit: a parent strategy with a shelved sub-goal sat
    # 'proposed' forever, parent goal stayed 'attempting' (filtered
    # out of `open_goals`), no spawn fired for 174 min until budget
    # exhaust. Routine T1 (60 min) eventually fires but Strategist
    # Noop'd 4 times because the snapshot ("X proved") didn't change
    # between ticks. T4 is the structural backstop: if we hit this
    # signal we KNOW the framework is deadlocked, so we wake
    # Strategist immediately + surface the stall in Context.md (see
    # `_section_stall_warning` in phase2_context). Strategist prompt
    # has the corresponding rule: don't Noop when stall section is
    # present.
    # v35 — stall is detected PER GROUP. The problem-wide reading cannot
    # see a child that ran out of moves while a sibling is busy (the
    # problem is not stalled, so nobody wakes), and when it does fire it
    # wakes the top group rather than the one that is actually stuck.
    if suppress_stall:
        return
    for _row in db.groups_stalled(conn, scope=scope, running=running):
        prob = str(_row["problem"])
        gid = int(_row["id"])
        if not _transitions.problem_accepts_wake(
                conn, prob, "inject_batch_done"):
            continue
        if db.problem_has_awaiting_human(conn, prob):
            continue
        if _strategist_inflight(conn, gid, running):
            continue
        # Observability (user-requested 2026-07-04): the stall wake's
        # trigger_kind is deliberately conflated with inject_batch_done
        # at spawn, so this line is the ONLY record distinguishing a T4
        # rescue from the cascade batch-done relay (which dedups this
        # enqueue away whenever it got there first). grep '[stall-wake]'
        # to measure the accidental-stall rate.
        print(f"[stall-wake] T4 enqueued Strategist for {prob} "
              f"group {gid} (no batch-done relay covered this stall)",
              flush=True)
        _enqueue_strategist(conn, gid, prob, priority=10)


# ---------------------------------------------------------------------
# Worker thread body
# ---------------------------------------------------------------------

def _routine_due(conn: sqlite3.Connection, problem: str,
                 interval_min: float,
                 since_iso: "str | None" = None,
                 group_id: "int | None" = None) -> bool:
    """Per-problem mirror of `db.problems_needing_t1`'s clock (the
    derivation-side twin the routine trigger never had — user ruling
    2026-07-12: the periodic wake outranks event classification).
    Anchor = the later of
    `problems.last_routine_at` (bumped only by a routine commit) and
    `since_iso` (daemon start — down-time excluded); NULL anchor with a
    running daemon means "never routine'd", due `interval_min` after
    start, exactly like the T1 enqueue side.

    v35 — `group_id` reads THAT group's clock instead of the problem's,
    keeping this twin aligned with the enqueue side now that the seat is
    per group. The two must agree or a wake gets classified against a
    clock that did not select it."""
    if not interval_min or interval_min <= 0:
        return False
    if group_id is not None:
        row = conn.execute(
            "SELECT last_routine_at FROM groups WHERE id = ?",
            (int(group_id),),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT last_routine_at FROM problems WHERE name = ?",
            (problem,),
        ).fetchone()
    if row is None:
        return False
    anchor = row["last_routine_at"]
    if since_iso and (not anchor or str(since_iso) > str(anchor)):
        anchor = since_iso
    if not anchor:
        return False
    try:
        anchor_dt = datetime.fromisoformat(str(anchor))
        now_dt = datetime.fromisoformat(db.now())
    except ValueError:
        return False
    return (now_dt - anchor_dt).total_seconds() >= interval_min * 60.0


def _warn_consecutive_strategist(conn: sqlite3.Connection, problem: str,
                                 trigger: str) -> None:
    """Observability probe (user call 2026-07-11): back-to-back Strategist
    pipelines on one problem are a design smell — the batch cycle exists
    to force a Strategist commit to be FOLLOWED by other pipelines; the
    only expected shape is a shelve-review wake followed by a stall wake.
    Print-only, never blocks: grep '[consecutive-strategist]' to measure
    the rate (same pattern as '[stall-wake]'). A problem with anything
    still in flight (leased queue row — v17 leases persist while a worker
    runs) is skipped: the in-between pipeline just has no row yet."""
    try:
        inflight = conn.execute(
            "SELECT 1 FROM queue q"
            " LEFT JOIN goals g ON q.target_kind = 'Goal'"
            "   AND g.id = CAST(q.target_id AS INTEGER)"
            " WHERE q.kind != 'Strategist'"
            "   AND ((q.target_kind = 'Goal' AND g.problem = ?)"
            "     OR (q.target_kind = 'Problem' AND q.target_id = ?))"
            " LIMIT 1", (problem, problem)).fetchone()
        if inflight is not None:
            return
        row = conn.execute(
            # v38: exclude in-flight rows — this probe runs INSIDE the
            # Strategist worker, whose own dispatch-time 'running' row
            # would otherwise always be the newest match.
            "SELECT p.kind, p.id FROM pipelines p"
            " LEFT JOIN goals g ON p.target_kind = 'Goal'"
            "   AND g.id = CAST(p.target_id AS INTEGER)"
            " WHERE p.status != 'running'"
            "   AND ((p.target_kind = 'Problem' AND p.target_id = ?)"
            "    OR (p.target_kind = 'Goal' AND g.problem = ?))"
            " ORDER BY p.started_at DESC LIMIT 1",
            (problem, problem)).fetchone()
        if row is not None and str(row["kind"]) == "Strategist":
            print(f"[consecutive-strategist] {problem}: this wake "
                  f"(trigger={trigger}) follows Strategist pipeline "
                  f"{row['id']} with no other pipeline in between — "
                  f"expected only for shelve-review → stall", flush=True)
    except Exception:  # noqa: BLE001 — probe must never break dispatch
        pass


def _strategist_target(conn: sqlite3.Connection, target_id: str,
                       target_kind: str) -> "tuple[int | None, str | None]":
    """Resolve a queued Strategist row to `(group_id, problem)`.

    v35 rows carry `target_kind='Group'` and the group id. Rows queued
    before v35 (or by any caller that still speaks the old shape) carry
    the problem name with `target_kind='Problem'`; those resolve to the
    problem's top group, which is what they always meant. Returns
    `(None, None)` when the row points at something that no longer
    exists — the caller reports `problem_not_found` rather than crashing
    the worker thread."""
    if target_kind == "Group":
        try:
            gid = int(target_id)
        except (TypeError, ValueError):
            return None, None
        row = conn.execute("SELECT problem FROM groups WHERE id = ?",
                           (gid,)).fetchone()
        if row is None:
            return None, None
        return gid, str(row["problem"])
    problem = str(target_id)
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (problem,)).fetchone() is None:
        return None, None
    return _groups.ensure_top_group(conn, problem), problem


def _derive_strategist_trigger(conn: sqlite3.Connection,
                                problem: str, *,
                                group_id: "int | None" = None,
                                routine_interval_min: float = 0.0,
                                since_iso: "str | None" = None,
                                ) -> tuple[str, int | None]:
    """Pick `trigger_kind` for a Strategist run on `problem`. Returns
    `(trigger, pending_review_id)` where pending_review_id is non-None
    iff a goal awaits review (regardless of the returned trigger).

    Priority order (user ruling 2026-07-12 — the PERIODIC wake outranks
    events): the design intent for routine is unconditional periodic
    dispatch; classifying it below the event conditions let a busy
    problem starve it indefinitely (stokes 2026-06-12: 0 routine over
    5h; b6 2026-07-12: a self-sustaining inject→reject→batch-done loop
    kept the belief-fixing wake out forever). Event conditions are
    PERSISTENT state (an unacknowledged batch / a pending goal does not
    evaporate), so losing one seat to the periodic wake only delays the
    event by one wake; the clock re-arms only on a routine commit, so a
    stolen seat re-fires the timer next tick. (The separate 'audit'
    trigger is retired 2026-07-25 — its belief sweep is phase 1 of the
    routine wake.)

      1. `routine` — the routine clock is due (`routine_interval_min`
         of RUNNING time since last routine commit; `since_iso`
         excludes down-time).
      2. `inject_batch_done` — unacknowledged Inject batch resolved.
      3. `pending_review` — a goal awaits a verdict.
      4. `inject_batch_done` again, on a structural STALL — the "empty
         batch done" reading (Phase 6, first_launch's replacement):
         only inject_batch_done.md carries the mandatory-advance rule,
         so classifying these wakes as routine invites a Noop →
         re-stall → re-wake livelock (P13 2026-06-13 shape).
      5. `routine` — residual (a seat whose reason resolved meanwhile).
    """
    # v35 — the lowest pending id in the PROBLEM may belong to another
    # group; handing it over asks group A to adjudicate B's goal. Pick
    # the lowest pending id this group actually owns.
    pending_id = None
    for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ?"
        "   AND status = 'pending_strategist_review' ORDER BY id",
        (problem,),
    ).fetchall():
        if group_id is None:
            pending_id = int(r["id"])
            break
        owner = _groups.group_for_goal(conn, problem, int(r["id"]))
        if owner is not None and int(owner["id"]) == int(group_id):
            pending_id = int(r["id"])
            break
    if _routine_due(conn, problem, routine_interval_min,
                    since_iso=since_iso, group_id=group_id):
        return ("routine", pending_id)
    # A FIRED routine audit is persistent state (routine_verdicts row,
    # acted_at NULL) the way an unacknowledged batch is — it seats the
    # action wake right behind the periodic wake (owner design
    # 2026-08-30): the audit's findings go stale fastest.
    if group_id is not None:
        from ...pipeline.strategist import audit as _audit
        if _audit.pending_fired_verdict(conn, int(group_id)) is not None:
            return ("routine_fired", pending_id)
    unack_batches = db.unacknowledged_inject_batches(
        conn, problem, group_id)
    if unack_batches:
        return ("inject_batch_done", pending_id)
    if pending_id is not None:
        return ("pending_review", pending_id)
    # No running-set here (worker thread) — queue-only in-flight check;
    # a brief false-stall just classifies this wake as batch-done, which
    # is benign (same context, stricter advance rule). v35 — ask about
    # THIS group's slice, matching the T4 enqueue side.
    stalled = (db.is_group_stalled(conn, problem, group_id)
               if group_id is not None
               else db.is_problem_stalled(conn, problem))
    if stalled:
        # 'stall' is a FIRST-CLASS kind since 2026-08-24 (owner ruling,
        # reversing the deliberate 2026-07-04 conflation with
        # inject_batch_done): every T4 rescue may mark an upstream
        # anomaly — a dead Strategist wake, a relay gap — and the
        # conflation made the rate invisible to the DB (grep-only via
        # the '[stall-wake]' log line). The wake BEHAVES as batch-done
        # everywhere (same prompt, same mandatory-advance gate, same
        # reopen-promise section); only the recorded identity differs.
        return ("stall", pending_id)
    return ("routine", pending_id)


def _row_is_stale(conn: sqlite3.Connection,
                  target_id: str, kind: str,
                  target_kind: str = "Problem") -> bool:
    """A queued row whose target has already reached a terminal state
    is dropped at THIS door — the one place every dispatch passes.

    Goal rows (Formalizer / Builder): the goal settled between enqueue
    and pop — proved by an OR-parallel racer, shelved by a cascade, or
    dead. Backward's in-pipeline race-guards (`goal_no_longer_open`)
    still catch a mid-spawn flip; this check catches the pre-spawn one
    so the whole spawn is never paid. Statuses that legitimately
    dispatch are exactly `open` / `attempting` (a rescue Delegate
    promotes its anchor to `attempting` at commit, before the row pops).

    A queued Strategist whose problem has already committed `Ingest`
    has nothing left to decide — it would only spawn, Noop, and advance
    `last_strategist_at`. The dispatcher drops such a popped row.

    Phase 6 — the old drop condition (root goal `proved`) is exactly
    wrong now: a root-proved problem is where the Strategist must wake to
    judge the charter and commit `Ingest` (the only exit trigger), so
    the drop keys off the problem terminal state instead. If a rollback
    later revokes the Ingest (post-Ingest un-prove), the problem re-enters
    the live path and the normal triggers re-fire.

    v35 — a Strategist row is keyed by GROUP (`target_kind='Group'`,
    `target_id` the group id); pre-v35 rows carry the problem name with
    `target_kind='Problem'`. Both resolve through `_strategist_target`,
    so the terminal check keeps asking the same question of the same
    problem.

    The two unresolvable cases are NOT symmetric. A `Group` row naming a
    group that no longer exists is definitively garbage — group ids are
    never reused, so nothing can bring it back, and spawning would only
    fail. An unresolvable `Problem` row keeps the pre-v35 answer ("not
    stale"): that branch is reached by a name, and refusing to drop on a
    name we cannot resolve is the anti-wedge default it was given.
    """
    if str(target_kind or "") == "Goal" and kind in (
            "Formalizer", "Builder"):
        row = conn.execute(
            "SELECT status FROM goals WHERE id = ?",
            (str(target_id),)).fetchone()
        if row is None:
            return True
        return str(row["status"]) not in ("open", "attempting")
    if kind != "Strategist":
        return False
    kind_str = str(target_kind or "Problem")
    _gid, problem = _strategist_target(conn, str(target_id), kind_str)
    if problem is None:
        return kind_str == "Group"
    # A group at a terminal status holds no seat — `db.groups_needing_t1`
    # has said so since v35 and filters the periodic clock on it. The
    # EVENT path never learned it: `maybe_enqueue_inject_batch_done`
    # wakes whichever group authored the settling batch, and a group that
    # Ingested while one of its own Injects was still in flight gets
    # woken by that Inject landing. It then plans a fresh batch on a
    # charter it has already delivered, and the judge passes it, having
    # no way to know the group left.
    #
    # Measured 2026-08-13/14 on union_closed: groups 383 and 381 ran two
    # post-delivery batches each — four batches, five adversary rounds,
    # on charters whose parents had already consumed the bricks. One fact
    # ("terminal groups do not dispatch") with two homes, and only the
    # clock knew it. This is the door every dispatch passes.
    if kind_str == "Group":
        from ...state import groups as _groups
        row = conn.execute(
            "SELECT status FROM groups WHERE id = ?",
            (str(target_id),)).fetchone()
        if row is not None and str(row["status"]) in _groups.TERMINAL_STATUSES:
            return True
    return db.problem_ingested(conn, problem)
