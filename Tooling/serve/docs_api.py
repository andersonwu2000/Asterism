"""The Project's documents over HTTP — `/api/projects/{p}/docs`
(human_interface_design.md §3.6).

Its own module on the `projects_api.py` / `commands_api.py` precedent:
`app.py` is at its size watermark, and a surface with two reads, two
writes and one shared refusal shape is a natural unit. All path
handling lives in `state/project_docs`, which owns the fence; this file
only translates its two refusal types into the two honest HTTP answers
(KeyError = 404, ValueError = 422) and decides how bytes reach a
browser.

THIS DOOR WRITES `user/`. `_docs/agent/` is what the Assistant
produced, reached through its own tool (§3.5) — a console PUT into it
would merge two areas whose separation is the point (§1.2-1). The
refusal says so and names the path that would have worked.

The Project must EXIST: the docs root is addressed by Project name, and
a typo that silently created `Problems/Erdsо/_docs/` would be a folder
nobody can ever find again. That is the one thing this module asks the
DB, through the same read-only connection every other read uses.
"""
from __future__ import annotations

import base64
import contextlib
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

from ..state import project_docs as _docs
from ..state import projects as _projects


class DocBody(BaseModel):
    """A write. `content` is text; `content_base64` carries an image or
    a pdf; `kind: "dir"` makes a folder instead of a file (§3.6: folder
    creation and deletion share the path)."""
    content: "str | None" = None
    content_base64: "str | None" = None
    kind: str = "file"


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount the four endpoints. `ro` is app.py's `_ro` contextmanager —
    borrowed so the Project check inherits the same 404/503 semantics."""

    def _require_project(project: str) -> None:
        """The Project has to be on the shelf. A malformed NAME is 422
        (the §3.2 ruling: not-a-name and name-taken are different
        answers to different questions); an unknown one is 404."""
        try:
            _docs.root(workspace, project)  # validates the name only
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        with ro(workspace) as conn:
            try:
                _projects.require(conn, project)
            except KeyError as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"no project {e.args[0]!r}") from e

    @contextlib.contextmanager
    def _answers(project: str):
        """The state module's two refusal types, as HTTP."""
        _require_project(project)
        try:
            yield
        except KeyError as e:
            raise HTTPException(
                status_code=404,
                detail=f"no document {e.args[0]!r}") from e
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    @app.get("/api/projects/{project}/docs")
    def docs_tree(project: str) -> dict:
        """The whole tree, flat and root-relative — what the left rail
        draws. A Project that has written nothing yet has an empty one;
        the root is created by the first write, not by the Project."""
        with _answers(project):
            return {"project": project, "entries": _docs.tree(workspace,
                                                              project)}

    @app.get("/api/projects/{project}/docs/{path:path}")
    def docs_read(project: str, path: str) -> dict:
        """One document. Text comes back as `content`; an image or pdf
        as `content_base64`, so one endpoint answers for both and the
        client decides by which key is present."""
        with _answers(project):
            raw = _docs.read(workspace, project, path)
            if _docs.is_binary(path):
                return {"path": path, "encoding": "base64",
                        "content_base64": base64.b64encode(raw).decode()}
            return {"path": path, "encoding": "utf-8",
                    "content": raw.decode("utf-8", errors="replace")}

    @app.put("/api/projects/{project}/docs/{path:path}")
    def docs_write(project: str, path: str, body: DocBody) -> dict:
        """Write a document or make a folder — under `user/` only."""
        with _answers(project):
            if (body.kind or "file").strip() == "dir":
                rel = _docs.mkdir(workspace, project, path,
                                  area=_docs.AREA_USER)
                return {"path": rel, "kind": "dir"}
            if body.content_base64 is not None:
                try:
                    content: "str | bytes" = base64.b64decode(
                        body.content_base64, validate=True)
                except (ValueError, TypeError) as e:
                    raise HTTPException(
                        status_code=422,
                        detail=f"content_base64 is not base64: {e}") from e
            else:
                content = body.content or ""
            rel = _docs.write(workspace, project, path, content,
                              area=_docs.AREA_USER)
            return {"path": rel, "kind": "file"}

    @app.delete("/api/projects/{project}/docs/{path:path}")
    def docs_delete(project: str, path: str) -> dict:
        """Remove a document, or an EMPTY folder — under `user/` only."""
        with _answers(project):
            rel = _docs.delete(workspace, project, path,
                               area=_docs.AREA_USER)
            return {"path": rel, "action": "delete"}
