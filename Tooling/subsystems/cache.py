"""Cache mutation invalidation hook (P3 C21).

Per impl §2.3, any goals INSERT/UPDATE invalidates two cache scopes:

    1. local_goals scope: spec wants `WHERE problem_scope='X' AND scope LIKE
       '%local_goals%'`. The schema_v1 search_cache table has no
       `problem_scope` column (P1 spec gap noted in C20 R2 audit MED-3) —
       so this implementation deletes ALL local_goals rows per goals write
       (over-invalidation, but never serves stale results). When P6 adds
       the column or another phase decides on the gap, this filter
       narrows.

    2. dedupe scope: spec says `WHERE mode='dedupe'` (dedupe is cross-Problem,
       so any goals write touches it). C20 R3 HIGH-2 wired dedupe rows to
       use `mode='dedupe'` so this filter actually matches.

Library writes (Library/Theorems/proved.lean append, Library/Counterexamples/
write) are P6 concerns and not handled here.

Public API:
    invalidate_for_goals_write(conn, problem=None) -> int
        Returns total rows deleted (test verification helper).
        `problem` is currently unused but kept in the signature so call sites
        can pass it now and have it become a SQL filter once the schema
        gap is resolved.

Silent-failure red lines:
    Spec §2.1: "走 mutation invalidation, 不靠 TTL". A failed invalidation
    means stale cache → wrong dedupe / search results in demo. We surface
    sqlite3.Error by re-raising — callers (CommitWriter.finalize,
    scheduler cascade paths) must observe the failure, not swallow it.
"""
from __future__ import annotations

import sqlite3


def invalidate_for_goals_write(
    conn: sqlite3.Connection,
    problem: str | None = None,
) -> int:
    """Delete cache rows triggered by a goals INSERT or UPDATE.

    Args:
      conn: live sqlite3 connection (caller's TX context — invalidation
            does NOT open its own TX so it composes with surrounding
            commits cleanly).
      problem: source goal's problem name (currently unused; reserved for
               P6 problem_scope-aware filter).

    Returns:
      Total rows deleted across both scopes.

    Raises:
      sqlite3.Error: caller must observe (no silent swallow).
    """
    _ = problem  # P6 reserved
    with conn:
        cur = conn.execute(
            "DELETE FROM search_cache WHERE scope LIKE '%local_goals%'"
        )
        local_goals_deleted = cur.rowcount
        cur = conn.execute(
            "DELETE FROM search_cache WHERE mode = 'dedupe'"
        )
        dedupe_deleted = cur.rowcount
    return local_goals_deleted + dedupe_deleted
