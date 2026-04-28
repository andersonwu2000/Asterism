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

Trigger point — pending vs live:
    spec §2.3 says "INSERT/UPDATE goals", but the implementation only fires
    inside CommitWriter.finalize() (pending → live transition) and at the
    three scheduler.py direct UPDATE sites that flip live rows. Pending
    rows are excluded from search/dedupe queries via `WHERE commit_state =
    'live'` (impl §1 commit protocol) so they cannot poison cache; firing
    on `begin()` would be wasted work. Aligns with phase3_cache.md:199
    "CommitWriter `finalize()` 統一鉤子".

Public API:
    invalidate_for_goals_write(conn, problem=None) -> int
        Returns total rows deleted (test verification helper).
        `problem` is currently unused but kept in the signature so call
        sites can pass it now and have it become a SQL filter once the
        schema gap is resolved.

When P6 unblocks the schema gap and you want problem-scoped filtering,
grep for `invalidate_for_goals_write(` to find every call site (currently
4: commit.py finalize() + scheduler.py three inline sites) and route the
goal's problem name through. CommitWriter.finalize() can read it from the
goals row directly; scheduler sites have it in scope already.

TX semantics:
    invalidate_for_goals_write opens its own short TX via `with conn:`. It
    composes correctly only when the caller's preceding goals UPDATE has
    already committed — i.e. the caller's `with self.conn:` block has
    exited. All four current call sites do this: finalize() and the three
    scheduler sites all exit their UPDATE TX before calling here.

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


def invalidate_for_library_write(conn: sqlite3.Connection) -> int:
    """Delete cache rows triggered by a Library write (P6 C43).

    Spec impl §2.3 字面: "Library/Theorems/proved.lean append 或
    Library/Counterexamples / Constructions 寫入 → DELETE search_cache
    WHERE scope LIKE '%library%'". The P3 cache infrastructure
    (search_cache + scope-keyed invalidation) was already in place
    when P4/P5 wrote silver-verdict json artifacts; P6 wires the
    Library promotion path to call this so the library scope is
    actually flushed when entries change.

    Args:
      conn: live sqlite3 connection.

    Returns:
      Rows deleted under the library scope.

    Raises:
      sqlite3.Error: caller must observe.
    """
    with conn:
        cur = conn.execute(
            "DELETE FROM search_cache WHERE scope LIKE '%library%'"
        )
        return cur.rowcount
