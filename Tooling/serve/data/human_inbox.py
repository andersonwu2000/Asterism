"""The human-decision inbox — `/api/inbox` and its badge (HID §1.4).

Everything a person still owes the engine an answer on: unresolved
`RequestUserAmend` rows and paused ingest sign-offs. Split out of
`timeline.py` 2026-09-02 (move-only) when the Project filter arrived:
the pair sat in that file only because the B3 line-range split left
them there, they share no helper with the event log, and the module was
at its size watermark.

Named `human_inbox` rather than `inbox` on purpose — a submodule named
for the function it exports shadows that function on the package (the
`data.library` collision the facade still has to undo by hand).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ...state import db


def inbox(conn: sqlite3.Connection, workspace: Path,
          project: "str | None" = None) -> dict:
    """Everything awaiting a human decision: unresolved amends (with the
    current on-disk file for the side-by-side diff) + paused ingest
    sign-offs (with snapshot summary). `project` narrows both halves to
    one shelf (§1.4) — the Inbox is a Project-level menu; absent, the
    read stays workspace-wide."""
    from ...state import amend as _amend
    from ...state import projects as _projects
    shelf = None if project is None else _projects.problems_of(conn, project)
    amends = []
    for a in _amend.pending_amends(conn):
        if shelf is not None and a["problem"] not in shelf:
            continue
        current = ""
        if a["file"] == "charter":
            # v40: the charter is DB-resident — reading a disk path here
            # showed the operator an EMPTY current goal beside the
            # proposal (the knows-but-flattens family).
            try:
                from ...state import intent as _intent
                pi = _intent.read(conn, a["problem"])
                current = pi.charter if pi is not None else ""
            except Exception:  # noqa: BLE001 — display only
                pass
        else:
            fpath = db.problem_dir(workspace, a["problem"]) / a["file"]
            try:
                current = fpath.read_text(encoding="utf-8")
            except OSError:
                pass
        amends.append({**a, "current_body": current})

    signoffs = []
    for r in conn.execute(
            "SELECT name, ingested_at FROM problems"
            " WHERE ingest_signoff_pending = 1 ORDER BY name"):
        problem = str(r["name"])
        if shelf is not None and problem not in shelf:
            continue
        snap = None
        loaded = None
        try:
            from ...quality import review as _review
            loaded = _review.load_review_snapshot(conn, problem)
        except Exception:  # noqa: BLE001 — snapshot is best-effort
            loaded = None
        if loaded is not None:
            data, stored_at = loaded
            delivs = data.get("deliverables", [])
            snap = {
                "stored_at": stored_at,
                "deliverable_count": len(delivs),
                "ok_count": sum(1 for d in delivs if d.get("ok")),
            }
        signoffs.append({
            "problem": problem,
            "ingested_at": r["ingested_at"],
            "snapshot": snap,
        })
    return {"amends": amends, "signoffs": signoffs}


def inbox_count(conn: sqlite3.Connection,
                project: "str | None" = None) -> int:
    """The Inbox badge — `inbox()`'s two halves counted. `project` scopes
    it to one shelf by the FK, so the badge and the list it opens can
    never disagree."""
    args: tuple = () if project is None else (project,)
    on_shelf = "" if project is None else (
        " AND problem IN (SELECT name FROM problems WHERE project = ?)")
    n = conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions"
        " WHERE decision_kind = 'RequestUserAmend'"
        "   AND outcome = 'awaiting_human'" + on_shelf, args).fetchone()[0]
    m = conn.execute(
        "SELECT COUNT(*) FROM problems"
        " WHERE ingest_signoff_pending = 1"
        + ("" if project is None else " AND project = ?"), args).fetchone()[0]
    return int(n) + int(m)
