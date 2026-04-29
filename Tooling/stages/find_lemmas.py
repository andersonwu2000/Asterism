"""find_lemmas stage (P3 C22; P6.x patch 28 library wire).

Wraps Tooling.subsystems.search to look up candidate lemmas in mathlib +
library scopes. Used by Backward agent prompt and Builder tactic_llm prompt
to surface relevant existing lemmas.

Public API:
    find_lemmas(conn, goal, lake_cwd=None) -> list[dict]

Returns candidate lemmas; each entry follows search shape:
{"name": str, "type": str, "score": float}.

  - mathlib scope: still stub ([]); full Mathlib walker deferred.
  - library scope: P6.x patch 28 returns sibling proved goals from the
    same Problem (DB-backed). problem_scope is taken from goal['problem'].

The query is derived from the goal's slug + statement (`question` column
when set). Library scope ignores the query (returns all proved siblings)
since the agent benefits from full visibility; richer ranking lands when
the count grows past prompt budget.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.subsystems.search import search


def find_lemmas(
    conn: sqlite3.Connection,
    goal: dict,
    lake_cwd: str | Path | None = None,
) -> list[dict]:
    """Return candidate lemmas from mathlib + library scopes.

    `goal` should have at least 'slug'; 'question' (the statement) is
    appended when present.
    """
    query_parts = [str(goal.get("slug", ""))]
    statement = goal.get("question") or ""
    if statement:
        query_parts.append(statement)
    query = " ".join(p for p in query_parts if p).strip()
    if not query:
        return []

    results: list[dict] = []
    # Mathlib scope first (broader corpus); then library (Problem-local
    # proved siblings). mathlib still stub returning []; library is now
    # DB-backed (P6.x patch 28).
    mathlib = search(query, scope="mathlib", kind="find_lemmas",
                     conn=conn, lake_cwd=lake_cwd)
    library = search(query, scope="library", kind="find_lemmas",
                     conn=conn, lake_cwd=lake_cwd,
                     problem_scope=str(goal.get("problem") or ""))
    results.extend(mathlib.results)
    results.extend(library.results)
    return results
