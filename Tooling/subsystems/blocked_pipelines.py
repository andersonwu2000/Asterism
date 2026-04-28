"""blocked_pipelines persistence (P3 C24).

Per impl §6.X / phase3_cache.md §In: goals.blocked_pipelines is a JSON list
of pipeline_kind strings that the scheduler's structural-refill BFS skips
when enqueueing. P3 introduces two write triggers:

    1. Generic N=5: failure_archive stage detects N
       dead_attempts(target=goal, pipeline_kind=K, outcome ∈
       {exhausted, unproductive}) and persists 'K' into the JSON list.
    2. IH-trap: Backward.cascade detects (Strategy 連續 ≥ 2 次 unproductive
       AND parent_subgoal_max_similarity ≥ ih_trap_similarity_threshold)
       → block 'Backward' immediately, before N=5.

Spike-011 D-11-1 atomicity: WRITE goes through SQLite atomic SQL using
`json_insert` + `json_each NOT EXISTS` dedup guard, all inside one
single-statement UPDATE. Spike A2 (Python read-modify-write + plain
UPDATE) had 100% lost-update rate; only strategy B (atomic SQL with
single-statement json_insert) was race-safe. The
`commit_state = 'live'` filter prevents writes against pending rows
(impl §1 commit protocol).

Public API:
    block_pipeline(conn, goal_id, pipeline_kind) -> bool  # newly added
    get_blocked_pipelines(conn, goal_id) -> list[str]
    is_blocked(conn, goal_id, pipeline_kind) -> bool
    unblock_pipeline(conn, goal_id, pipeline_kind=None) -> int
"""
from __future__ import annotations

import json
import sqlite3


_VALID_PIPELINE_KINDS: frozenset[str] = frozenset({
    "Builder", "Backward", "Refuter", "Forward",
    "Generalizer", "Counterexample", "ConstructionSearch", "Strategist",
})


def block_pipeline(
    conn: sqlite3.Connection,
    goal_id: int,
    pipeline_kind: str,
) -> bool:
    """Add `pipeline_kind` to goals.blocked_pipelines for `goal_id`.

    Atomic SQL per spike-011 D-11-1: single-statement json_insert with a
    json_each NOT EXISTS dedup guard. No race window, no read-modify-write.
    Idempotent: re-block returns False (UPDATE 0 rows because guard fails).

    Returns True iff a row was actually mutated (newly blocked AND target
    goal was live). False on either: pipeline_kind already in list, or
    goal_id has commit_state != 'live', or goal_id missing.

    Raises:
        ValueError: pipeline_kind not in schema CHECK enum.
        sqlite3.Error: caller observes DB failure (silent-failure red line).
    """
    if pipeline_kind not in _VALID_PIPELINE_KINDS:
        raise ValueError(
            f"unknown pipeline_kind: {pipeline_kind!r}; "
            f"valid: {sorted(_VALID_PIPELINE_KINDS)}"
        )
    with conn:
        cursor = conn.execute(
            """UPDATE goals
               SET blocked_pipelines = json_insert(
                   COALESCE(blocked_pipelines, '[]'), '$[#]', ?)
               WHERE id = ? AND commit_state = 'live'
                 AND NOT EXISTS (
                     SELECT 1 FROM json_each(
                         COALESCE(blocked_pipelines, '[]'))
                     WHERE value = ?)""",
            (pipeline_kind, goal_id, pipeline_kind),
        )
    return cursor.rowcount > 0


def get_blocked_pipelines(
    conn: sqlite3.Connection,
    goal_id: int,
) -> list[str]:
    """Return the current blocked_pipelines list for `goal_id` (empty if NULL).

    Reads only live rows; pending rows are invisible by spec.

    Raises:
        ValueError: stored JSON is corrupt (schema-level invariant violated;
            silent-failure red line — never fall back to []).
    """
    row = conn.execute(
        "SELECT blocked_pipelines FROM goals "
        "WHERE id = ? AND commit_state = 'live'",
        (goal_id,),
    ).fetchone()
    if row is None or row[0] is None:
        return []
    try:
        parsed = json.loads(row[0])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"goals.blocked_pipelines JSON corrupt for goal_id={goal_id}: "
            f"{exc}; raw={row[0]!r}"
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"goals.blocked_pipelines not a JSON list for goal_id={goal_id}: "
            f"{type(parsed).__name__}"
        )
    return parsed


def is_blocked(
    conn: sqlite3.Connection,
    goal_id: int,
    pipeline_kind: str,
) -> bool:
    """Convenience: True iff `pipeline_kind` is in goals.blocked_pipelines."""
    return pipeline_kind in get_blocked_pipelines(conn, goal_id)


def unblock_pipeline(
    conn: sqlite3.Connection,
    goal_id: int,
    pipeline_kind: str | None = None,
) -> int:
    """Remove `pipeline_kind` from goals.blocked_pipelines (or all if None).

    Used by `asterism goal unblock` CLI (P3 C26 manual rescue path).
    Returns count of entries removed.

    Atomic per HIGH-1 fix: clear-all uses single UPDATE; specific-kind
    uses subselect to compute new list inline (no Python read-modify-write
    round-trip). Both go through `WHERE commit_state='live'`.
    """
    if pipeline_kind is None:
        current = get_blocked_pipelines(conn, goal_id)
        if not current:
            return 0
        with conn:
            conn.execute(
                "UPDATE goals SET blocked_pipelines = '[]' "
                "WHERE id = ? AND commit_state = 'live'",
                (goal_id,),
            )
        return len(current)

    # Specific kind: SQLite has no list `remove`; we compute the filtered
    # list inline via json_group_array(json_each.value WHERE value != ?).
    with conn:
        cursor = conn.execute(
            """UPDATE goals
               SET blocked_pipelines = (
                   SELECT COALESCE(json_group_array(value), '[]')
                   FROM json_each(COALESCE(goals.blocked_pipelines, '[]'))
                   WHERE value != ?
               )
               WHERE id = ? AND commit_state = 'live'
                 AND EXISTS (
                     SELECT 1 FROM json_each(
                         COALESCE(goals.blocked_pipelines, '[]'))
                     WHERE value = ?)""",
            (pipeline_kind, goal_id, pipeline_kind),
        )
    # rowcount > 0 iff the EXISTS guard fired (kind was present).
    return 1 if cursor.rowcount > 0 else 0
