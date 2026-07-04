"""Tree-level DB consistency sweep — the crash-window audit's predicates,
executable (task #11).

State propagation is deliberately non-transactional (every db helper
commits; architecture.md §13 rejects two-phase state) and the compensation
net — startup recovery, per-tick reconcile, inject backstop, root gate —
repairs single-row conditions. The 2026-07-04 crash-window audit
(failure_modes.md "Crash-window 補償對照表") found the net's blind spot is
TREE-level: a cascade interrupted mid-propagation leaves states no
single-row predicate sees (a succeeded strategy under an unproved goal, a
live strategy under a terminal goal, alive-looking goals unreachable from
any root). This module turns each audited window into a SQL predicate so
"is every half-state covered?" is a query, not an archaeology session.

Consumers: `asterism drift-check` (operator gate; run with the daemon
stopped — a mid-tick snapshot can transiently trip A2/A3-class rows) and
startup recovery (which auto-repairs the unambiguous subset).
"""
from __future__ import annotations

import sqlite3

from . import db as _db

# Hard-terminal goal statuses: a completed cascade never leaves a live
# strategy under one of these (proved → siblings superseded; the rest →
# inward-killed dead).
_TERMINAL_GOAL = ("proved", "disproved", "dead", "shelved")

# Phase 6 — single-source alive seed (root ∪ detached) lives in db.py;
# this copy already had the correct shape, now it can't drift.
_ALIVE_CTE = f"WITH RECURSIVE {_db.ALIVE_CTE_GLOBAL} "


def consistency_sweep(conn: sqlite3.Connection, *,
                      scope: "str | None" = None) -> "dict[str, list[dict]]":
    """Run every tree-level predicate; return {category: [row dicts]}.
    Empty dict values = consistent. Categories map 1:1 to audit windows:

      succeeded_strategy_unproved_goal — A2 (verify promote died between
        strategy→succeeded and goal→proved).
      live_strategy_terminal_goal — A3 / F3 / F4 inward-kill gaps (proved
        goal's losing sibling never superseded; shelve/kill cascade died
        mid-walk). `proposed` rows are auto-repaired at startup; `stalled`
        rows are report-only (no stalled→dead/superseded edge exists).
      open_with_proposed_strategy / attempting_without_live_strategy —
        the two startup-recovery predicates, promoted to assertions so a
        MID-RUN occurrence is visible before the next restart repairs it.
      unreachable_alive_goal — D2 / E2 / F4 zombies: open/attempting,
        not detached, not reachable from any root through live strategies
        — dispatch will never touch them, nothing ever terminals them,
        and proof_store.inventory cannot see them (file + row both exist).
      revival_pending — B1 signal: shelved goal whose alias target is
        proved; one housekeeping pass should revive it (persistent rows
        after a pass = investigate; the revival itself is idempotent since
        task #11).
    """
    like = scope or "%"

    def q(sql: str, *params) -> "list[dict]":
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    out: "dict[str, list[dict]]" = {}
    out["succeeded_strategy_unproved_goal"] = q(
        "SELECT s.id AS strategy_id, s.goal_id, g.status AS goal_status,"
        "       g.problem FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE s.status = 'succeeded' AND g.status != 'proved'"
        "   AND g.problem LIKE ?", like)
    out["live_strategy_terminal_goal"] = q(
        "SELECT s.id AS strategy_id, s.status AS strategy_status,"
        "       s.goal_id, g.status AS goal_status, g.problem"
        "  FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE s.status IN ('proposed','stalled')"
        "   AND g.status IN (?,?,?,?) AND g.problem LIKE ?",
        *_TERMINAL_GOAL, like)
    out["open_with_proposed_strategy"] = q(
        "SELECT DISTINCT g.id AS goal_id, g.problem FROM goals g"
        "  JOIN strategies s ON s.goal_id = g.id"
        " WHERE g.status = 'open' AND s.status = 'proposed'"
        "   AND g.problem LIKE ?", like)
    out["attempting_without_live_strategy"] = q(
        "SELECT g.id AS goal_id, g.problem FROM goals g"
        " WHERE g.status = 'attempting' AND g.problem LIKE ?"
        "   AND NOT EXISTS (SELECT 1 FROM strategies s"
        "                    WHERE s.goal_id = g.id"
        "                      AND s.status IN ('proposed','succeeded'))",
        like)
    out["unreachable_alive_goal"] = q(
        _ALIVE_CTE +
        "SELECT g.id AS goal_id, g.status, g.problem FROM goals g"
        " WHERE g.status IN ('open','attempting')"
        "   AND g.origin != 'root' AND g.detached = 0"
        "   AND g.id NOT IN alive AND g.problem LIKE ?", like)
    out["revival_pending"] = q(
        "SELECT g.id AS goal_id, g.alias_target_id, g.problem FROM goals g"
        "  JOIN goals x ON x.id = g.alias_target_id"
        " WHERE g.status = 'shelved' AND x.status = 'proved'"
        "   AND g.problem LIKE ?", like)
    return out


def repair_unambiguous(conn: sqlite3.Connection) -> "dict[str, int]":
    """Startup auto-repair for the sweep categories whose completed-cascade
    outcome is unambiguous — per-row through the CHECKED mutator (never a
    bulk UPDATE: the inject-outcome hook must fire, D6-lesson).

      live `proposed` strategy under a terminal goal:
        parent proved      → superseded (the OR race was won by a sibling)
        parent dead/disproved/shelved → dead (the inward-kill that the
                                        interrupted cascade owed it)
    `stalled` rows and every other category are report-only — their repair
    is either recovery's existing job or needs operator judgment."""
    from . import transitions
    fixed = {"superseded": 0, "dead": 0}
    rows = conn.execute(
        "SELECT s.id AS sid, g.status AS gstat FROM strategies s"
        "  JOIN goals g ON g.id = s.goal_id"
        " WHERE s.status = 'proposed' AND g.status IN (?,?,?,?)",
        _TERMINAL_GOAL).fetchall()
    for r in rows:
        to = "superseded" if r["gstat"] == "proved" else "dead"
        transitions.apply_strategy_transition(
            conn, int(r["sid"]), to,
            event="startup_terminal_parent_reconcile")
        fixed[to] += 1
    if any(fixed.values()):
        conn.commit()
        print(f"[recovery] terminal-parent strategies reconciled: "
              f"{fixed['superseded']} superseded, {fixed['dead']} dead "
              f"(interrupted-cascade repair, task #11)", flush=True)
    return fixed
