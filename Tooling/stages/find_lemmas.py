"""find_lemmas stage (P3 C22).

Wraps Tooling.subsystems.search to look up candidate lemmas in mathlib +
library scopes. Used by Backward agent prompt and Builder tactic_llm prompt
to surface relevant existing lemmas.

Public API:
    find_lemmas(conn, goal, lake_cwd=None) -> list[dict]

Returns up to ~20 candidate lemmas; each entry follows search.lean output
shape: {"name": str, "type": str, "score": float}. Empty list when search
returns nothing (P3: search.lean stubs return [] for both scopes; real
implementation deferred to P5/P6 per phase3 doc Subsystem caveat).

The query is derived from the goal's slug + statement (`question` column
when set). For P3 demo simplicity a single concatenated query string is
used; richer query construction (e.g. type-pattern extraction) lands when
the search subsystem itself is upgraded.
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
    # promoted lemmas). Both are stubs in P3 returning empty; the merge
    # logic is here so P5/P6 can drop in real results without re-wiring
    # the Backward / Builder call sites.
    mathlib = search(query, scope="mathlib", kind="find_lemmas",
                     conn=conn, lake_cwd=lake_cwd)
    library = search(query, scope="library", kind="find_lemmas",
                     conn=conn, lake_cwd=lake_cwd)
    results.extend(mathlib.results)
    results.extend(library.results)
    return results
