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

Spike-011 D-11-1 confirmed SQLite WAL + single-statement json_insert is
atomic enough — no application-level lock needed. The
`commit_state = 'live'` filter prevents writes against pending rows
(impl §1 commit protocol).

Public API:
    block_pipeline(conn, goal_id, pipeline_kind) -> bool  # added or already in
    get_blocked_pipelines(conn, goal_id) -> list[str]
    is_blocked(conn, goal_id, pipeline_kind) -> bool
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

    Returns True if newly added (not already present), False if no-op.
    Idempotent: re-adding does not produce duplicates.

    Raises:
        ValueError: pipeline_kind not in schema CHECK enum.
        sqlite3.Error: caller observes DB failure (silent-failure red line).
    """
    if pipeline_kind not in _VALID_PIPELINE_KINDS:
        raise ValueError(
            f"unknown pipeline_kind: {pipeline_kind!r}; "
            f"valid: {sorted(_VALID_PIPELINE_KINDS)}"
        )

    current = get_blocked_pipelines(conn, goal_id)
    if pipeline_kind in current:
        return False

    new_list = current + [pipeline_kind]
    with conn:
        conn.execute(
            "UPDATE goals SET blocked_pipelines = ? "
            "WHERE id = ? AND commit_state = 'live'",
            (json.dumps(new_list), goal_id),
        )
    return True


def get_blocked_pipelines(
    conn: sqlite3.Connection,
    goal_id: int,
) -> list[str]:
    """Return the current blocked_pipelines list for `goal_id` (empty if NULL).

    Reads only live rows; pending rows are invisible by spec.
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
    except json.JSONDecodeError:
        # Corrupt JSON — treat as empty so BFS still makes progress.
        # Caller observability via callers' own logging if needed.
        return []
    return parsed if isinstance(parsed, list) else []


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
    """
    current = get_blocked_pipelines(conn, goal_id)
    if pipeline_kind is None:
        if not current:
            return 0
        with conn:
            conn.execute(
                "UPDATE goals SET blocked_pipelines = '[]' "
                "WHERE id = ? AND commit_state = 'live'",
                (goal_id,),
            )
        return len(current)

    if pipeline_kind not in current:
        return 0
    new_list = [k for k in current if k != pipeline_kind]
    with conn:
        conn.execute(
            "UPDATE goals SET blocked_pipelines = ? "
            "WHERE id = ? AND commit_state = 'live'",
            (json.dumps(new_list), goal_id),
        )
    return current.count(pipeline_kind)
