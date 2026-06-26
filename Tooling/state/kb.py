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
from pathlib import Path

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


def lesson_bullets(content: str) -> list[str]:
    """The `- <lesson>` bullet texts from a LESSONS.md body. Header / anchor
    comment lines (`<!-- ... -->`) don't start with `- `, so they fall out.
    The canonical parser shared by the reflection write-path and the migration."""
    out: list[str] = []
    for ln in content.splitlines():
        s = ln.lstrip()
        if s.startswith("- "):
            text = s[2:].strip()
            if text:
                out.append(text)
    return out


def migrate_all_lessons(conn: sqlite3.Connection, workspace: Path) -> int:
    """One-shot bootstrap: re-sync every registered problem's `LESSONS.md`
    bullets into the KB as reflection lessons. Idempotent (delegates to
    `replace_reflection_lessons`), so re-running is safe and re-converges the
    KB to the on-disk files. Returns the number of problems with ≥1 bullet."""
    migrated = 0
    for row in conn.execute("SELECT name FROM problems ORDER BY name"):
        problem = row["name"]
        path = db.problem_dir(workspace, problem) / "LESSONS.md"
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        bullets = lesson_bullets(content)
        if bullets:
            replace_reflection_lessons(conn, problem, bullets)
            migrated += 1
    return migrated


def query(conn: sqlite3.Connection, *, problem: str,
          goal_id: int | None = None) -> dict[str, list[sqlite3.Row]]:
    """Retrieval seam for the read path and the (future) LLM preprocessing layer:
    the KB knowledge relevant to a proving context, split by type. Currently
    problem-scoped; the scope-aware ancestor / Library-tree-path walk lands with
    the Library tier. `goal_id` is accepted now so callers bind to the stable
    signature before that retrieval grows."""
    rows = entries_for_problem(conn, problem)
    return {
        "lessons": [r for r in rows if r["type"] == "lesson"],
        "antipatterns": [r for r in rows if r["type"] == "antipattern"],
    }


def replace_reflection_lessons(conn: sqlite3.Connection, problem: str,
                               titles: list[str]) -> None:
    """Re-sync a problem's reflection-authored lesson entries to `titles` (the
    current LESSONS.md bullets). Deletes the prior reflection lessons and
    re-inserts, so corrections and removals propagate — not just appends.
    Scoped to `type='lesson' AND provenance='reflection'`, leaving legacy-
    migrated lessons and antipattern entries untouched."""
    conn.execute(
        "DELETE FROM kb_entries WHERE problem = ? AND type = 'lesson'"
        " AND provenance = 'reflection'",
        (problem,),
    )
    ts = db.now()
    conn.executemany(
        "INSERT INTO kb_entries"
        " (type, title, body, problem, node_id, scope, provenance, created_at)"
        " VALUES ('lesson', ?, '', ?, NULL, 'problem', 'reflection', ?)",
        [(t, problem, ts) for t in titles],
    )
    conn.commit()
