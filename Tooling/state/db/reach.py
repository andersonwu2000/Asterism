from __future__ import annotations

import sqlite3

from .core import now


# ---------------------------------------------------------------------
# Phase 6 — shared alive-reachability CTE (single source of truth)
# ---------------------------------------------------------------------
# Seed = root ∪ detached, then walk subgoals of live ('proposed' /
# 'succeeded') strategies of alive goals. Forward-injected goals are
# `detached=1` at insert (forward.py), so this ONE unconditional shape
# covers both classic (root present) and pure-NL (no root) problems — no
# root?-conditional seed needed. Historical divergence: per-problem copies
# with a root-only seed silently dropped detached Forward goals
# (`is_problem_stalled` cond-2, dedupe's alive walks) — every consumer of
# alive-reachability must build on these fragments.
# `goals_reachable_excluding` below keeps its own copy: its node-exclusion
# params thread through every branch and don't fit the shared shape.

ALIVE_CTE_GLOBAL = (
    "alive(id) AS ("
    "    SELECT id FROM goals WHERE origin = 'root'"
    "    UNION"
    "    SELECT id FROM goals WHERE detached = 1"
    "    UNION"
    "    SELECT g.id FROM goals g"
    "    JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
    "    JOIN strategies s ON s.id = ss.strategy_id"
    "    JOIN alive a ON a.id = s.goal_id"
    "    WHERE s.status IN ('proposed','succeeded')"
    ")"
)

# Binds TWO positional params: (problem, problem).
ALIVE_CTE_PER_PROBLEM = (
    "alive(id) AS ("
    "    SELECT id FROM goals WHERE problem = ? AND origin = 'root'"
    "    UNION"
    "    SELECT id FROM goals WHERE problem = ? AND detached = 1"
    "    UNION"
    "    SELECT g.id FROM goals g"
    "    JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
    "    JOIN strategies s ON s.id = ss.strategy_id"
    "    JOIN alive a ON a.id = s.goal_id"
    "    WHERE s.status IN ('proposed','succeeded')"
    ")"
)


def goals_reachable_excluding(conn: sqlite3.Connection, *,
                              problem: str,
                              exclude_goal_id: int) -> set[int]:
    """Goal ids in `problem` reachable from a root / detached seed via
    proposed|succeeded strategies WITHOUT passing through
    `exclude_goal_id` (it is removed as a node, cutting every path that
    ran through it — transitively, since the CTE never re-adds it).

    The shelve cascade uses this to spare a descendant of a just-
    terminated goal that still has an INDEPENDENT live path to root — a
    cross-branch cited / auto-linked sibling. A shared (multi-parent) DAG
    node must only be cascade-shelved when it loses its LAST live parent,
    not merely the one that just died; otherwise a goal another live
    strategy still needs becomes un-dispatchable and that strategy hangs.
    Mirrors `open_goals`' alive CTE (root ∪ detached ∪ subgoals-of-live-
    strategies-of-live-goals), scoped to one problem, minus the excluded
    node. Maintains the invariant `open ⇒ reachable`."""
    rows = conn.execute(
        "WITH RECURSIVE alive(id) AS ("
        "    SELECT id FROM goals"
        "      WHERE problem = ? AND origin = 'root' AND id != ?"
        "    UNION"
        "    SELECT id FROM goals"
        "      WHERE problem = ? AND detached = 1 AND id != ?"
        "    UNION"
        "    SELECT g.id FROM goals g"
        "    JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
        "    JOIN strategies s ON s.id = ss.strategy_id"
        "    JOIN alive a ON a.id = s.goal_id"
        "    WHERE g.problem = ? AND g.id != ?"
        "      AND s.status IN ('proposed','succeeded')"
        ") SELECT id FROM alive",
        (problem, exclude_goal_id, problem, exclude_goal_id,
         problem, exclude_goal_id),
    ).fetchall()
    return {int(r["id"]) for r in rows}


def open_goals(conn: sqlite3.Connection,
               *, scope: str | None = None) -> list[sqlite3.Row]:
    """Open goals eligible for dispatch.

    Walks the strategy DAG from each root: a goal is 'reachable' iff
    every strategy on some ancestor chain back to a root is alive
    ('proposed' or 'succeeded'). Open goals not reachable this way are
    orphaned by an upstream supersede / dead and must NOT be dispatched.

    The recursive CTE handles arbitrary depth — fixing the prior bug
    where a depth-2 sub-goal of a 'proposed' strategy was kept alive
    even when that strategy's own goal was orphaned upstream.

    `scope` (optional SQL LIKE pattern): when set, only return goals
    whose problem matches. Used by `dispatcher.run(scope=...)` so a
    benchmark daemon doesn't dispatch unrelated research problems
    sitting in the same workspace.
    """
    # Phase 2 — `detached=1` goals are dispatchable independently
    # (Strategist Reopen on a goal whose upward strategy chain is dead
    # auto-flagged them; framework treats them as if they have a live
    # parent strategy). UNION'd into the alive seed set so descendants
    # via their own live strategies also propagate.
    sql = (
        f"WITH RECURSIVE {ALIVE_CTE_GLOBAL} "
        "SELECT g.* FROM goals g "
        "JOIN problems p ON p.name = g.problem "
        "WHERE g.status = 'open' AND g.id IN alive "
        # Curry-Howard unified — any kind whose body carries `sorry`
        # is a deferred obligation and enters BFS. Mint commits
        # sorry-free outputs as 'proved' directly; sorry-bearing
        # outputs land here regardless of kind and dispatch as
        # Formalizer; `_skeleton.build_strategy_skeleton`
        # preserves the original `theorem|def|structure|class` keyword
        # in the strategy patch so the elaborator sees a matching
        # declaration head. Pre-unification this filter was
        # `g.kind = 'theorem'`, which silently stranded any
        # `def := sorry` Forward output at status='open' or hid the
        # stub behind a fake-proved status (brouwer 2026-05-22 G3).
        # Phase 5 — first-launch race protection now lives in goals.status:
        # root inits as 'frozen' and Strategist must explicitly
        # `Reopen(root)` to release BFS. The `g.status = 'open'` filter
        # above already excludes frozen roots, so no separate gate is
        # needed here. (Sub-goals never become frozen — only roots — so
        # this filter cleanly maps to the legacy bootstrap_done=1 gate
        # without ambiguity.)
    )
    params: tuple = ()
    if scope is not None:
        sql += "AND g.problem LIKE ? "
        params = (scope,)
    sql += "ORDER BY g.id"
    return list(conn.execute(sql, params))


def root_proved(conn: sqlite3.Connection, problem: str | None = None,
                scope: str | None = None) -> bool:
    """True iff all root goals in scope have status='proved'.

    `problem`: exact-match filter (single problem).
    `scope`: SQL LIKE pattern — matches `dispatcher.run(scope=...)`
        usage. Required for scoped runs: an unfiltered call checks
        every root in the DB, so a `--scope sylvester_gallai` run
        whose SG root is proved returns False because miniF2F roots
        sitting in the same workspace are still open. Observed
        2026-05-19 SG run: root proved, daemon exit logged
        `roots_proved=False` + returned exit code 1 even though the
        scoped problem succeeded.
    """
    sql = "SELECT count(*) AS c FROM goals WHERE origin = 'root' AND status != 'proved'"
    args: tuple = ()
    if problem:
        sql += " AND problem = ?"
        args = (problem,)
    elif scope is not None:
        sql += " AND problem LIKE ?"
        args = (scope,)
    row = conn.execute(sql, args).fetchone()
    return row is not None and int(row["c"]) == 0


