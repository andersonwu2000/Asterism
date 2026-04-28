"""find_subgoals stage (P3 C22).

Wraps Tooling.subsystems.search to look up existing local Goals that might
be reusable as sub-goals of a new Backward decomposition. This is the
dedupe gate operating BEFORE Backward proposes new sub-goals — if a
candidate sub-goal already exists in this Problem, the new strategy
should reference it rather than duplicate.

Public API:
    find_subgoals(conn, goal) -> list[dict]

Returns sub-goal candidates from local_goals scope. Each entry:
    {"id": int, "slug": str, "lean_path": str, "statement_hash": str|None}.

Self-exclusion: when goal['id'] is provided, the parent goal itself is
filtered out of results (it cannot be its own sub-goal).

Cache key isolates Problem (problem_scope param feeds into hash) but the
underlying SQL filter by Problem is **deferred to P6**:
search.py:_search_local_goals queries `WHERE commit_state='live'` only —
cross-Problem rows leak through under P6 multi-Problem until search_cache
schema gets a problem_scope column (see C20 R3 MED-3, state.md:46). P3
single-Problem demo OK; P6 must amend schema or accept the leak.
"""
from __future__ import annotations

import sqlite3


from Tooling.subsystems.search import search


def find_subgoals(
    conn: sqlite3.Connection,
    goal: dict,
) -> list[dict]:
    """Return existing local Goals matching the candidate decomposition query.

    `goal` should have at least 'slug' and 'problem'. If 'id' is present,
    the parent goal itself is excluded (cannot be its own sub-goal — would
    be a no-op self-loop in the proof graph).
    """
    query = str(goal.get("slug", "")).strip()
    problem = str(goal.get("problem", "")).strip()
    if not query:
        return []

    result = search(
        query,
        scope="local_goals",
        kind="find_subgoals",
        conn=conn,
        problem_scope=problem,
    )
    parent_id = goal.get("id")
    if parent_id is None:
        return result.results
    return [r for r in result.results if r.get("id") != parent_id]
