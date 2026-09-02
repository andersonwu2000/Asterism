"""state.projects — the Project row (human_interface_design.md §3.1).

A Project is the shelf a problem sits on: one folder in the UI, one
inbox, one Assistant session. Its SoT is the `projects` table (v48), and
`problems.project` is the only link — never a prefix re-derived at read
time, which is the whole point of the migration: a dotted problem name
picks the DEFAULT Project at registration, and from that moment the two
are independent. Renaming a Project must not move a directory, and
`Problems/<segment>/…` stays a problem's physical home whatever its
Project is later called.

Every mutator here is the single sanctioned writer of its column, so the
serve endpoints (`/api/projects`) hold no SQL of their own. Two refusal
types, because the write layer owes the caller two different answers:
`KeyError` = no such Project (404), `ValueError` = it exists and the
write is refused (409, the `amend.resolve_amend` shape).
"""
from __future__ import annotations

import re
import sqlite3

from . import db

#: One segment of a problem name. A Project name is exactly that — a
#: dotted one could never be any problem's first segment, so the same
#: rule that admits `Erdos` in `Erdos.p1` admits a Project called
#: `Erdos` and nothing else.
NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
#: The problem-name gate, composed from the segment rule so the two
#: cannot drift (serve's `create_problem_ep` reads it from here).
PROBLEM_NAME_RE = re.compile(
    rf"{NAME_RE.pattern}(\.{NAME_RE.pattern})*")
NAME_MAX = 120


class InvalidName(ValueError):
    """The name itself is malformed — 422, not 409 (§3.2 appendix ruling
    2026-09-02, matching `/api/problems/create`). A ValueError from the
    mutators means "the Project is there and the write is refused", which
    is a different answer to a different question; a caller that cannot
    tell them apart tells the person their name is taken when it is
    simply not a name. A subclass, so every existing `except ValueError`
    still catches it."""


def _validate(name: str) -> str:
    name = (name or "").strip()
    if not NAME_RE.fullmatch(name) or len(name) > NAME_MAX:
        raise InvalidName(
            f"invalid project name {name!r} — one identifier "
            f"(letter, then letters/digits/underscore), at most "
            f"{NAME_MAX} characters; no dots, a Project name is a "
            f"problem name's FIRST segment")
    return name


def require(conn: sqlite3.Connection, name: str) -> None:
    """KeyError when the Project is not there — the missing-resource
    signal the write endpoints turn into 404 (a ValueError from the
    mutators means 'it is there, and the write is refused')."""
    if conn.execute("SELECT 1 FROM projects WHERE name = ?",
                    (name,)).fetchone() is None:
        raise KeyError(name)


def list_projects(conn: sqlite3.Connection) -> "list[dict]":
    """Every Project with its problem count, name order. An empty
    Project is legal (§3.1) and appears here with a count of 0."""
    return [{"name": str(r["name"]),
             "description": str(r["description"] or ""),
             "problems": int(r["problems"])}
            for r in conn.execute(
                "SELECT p.name AS name, p.description AS description,"
                "       (SELECT COUNT(*) FROM problems pr"
                "         WHERE pr.project = p.name) AS problems"
                "  FROM projects p ORDER BY p.name")]


def problems_of(conn: sqlite3.Connection, project: str) -> "set[str]":
    """The problem names on one shelf — the FK, matched exactly. Callers
    that scope a workspace-wide read to a Project (the Inbox, §1.4) ask
    HERE instead of filtering on the name's first segment, which stops
    being the Project the moment someone renames one."""
    return {str(r[0]) for r in conn.execute(
        "SELECT name FROM problems WHERE project = ?", (project,))}


def create_project(conn: sqlite3.Connection, name: str,
                   description: str = "") -> str:
    """Mint a Project. Creating over a live one is a CONFLICT, not an
    upsert: the second call would erase the first's description without
    saying so."""
    name = _validate(name)
    if conn.execute("SELECT 1 FROM projects WHERE name = ?",
                    (name,)).fetchone() is not None:
        raise ValueError(f"project {name!r} already exists")
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES (?, ?, ?)", (name, description or "", db.now()))
    conn.commit()
    return name


def rename_project(conn: sqlite3.Connection, old: str, new: str) -> str:
    """Rename in the table; the FK follows in the SAME transaction.
    Neither the problem's name nor its directory moves — that is what
    makes a rename cheap enough to be a UI affordance at all."""
    require(conn, old)
    new = _validate(new)
    if new == old:
        return new
    if conn.execute("SELECT 1 FROM projects WHERE name = ?",
                    (new,)).fetchone() is not None:
        raise ValueError(f"project {new!r} already exists")
    try:
        # FK first: `problems.project` REFERENCES projects(name), so with
        # enforcement on the parent row cannot be renamed out from under
        # the children in either order — do both, then commit once.
        conn.execute("PRAGMA defer_foreign_keys = ON")
        conn.execute("UPDATE projects SET name = ? WHERE name = ?",
                     (new, old))
        conn.execute("UPDATE problems SET project = ? WHERE project = ?",
                     (new, old))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return new


def delete_project(conn: sqlite3.Connection, name: str) -> None:
    """Delete an EMPTY Project. A populated one is refused: deleting it
    would either strand its problems or silently take them with it, and
    neither is a thing a click should be able to do."""
    require(conn, name)
    n = conn.execute("SELECT COUNT(*) FROM problems WHERE project = ?",
                     (name,)).fetchone()[0]
    if n:
        raise ValueError(
            f"project {name!r} still holds {n} problem(s) — move or "
            f"delete them first (an empty Project is legal)")
    conn.execute("DELETE FROM projects WHERE name = ?", (name,))
    conn.commit()


def set_description(conn: sqlite3.Connection, name: str, text: str) -> None:
    require(conn, name)
    conn.execute("UPDATE projects SET description = ? WHERE name = ?",
                 (text or "", name))
    conn.commit()


def project_of(conn: sqlite3.Connection, problem: str) -> "str | None":
    row = conn.execute("SELECT project FROM problems WHERE name = ?",
                       (problem,)).fetchone()
    return None if row is None or row[0] is None else str(row[0])


def ensure_for_problem(conn: sqlite3.Connection, problem: str) -> str:
    """Registration's half of §3.1: file `problem` under the Project its
    name defaults to (first dotted segment, else the whole name),
    minting the Project row when the prefix names none yet. Idempotent,
    and it never overwrites a problem already filed — a re-init must not
    undo a rename."""
    existing = project_of(conn, problem)
    if existing:
        return existing
    name = problem.split(".", 1)[0] if "." in problem else problem
    if conn.execute("SELECT 1 FROM projects WHERE name = ?",
                    (name,)).fetchone() is None:
        conn.execute("INSERT INTO projects (name, description, created_at)"
                     " VALUES (?, '', ?)", (name, db.now()))
    conn.execute("UPDATE problems SET project = ? WHERE name = ?",
                 (name, problem))
    return name
