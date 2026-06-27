"""Phase 12 informal knowledge base — lesson / antipattern entries.

Single source of truth for the KB type enum + row helpers. The CHECK
constraint on `kb_entries.type` (db.py) mirrors `KB_TYPES`; tests/test_kb.py
binds them (schema CHECK == runtime set), so adding a type is a single-point
change.

Stores only CONFIRMED informal knowledge: `lesson` (positive experience) and
`antipattern` (a wall an approach hit). Unverified guesses — a failed attempt's
"alternative direction" — are NOT stored here; they stay in the prior_partial
carry-over. Breadth reads off `node_id` alone: NULL = problem-wide / global,
set = bound to that goal node (the `scope` column was dropped in Phase 12).
"""
from __future__ import annotations

import sqlite3

from . import db

# Canonical type enum — the kb_entries.type CHECK constraint in db.py must
# equal this (tests/test_kb.py enforces the binding).
KB_TYPES = frozenset({"lesson", "antipattern"})


def insert_entry(
    conn: sqlite3.Connection,
    *,
    entry_type: str,
    title: str,
    body: str = "",
    problem: str | None = None,
    node_id: int | None = None,
    provenance: str = "",
) -> int:
    """Insert one KB entry; return its id. `node_id` NULL = problem-wide /
    global, set = bound to that goal node. The type enum is validated up front
    so a bad value fails loudly at the call site, not via a CHECK at commit."""
    if entry_type not in KB_TYPES:
        raise ValueError(
            f"unknown kb entry type {entry_type!r}; expected {sorted(KB_TYPES)}")
    cur = conn.execute(
        "INSERT INTO kb_entries"
        " (type, title, body, problem, node_id, provenance, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entry_type, title, body, problem, node_id, provenance, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_lesson(
    conn: sqlite3.Connection,
    *,
    problem: str,
    title: str,
    body: str = "",
    node_id: int | None = None,
    provenance: str,
) -> int:
    """Model B reflection write — append one lesson. `node_id` None = global /
    problem-wide (type-2, promotable), set = bound to that goal node (type-1,
    discarded at promotion). Idempotent on `provenance` (a per-reflection-spawn
    key like `reflection:<sid>`) so a re-fired spawn never double-inserts.
    Returns 1 if inserted, 0 if the source was already captured. No commit-time
    surprise: the type is fixed 'lesson'."""
    cur = conn.execute(
        "INSERT INTO kb_entries"
        " (type, title, body, problem, node_id, provenance, created_at)"
        " SELECT 'lesson', ?, ?, ?, ?, ?, ?"
        " WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE provenance = ?)",
        (title, body, problem, node_id, provenance, db.now(), provenance),
    )
    conn.commit()
    return cur.rowcount


def edit_global_lesson(
    conn: sqlite3.Connection,
    *,
    entry_id: int,
    problem: str,
    title: str,
    body: str = "",
) -> int:
    """Model B reflection write — correct / supersede an existing GLOBAL lesson
    in place (the C3-A 'a prior claim is now false' path). Scoped to the
    problem's global lessons (`node_id IS NULL`), so a stale / wrong id can
    never touch another problem's entry, a node-bound lesson, or an antipattern.
    Returns 1 if updated, 0 if the id matched no eligible row."""
    cur = conn.execute(
        "UPDATE kb_entries SET title = ?, body = ?"
        " WHERE id = ? AND problem = ? AND type = 'lesson' AND node_id IS NULL",
        (title, body, entry_id, problem),
    )
    conn.commit()
    return cur.rowcount


def global_lessons(conn: sqlite3.Connection,
                   problem: str) -> list[sqlite3.Row]:
    """A problem's GLOBAL lessons (id, title, body), oldest first — the surface
    the reflection prompt shows so the agent can dedup before adding or pick an
    id to edit. Node-bound lessons + antipatterns are excluded."""
    return conn.execute(
        "SELECT id, title, body FROM kb_entries"
        " WHERE problem = ? AND type = 'lesson' AND node_id IS NULL"
        " ORDER BY id",
        (problem,),
    ).fetchall()


def lessons_with_node_info(conn: sqlite3.Connection,
                           problem: str) -> list[sqlite3.Row]:
    """Every lesson for `problem`, with each node-bound entry's goal slug /
    statement / status joined in (NULL columns for globals). Globals first,
    then node experience grouped by node, each block oldest-first. Feeds the
    grep-able `KB_LESSONS` file: the prover greps it for a goal analogous to
    its own and the joined slug/statement is the tree-structure context a flat
    title/body dump would lose."""
    return conn.execute(
        "SELECT k.id, k.title, k.body, k.node_id,"
        "       g.slug AS node_slug, g.statement AS node_statement,"
        "       g.status AS node_status "
        "FROM kb_entries k LEFT JOIN goals g ON g.id = k.node_id "
        "WHERE k.problem = ? AND k.type = 'lesson' "
        "ORDER BY (k.node_id IS NOT NULL), k.node_id, k.id",
        (problem,),
    ).fetchall()


def entries_for_problem(conn: sqlite3.Connection,
                        problem: str) -> list[sqlite3.Row]:
    """All KB entries owned by `problem`, oldest first. The scope-aware per-node
    retrieval walk (along the goal ancestor chain) lands in a later step; this
    is the problem-wide read the migration + read-path wiring build on."""
    return conn.execute(
        "SELECT * FROM kb_entries WHERE problem = ? ORDER BY id", (problem,)
    ).fetchall()


def query(conn: sqlite3.Connection, *, problem: str,
          goal_id: int | None = None) -> dict[str, list[sqlite3.Row]]:
    """Retrieval seam for the read path and the (future) LLM preprocessing layer:
    the KB knowledge relevant to a proving context, split by type. `goal_id`
    filters node-bound entries to their own goal (interim mechanical floor); the
    target-2 semantic-analog layer grows on this signature."""
    rows = entries_for_problem(conn, problem)

    def _visible(r: sqlite3.Row) -> bool:
        # Interim read (pre-target-2 semantic retrieval): a node-bound entry
        # (`node_id` set — a node-experience lesson OR an antipattern) is "what
        # was learned on THIS goal", surfaced only to its own goal; a
        # problem-wide entry (`node_id` NULL — global lesson / legacy) radiates
        # to every goal. Uniform across both types. target-2 later adds semantic
        # analog reach on top of this floor.
        return (goal_id is None or r["node_id"] is None
                or r["node_id"] == goal_id)

    return {
        "lessons": [r for r in rows
                    if r["type"] == "lesson" and _visible(r)],
        "antipatterns": [r for r in rows
                         if r["type"] == "antipattern" and _visible(r)],
    }
