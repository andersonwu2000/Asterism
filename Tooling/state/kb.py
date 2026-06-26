"""Phase 12 informal knowledge base — lesson / antipattern entries.

Single source of truth for the KB enum sets + row helpers. The CHECK
constraints on `kb_entries` (db.py) mirror these frozensets; tests/test_kb.py
binds them (schema CHECK == runtime set), so adding a type/scope is a
single-point change.

Stores only CONFIRMED informal knowledge: `lesson` (positive experience) and
`antipattern` (a wall an approach hit). Unverified guesses — a failed attempt's
"alternative direction" — are NOT stored here; they stay in the prior_partial
carry-over. Each entry mounts on the goal node it was learned on (`node_id`)
and radiates as far as `scope` allows during retrieval.
"""
from __future__ import annotations

import sqlite3

from . import db

# Canonical enum sets — the kb_entries CHECK constraints in db.py must equal
# these (tests/test_kb.py enforces the binding).
KB_TYPES = frozenset({"lesson", "antipattern"})
KB_SCOPES = frozenset({"node", "subtree", "problem", "domain"})


def insert_entry(
    conn: sqlite3.Connection,
    *,
    entry_type: str,
    title: str,
    body: str = "",
    problem: str | None = None,
    node_id: int | None = None,
    scope: str = "problem",
    provenance: str = "",
) -> int:
    """Insert one KB entry; return its id. The enums are validated up front so a
    bad value fails loudly at the call site, not via a CHECK at commit time."""
    if entry_type not in KB_TYPES:
        raise ValueError(
            f"unknown kb entry type {entry_type!r}; expected {sorted(KB_TYPES)}")
    if scope not in KB_SCOPES:
        raise ValueError(
            f"unknown kb scope {scope!r}; expected {sorted(KB_SCOPES)}")
    cur = conn.execute(
        "INSERT INTO kb_entries"
        " (type, title, body, problem, node_id, scope, provenance, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (entry_type, title, body, problem, node_id, scope, provenance, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def entries_for_problem(conn: sqlite3.Connection,
                        problem: str) -> list[sqlite3.Row]:
    """All KB entries owned by `problem`, oldest first. The scope-aware per-node
    retrieval walk (along the goal ancestor chain) lands in a later step; this
    is the problem-wide read the migration + read-path wiring build on."""
    return conn.execute(
        "SELECT * FROM kb_entries WHERE problem = ? ORDER BY id", (problem,)
    ).fetchall()
