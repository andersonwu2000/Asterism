"""Inventory metrics for the Strategist agent prompt (P7 C49).

Aggregates DB state into a structured dict the Strategist prompt template
can serialize. Three SQL queries from impl §6.4:

  1. per-Goal      — for each live goal in `problem`: status, depth, age,
                     bad_goal_count, child strategy outcome counts.
  2. per-subtree   — recursive CTE rooted at origin='root' goals; reports
                     goal_count grouped by (root_id, depth).
  3. global top-N  — top 10 goals by bad_goal_count across all problems.

`collect(conn, problem)` returns a dict with all three sections plus a
small meta block (problem name, generated_at). Strategist prompt template
takes this dict and renders into prompt slots.

Public API:
    collect(conn, problem) -> dict
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# SQL definitions (impl §6.4)
# ---------------------------------------------------------------------------

_PER_GOAL_SQL = """
SELECT
    g.id,
    g.slug,
    g.status,
    g.depth,
    g.status_changed_at,
    (SELECT COUNT(*) FROM dead_attempts d
     WHERE d.target_id = g.id
       AND d.reason_summary LIKE 'bad sub-Goal%') AS bad_goal_count,
    (SELECT json_group_object(s.status, cnt)
     FROM (
        SELECT status, COUNT(*) AS cnt
        FROM strategies WHERE goal_id = g.id GROUP BY status
     ) s) AS child_strategy_outcomes
FROM goals g
WHERE g.problem = ? AND g.commit_state = 'live'
ORDER BY g.id ASC
"""

# Per-subtree recursive CTE — counts live goals at each depth under each
# root (origin='root') goal in the given Problem.
_PER_SUBTREE_SQL = """
WITH RECURSIVE subtree(root_id, current_id, depth) AS (
    SELECT id, id, depth FROM goals
     WHERE origin = 'root' AND problem = ? AND commit_state = 'live'
    UNION ALL
    SELECT s.root_id, sg.subgoal_id, g.depth
    FROM subtree s
    JOIN strategies st ON st.goal_id = s.current_id
                       AND st.commit_state = 'live'
    JOIN strategy_subgoals sg ON sg.strategy_id = st.id
    JOIN goals g ON g.id = sg.subgoal_id AND g.commit_state = 'live'
)
SELECT root_id, depth, COUNT(*) AS goal_count
FROM subtree
GROUP BY root_id, depth
ORDER BY root_id ASC, depth ASC
"""

_GLOBAL_TOP_N_SQL = """
SELECT g.id, g.slug, g.problem, COUNT(d.id) AS bg_count
FROM goals g LEFT JOIN dead_attempts d
  ON d.target_id = g.id AND d.reason_summary LIKE 'bad sub-Goal%'
WHERE g.commit_state = 'live'
GROUP BY g.id
HAVING bg_count > 0
ORDER BY bg_count DESC, g.id ASC
LIMIT ?
"""

DEFAULT_TOP_N = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attempting_age_min(now: datetime, status_changed_at: str | None) -> float | None:
    """Minutes since `status_changed_at` (ISO-8601 in UTC). None when blank."""
    if not status_changed_at:
        return None
    try:
        dt = datetime.fromisoformat(status_changed_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return round(delta.total_seconds() / 60.0, 3)


def _decode_child_outcomes(raw: str | None) -> dict[str, int]:
    """`json_group_object` returns a JSON string (or None when no rows)."""
    if not raw:
        return {}
    import json
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(obj, dict):
        return {}
    return {str(k): int(v) for k, v in obj.items() if isinstance(v, (int, float))}


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def collect(
    conn: sqlite3.Connection,
    problem: str,
    *,
    top_n: int = DEFAULT_TOP_N,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect Strategist inventory for a single Problem.

    `now` is injectable for deterministic age calculation in tests; defaults
    to UTC wall-clock.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    per_goal: list[dict[str, Any]] = []
    for row in conn.execute(_PER_GOAL_SQL, (problem,)).fetchall():
        gid, slug, status, depth, status_changed_at, bg_count, child_raw = row
        per_goal.append({
            "id": gid,
            "slug": slug,
            "status": status,
            "depth": depth,
            "attempting_age_min": _attempting_age_min(now, status_changed_at),
            "bad_goal_count": bg_count or 0,
            "child_strategy_outcomes": _decode_child_outcomes(child_raw),
        })

    per_subtree: list[dict[str, Any]] = [
        {"root_id": root_id, "depth": depth, "goal_count": goal_count}
        for (root_id, depth, goal_count) in conn.execute(
            _PER_SUBTREE_SQL, (problem,)
        ).fetchall()
    ]

    top_n_global: list[dict[str, Any]] = [
        {"id": gid, "slug": slug, "problem": prob, "bad_goal_count": bg_count}
        for (gid, slug, prob, bg_count) in conn.execute(
            _GLOBAL_TOP_N_SQL, (top_n,)
        ).fetchall()
    ]

    return {
        "meta": {
            "problem": problem,
            "generated_at": now.isoformat(),
            "top_n_limit": top_n,
        },
        "per_goal": per_goal,
        "per_subtree": per_subtree,
        "top_n_bad_goals_global": top_n_global,
    }
