"""The Programme's decided history over HTTP —
`/api/problems/{p}/programme/revisions` (human_interface_design.md
§1.4-2, third bullet).

Its own module on the `docs_api.py` / `commands_api.py` precedent:
`app.py` is at its size watermark, and two reads that share one
existence check are a natural unit.

ON DEMAND, never on a poll — the same rule `/programme/verdict/{rev_id}`
was given: a debate carries every round's draft, and union_closed's
chain is hundreds of revisions long. The Groups screen asks for the list
when the reader opens it, and for one revision when the reader opens
that.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from . import data as _data
from .data import revisions as _revisions


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount the two reads. `ro` is app.py's `_ro` contextmanager —
    borrowed so they inherit the same 404/503 semantics."""

    def _require_problem(conn, problem: str) -> None:  # noqa: ANN001
        if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                        (problem,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="unknown problem")

    @app.get("/api/problems/{problem}/programme/verdict/{rev_id}")
    def programme_verdict(problem: str, rev_id: int) -> dict:
        """The judge's verdict on ONE revision — criterion by criterion,
        plus which seat issued it.

        On demand, never on a poll: the Timeline row that opens this
        already names the revision, and union_closed's last 100
        revisions carry 152 KB of verdict against a 15s poll.

        Keyed by the programme_revisions row id, which the Timeline
        event carries as `rev_id`: `rev` alone names several rows (a
        rejected proposal and the revision that later takes its
        number).

        (Moved here from `app.py` with the two reads below: it is the
        same cluster, and app.py is at its size watermark.)"""
        with ro(workspace) as conn:
            v = _data.programme_verdict(conn, problem, rev_id)
        if v is None:
            raise HTTPException(status_code=404, detail="no such revision")
        return v

    @app.get("/api/problems/{problem}/programme/revisions")
    def programme_revisions(problem: str, group: "int | None" = None) -> dict:
        """One group's decided chain, newest first — no bodies.

        `group` selects a discussion group's chain (v35); omitted, the
        top group's, which is the argument the problem page is about. A
        group belonging to another problem is a 404, not somebody else's
        history."""
        with ro(workspace) as conn:
            _require_problem(conn, problem)
            if group is not None:
                card = _data.group_card(conn, group)
                if card is None or card["problem"] != problem:
                    raise HTTPException(
                        status_code=404,
                        detail=f"group {group} is not part of {problem}")
            return {"problem": problem, "group_id": group,
                    "revisions": _revisions.programme_revisions(
                        conn, problem, group)}

    @app.get("/api/problems/{problem}/programme/revisions/{rev_id}")
    def programme_revision(problem: str, rev_id: int) -> dict:
        """ONE revision: the body that was decided, the rounds that got
        there, and the verdict that closed it.

        Keyed by the row id — `rev` alone names several rows, since a
        rejected proposal and the revision that later takes its number
        share a number. A row belonging to another problem is a 404: an
        id is not a capability."""
        with ro(workspace) as conn:
            _require_problem(conn, problem)
            d = _revisions.programme_revision(conn, problem, rev_id)
        if d is None:
            raise HTTPException(status_code=404, detail="no such revision")
        return d
