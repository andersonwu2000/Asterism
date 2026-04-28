"""find_subgoals stage (P3 C22).

Wraps Tooling.subsystems.search to look up existing local Goals that might
be reusable as sub-goals of a new Backward decomposition. This is the
dedupe gate operating BEFORE Backward proposes new sub-goals — if a
candidate sub-goal already exists in this Problem, the new strategy
should reference it rather than duplicate.

Public API:
    find_subgoals(conn, goal) -> list[dict]

Returns sub-goal candidates from local_goals scope (current Problem only).
Each entry: {"id": int, "slug": str, "lean_path": str, "statement_hash":
str|None}.

Cross-Problem search is intentionally excluded (impl §2.2: local_goals
scope hash key participates in problem to prevent A INSERT collisions
wiping B cache). Library scope (Library/Theorems/proved.lean) IS reachable
once P6 lands but for P3 returns []; that's the find_lemmas concern, not
find_subgoals.
"""
from __future__ import annotations

import sqlite3


from Tooling.subsystems.search import search


def find_subgoals(
    conn: sqlite3.Connection,
    goal: dict,
) -> list[dict]:
    """Return existing local Goals matching the candidate decomposition query.

    `goal` should have at least 'slug' and 'problem'.
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
    return result.results
