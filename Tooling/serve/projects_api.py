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
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        finally:
            conn.close()

    @app.get("/api/projects")
    def projects_list() -> dict:
        """A fresh workspace has none, and an empty Project is legal —
        the count is what a card shows, not a filter."""
        if not (workspace / "asterism.db").exists():
            return {"projects": []}
        with ro(workspace) as conn:
            return {"projects": _projects.list_projects(conn)}

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
