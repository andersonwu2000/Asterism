"""failure_archive stage (P3 C24).

After a Pipeline outcome is exhausted/unproductive, this stage:

    1. Counts the goal's prior dead_attempts for the same pipeline_kind
       with outcomes ∈ {exhausted, unproductive}.
    2. If the count reaches N_BLOCK_AFTER_FAILURES (default 5), persists
       pipeline_kind into goals.blocked_pipelines via
       Tooling.subsystems.blocked_pipelines.

Builder needs_decomp / bad_goal outcomes are NOT counted (phase3_cache.md
§In line 117): the former is the expected "please decompose" branch,
the latter records sub-goal-level lessons for the parent.

This stage does NOT itself INSERT dead_attempts rows — that responsibility
stays with the calling pipeline (Builder._record_dead_attempts,
scheduler._cascade_*). failure_archive only reads + dispatches the block.

Public API:
    archive_check(conn, goal_id, pipeline_kind,
                  threshold=N_BLOCK_AFTER_FAILURES) -> bool
        True if pipeline_kind got blocked this call.
"""
from __future__ import annotations

import sqlite3

from Tooling.subsystems.blocked_pipelines import block_pipeline, is_blocked


N_BLOCK_AFTER_FAILURES: int = 5
_COUNTABLE_OUTCOMES: tuple[str, ...] = ("exhausted", "unproductive")
# spike-008 D-08-1; phase3 §Config 行 170 lists this as `ih_trap_similarity_threshold`.
# Hoisted to module level so P7 Strategist tuning is one grep away.
IH_TRAP_SIMILARITY_THRESHOLD: float = 0.85


def archive_check(
    conn: sqlite3.Connection,
    goal_id: int,
    pipeline_kind: str,
    threshold: int = N_BLOCK_AFTER_FAILURES,
) -> bool:
    """Check failure count for (goal_id, pipeline_kind) and block if at threshold.

    Args:
      conn: live sqlite3 connection.
      goal_id: target Goal id (target_kind='Goal' rows in dead_attempts).
      pipeline_kind: e.g. 'Backward', 'Builder'.
      threshold: failure count at which to block (default 5 per phase3 §Config).

    Returns:
      True if a block was newly added on this call. False if not yet at
      threshold OR if already blocked (idempotent).
    """
    if is_blocked(conn, goal_id, pipeline_kind):
        return False

    # Generic count (Builder needs_decomp / bad_goal excluded by outcome filter).
    placeholders = ",".join("?" * len(_COUNTABLE_OUTCOMES))
    count = conn.execute(
        f"SELECT COUNT(*) FROM dead_attempts "
        f"WHERE target_id = ? AND target_kind = 'Goal' "
        f"AND pipeline_kind = ? "
        f"AND outcome IN ({placeholders})",
        (str(goal_id), pipeline_kind, *_COUNTABLE_OUTCOMES),
    ).fetchone()[0]

    if count < threshold:
        return False

    return block_pipeline(conn, goal_id, pipeline_kind)


def archive_ih_trap(
    conn: sqlite3.Connection,
    goal_id: int,
    pipeline_kind: str = "Backward",
) -> bool:
    """IH-trap special case: block pipeline_kind immediately when the goal
    has 2 consecutive recent unproductive Backward outcomes AND the most
    recent strategies row carries parent_subgoal_max_similarity >=
    IH_TRAP_SIMILARITY_THRESHOLD.

    spec phase3_cache.md §In line 116-118: "Strategy 連續 ≥ 2 次 unproductive
    AND parent_subgoal_max_similarity ≥ threshold → 立即 UPDATE
    blocked_pipelines (不等 N=5)".

    Spec literal interpretation (R3 audit MED-4 clarification):
      - Spec subject is "Strategy" but the unproductive *outcome* is recorded
        per Backward pipeline run with target_kind='Goal' (the strategy
        itself stays in 'proposed' status when its parent decomposition is
        unproductive — there is no Strategy-side outcome row in this flow).
        So we read the goal-side dead_attempts as the proxy for "Strategy's
        outcome".
      - "Strategy similarity ≥ threshold" is interpreted as the most recent
        live strategy's parent_subgoal_max_similarity column (the new
        proposal that's currently exhibiting the IH-trap pattern). If a
        later strategy proves successful with low similarity, this trigger
        does not fire (mixed-outcome streak breaks the 2-unproductive run).

    Returns True if newly blocked. Threshold = IH_TRAP_SIMILARITY_THRESHOLD
    (module constant, spike-008 D-08-1).
    """
    if is_blocked(conn, goal_id, pipeline_kind):
        return False

    # Last 2 dead_attempts for this goal+pipeline_kind.
    last_two = conn.execute(
        "SELECT outcome FROM dead_attempts "
        "WHERE target_id = ? AND target_kind = 'Goal' AND pipeline_kind = ? "
        "ORDER BY ts DESC LIMIT 2",
        (str(goal_id), pipeline_kind),
    ).fetchall()

    if len(last_two) < 2:
        return False
    if not all(r[0] == "unproductive" for r in last_two):
        return False

    # Most recent strategy on this goal: its similarity score.
    sim_row = conn.execute(
        "SELECT parent_subgoal_max_similarity FROM strategies "
        "WHERE goal_id = ? AND commit_state = 'live' "
        "ORDER BY id DESC LIMIT 1",
        (goal_id,),
    ).fetchone()
    if sim_row is None or sim_row[0] is None:
        return False
    if sim_row[0] < IH_TRAP_SIMILARITY_THRESHOLD:
        return False

    return block_pipeline(conn, goal_id, pipeline_kind)
