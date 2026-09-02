"""The Project shelves over HTTP — `/api/projects`
(human_interface_design.md §3.1).

Its own module for the reason `run.py` / `chat.py` are: `app.py` is at
its size watermark, and a surface with one read, three writes and a
shared refusal shape is a natural unit. Every write goes through
`state/projects`, which owns the SQL; this file only translates the two
refusal types into the two honest HTTP answers.
"""
from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

from ..state import db
from ..state import projects as _projects
from . import data as _data


class ProjectBody(BaseModel):
    """POST names the Project; PATCH sends only what changed — a `name`
    is a rename, a `description` re-blurbs, and both may travel together.
    None means "leave it", which is why description is not defaulted to
    the empty string."""
    name: str | None = None
    description: str | None = None


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount the four endpoints. `ro` is app.py's `_ro` contextmanager —
    borrowed so the read inherits the same 404/503 semantics."""

    @contextlib.contextmanager
    def _writes():
        """The `resolve_amend` write shape: a real connection through the
        state functions, whose two refusal types map to the two honest
        answers — KeyError = the Project is not there (404), ValueError =
        it is, and the write is refused (409: duplicate, still populated,
        malformed name)."""
        if not (workspace / "asterism.db").exists():
            raise HTTPException(status_code=404, detail="NO_DATABASE")
        conn = db.connect(workspace / "asterism.db")
        try:
            yield conn
        except KeyError as e:
            raise HTTPException(status_code=404,
                                detail=f"no project {e.args[0]!r}")
        except _projects.InvalidName as e:
            # The name is not a name — a malformed REQUEST, like
            # `/api/problems/create`'s 422. 409 would have told the
            # person "already exists", which is a different problem and
            # a different fix (ruling 2026-09-02, §3.2 appendix).
            raise HTTPException(status_code=422, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        finally:
            conn.close()

    @app.get("/api/projects")
    def projects_list() -> dict:
        """A fresh workspace has none, and an empty Project is legal —
        the count is what a card shows, not a filter. The card's three
        live numbers (running / attention / last_event) come from
        `data/projects.py`; `running` is an engine-liveness claim, so it
        is gated on the daemon status the board is gated on."""
        if not (workspace / "asterism.db").exists():
            return {"projects": []}
        from .daemon_cache import daemon_status
        daemon = daemon_status(workspace)
        with ro(workspace) as conn:
            return {"projects": _data.project_rows(conn, daemon=daemon)}

    @app.get("/api/projects/{name}/events")
    def project_events(name: str, limit: "int | None" = None,
                       before: "str | None" = None) -> dict:
        """The shelf's Timeline — every task's events in one stream
        (§1.4: the Timeline is a Project surface with a task list as its
        secondary menu, so it must read whole before it reads scoped).
        History, so it is its own endpoint and nobody polls it."""
        with ro(workspace) as conn:
            try:
                _projects.require(conn, name)
            except KeyError:
                raise HTTPException(status_code=404,
                                    detail=f"no project {name!r}")
            return _data.project_events(conn, name, limit=limit,
                                        before=before)

    @app.post("/api/projects")
    def create_project(body: ProjectBody) -> dict:
        with _writes() as conn:
            name = _projects.create_project(
                conn, body.name or "", description=body.description or "")
            return {"project": name, "action": "create"}

    @app.patch("/api/projects/{name}")
    def patch_project(name: str, body: ProjectBody) -> dict:
        """Rename and/or re-blurb. The rename carries `problems.project`
        with it; neither the problem names nor their directories move."""
        with _writes() as conn:
            if body.description is not None:
                _projects.set_description(conn, name, body.description)
            if body.name and body.name != name:
                name = _projects.rename_project(conn, name, body.name)
            else:
                _projects.require(conn, name)
            return {"project": name, "action": "update"}

    @app.delete("/api/projects/{name}")
    def delete_project(name: str) -> dict:
        with _writes() as conn:
            _projects.delete_project(conn, name)
            return {"project": name, "action": "delete"}
