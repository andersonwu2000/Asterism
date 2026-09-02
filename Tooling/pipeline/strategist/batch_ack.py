"""strategist.batch_ack — which completed Inject batches a commit may
acknowledge.

A batch's REPORT (its per-step outcomes, worker replies and landed
slugs) reaches the Strategist through the Context's batch section, and a
batch stops being reported once it is acknowledged. Until 2026-09-03 the
acknowledgement was purely a clock: `groups.last_strategist_at`, bumped
by every commit, and a batch counted as delivered iff its last row
update was older than that stamp.

That was true while a wake was a snapshot: everything a wake could ever
learn about was already in its Context. Since the per-round refresh
(1c942b70 / ff9e9a6a) it is not. A batch that finishes MID-DEBATE
reaches the author as one delta line — enough to act on, not the report
— and the clock then swallowed it at commit, so its outcomes reached no
wake at all. A delta line is not the report.

The law, run once per commit before the clock is bumped:

  * a batch whose report this wake DELIVERED (it was in the Context the
    author read) is acknowledged — the wake received it, which is all
    acknowledgement ever meant;
  * a batch this wake ACTED ON is acknowledged: the landed decisions name
    one of its goals, so the Strategist has demonstrably read it;
  * anything else completed mid-debate is CARRIED — marked so the clock
    bump cannot swallow it, and the next wake gets the whole report.

Keyed by batch_id, never by goal id: two batches can work the same goal,
and the question is always "has THIS batch's report been delivered".
"""
from __future__ import annotations

import sqlite3

from ...state import db


def landed_goal_ids(conn: sqlite3.Connection,
                    row_ids: "list[int]") -> "set[int]":
    """The goals a committed batch of decisions ACTED ON: every row's
    `target_id` plus every goal it produced.

    Read off the committed ROWS, not the in-memory decisions, so the rule
    is kind-agnostic — `ConfirmShelve`, `MarkDeliverable`,
    `ReturnToParent`, `Delegate` and every kind added later name their
    goal in the same column, and none of them has to be listed here.
    """
    out: set[int] = set()
    for rid in row_ids:
        row = conn.execute(
            "SELECT target_id, produced_goal_id FROM strategist_decisions"
            " WHERE id = ?", (int(rid),)).fetchone()
        if row is None:
            continue
        for col in ("target_id", "produced_goal_id"):
            if row[col] is not None:
                out.add(int(row[col]))
    return out


def batch_goal_ids(conn: sqlite3.Connection, batch_id: str) -> "set[int]":
    """This batch's goal set: the goals its steps produced, the sub-goals
    MINTED by the strategies its steps produced, and their minted
    descendants.

    'minted' edges only (the `strategy_subgoals.link_kind` split): a
    CITED sibling has its own life and its own producing batch, so acting
    on it says nothing about having read this one.
    """
    goals: set[int] = set()
    strategies: set[int] = set()
    for row in conn.execute(
            "SELECT produced_goal_id, produced_strategy_id"
            " FROM strategist_decisions WHERE batch_id = ?", (batch_id,)):
        if row["produced_goal_id"] is not None:
            goals.add(int(row["produced_goal_id"]))
        if row["produced_strategy_id"] is not None:
            strategies.add(int(row["produced_strategy_id"]))
    fresh_goals = set(goals)
    while fresh_goals or strategies:
        for gid in fresh_goals:
            strategies.update(
                int(r["id"]) for r in conn.execute(
                    "SELECT id FROM strategies WHERE goal_id = ?", (gid,)))
        fresh_goals = set()
        for sid in strategies:
            for r in conn.execute(
                    "SELECT subgoal_id FROM strategy_subgoals"
                    " WHERE strategy_id = ? AND link_kind = 'minted'",
                    (sid,)):
                kid = int(r["subgoal_id"])
                if kid not in goals:
                    goals.add(kid)
                    fresh_goals.add(kid)
        strategies = set()
    return goals


def settle(conn: sqlite3.Connection, *, problem: str,
           group_id: "int | None",
           delivered: "list[str] | None",
           landed_row_ids: "list[int]") -> "tuple[list[str], list[str]]":
    """Apply the law to every batch of `group_id` still unacknowledged,
    and return `(acknowledged, carried)`.

    `delivered` is the batch roster this wake's Context actually carried
    (captured before it was compiled). `None` means "no wake framed this
    commit" — a direct caller or a test — and is read as "everything was
    delivered", i.e. exactly the pre-2026-09-03 clock behaviour.

    Writes only the carry marks. The acknowledgement itself is still the
    caller's clock bump, which must follow this call: a batch is
    acknowledged by NOT being carried past it.
    """
    unack = db.unacknowledged_inject_batches(conn, problem, group_id)
    if not unack:
        return [], []
    landed = landed_goal_ids(conn, landed_row_ids)
    acked: list[str] = []
    carried: list[str] = []
    for bid in unack:
        if (delivered is None or bid in delivered
                or (landed and (landed & batch_goal_ids(conn, bid)))):
            acked.append(bid)
        else:
            carried.append(bid)
    ts = db.now()
    for bid in acked:
        conn.execute(
            "UPDATE strategist_decisions SET report_carried_at = NULL"
            " WHERE batch_id = ? AND report_carried_at IS NOT NULL", (bid,))
    for bid in carried:
        conn.execute(
            "UPDATE strategist_decisions SET report_carried_at = ?"
            " WHERE batch_id = ? AND report_carried_at IS NULL", (ts, bid))
    conn.commit()
    if carried:
        print(f"[strategist] batch report carried to the next wake: "
              f"{', '.join(b[:8] for b in carried)} ({problem})", flush=True)
    return acked, carried
