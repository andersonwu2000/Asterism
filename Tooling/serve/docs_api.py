"""The Project's documents over HTTP — `/api/projects/{p}/docs`
(human_interface_design.md §3.6).

Its own module on the `projects_api.py` / `commands_api.py` precedent:
`app.py` is at its size watermark, and a surface with two reads, three
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
import json
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
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


class DocMove(BaseModel):
    """A rename. The destination travels in the BODY, not the URL: a
    URL parser collapses `user/../x` before the request is sent, so a
    path in the address is a path the fence never gets to judge."""
    to: str = ""


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount the five endpoints. `ro` is app.py's `_ro` contextmanager —
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

    def _theory_records(project: str) -> "dict[str, dict]":
        """Every landed theory document's ROW, by root-relative path.

        A theory document is a row before it is a file
        (theory_wake_design.md §4): whose wall it was written for, when,
        that a reviewer passed it and what the reviewer checked are all
        absent from the prose, so the listing that draws the shelf
        carries them the way the agent roster does.

        Found by PATH. `theory_documents.path` is workspace-relative and
        this Project's agent area is exactly one prefix of it, so no
        problem→Project join is needed — and a row whose `path` is NULL
        (the refused run, which lands no file) never matches, which is
        the right answer for a listing of files.
        """
        prefix = (_docs.root(workspace, project)
                  .relative_to(workspace).as_posix() + "/")
        with ro(workspace) as conn:
            rows = conn.execute(
                "SELECT group_id, created_at, status, rounds, objective,"
                " verdict_json, path FROM theory_documents"
                " WHERE path LIKE ?", (f"{prefix}{_docs.AREA_AGENT}/%",)
            ).fetchall()
        # The rubric's own parser renders the reviewer's four lines — a
        # second reading of the verdict living here is the drift that
        # made every rebut report as `passed` for a week (44ff4321).
        # Lazily, on `data/verdict.py`'s precedent: the shape belongs to
        # the code that writes it, not to the door that serves it.
        from ..pipeline.theorist.verdict import clear_lines
        out: "dict[str, dict]" = {}
        for r in rows:
            rel = str(r["path"]).replace("\\", "/")[len(prefix):]
            try:
                ruling = json.loads(r["verdict_json"] or "")
            except ValueError:
                ruling = None
            out[rel] = {
                "group_id": (None if r["group_id"] is None
                             else int(r["group_id"])),
                "created_at": str(r["created_at"] or ""),
                "status": str(r["status"]),
                "rounds": int(r["rounds"] or 0),
                "objective": str(r["objective"] or ""),
                # a row the parser cannot read costs the four lines and
                # nothing else — the record is the point
                "verdict": (clear_lines(ruling)
                            if isinstance(ruling, dict) else []),
            }
        return out

    @app.get("/api/projects/{project}/docs")
    def docs_tree(project: str) -> dict:
        """The whole tree, flat and root-relative — what the left rail
        draws. A Project that has written nothing yet has an empty one;
        the root is created by the first write, not by the Project.

        An entry the theory layer wrote carries its `theory` record;
        every other one carries no such key, so "is this a theory
        document" stays a question about the entry rather than a name
        pattern the shelf would have to parse.
        """
        with _answers(project):
            entries = _docs.tree(workspace, project)
            theory = _theory_records(project)
            for e in entries:
                rec = theory.get(e["path"])
                if rec is not None and e["kind"] == "file":
                    e["theory"] = rec
            return {"project": project, "entries": entries}

    #: What `?raw=1` calls each kind, for the browser that will render
    #: it. Anything else is served as bytes with no claim about them.
    _MEDIA = {".pdf": "application/pdf", ".png": "image/png",
              ".jpg": "image/jpeg", ".svg": "image/svg+xml",
              ".md": "text/markdown; charset=utf-8",
              ".tex": "text/plain; charset=utf-8",
              ".txt": "text/plain; charset=utf-8",
              ".lean": "text/plain; charset=utf-8"}

    @app.get("/api/projects/{project}/docs/{path:path}")
    def docs_read(project: str, path: str, raw: int = 0):
        """One document. Text comes back as `content`; an image or pdf
        as `content_base64`, so one endpoint answers for both and the
        client decides by which key is present.

        `?raw=1` hands over the FILE instead (§3.6 allows either shape).
        A paper's pdf runs to tens of megabytes, and base64 in a JSON
        field is 4/3 of that for the browser to parse before it can show
        page one — and a blob cannot answer the range requests a pdf
        viewer makes. Same address, same fence: only the wire shape
        differs."""
        with _answers(project):
            if raw:
                target = _docs.locate(workspace, project, path)
                if not target.is_file():
                    raise KeyError(path)
                suffix = target.suffix.lower()
                return FileResponse(
                    target,
                    media_type=_MEDIA.get(suffix,
                                          "application/octet-stream"),
                    filename=target.name,
                    content_disposition_type="inline")
            raw_bytes = _docs.read(workspace, project, path)
            if _docs.is_binary(path):
                return {"path": path, "encoding": "base64",
                        "content_base64":
                            base64.b64encode(raw_bytes).decode()}
            return {"path": path, "encoding": "utf-8",
                    "content": raw_bytes.decode("utf-8", errors="replace")}

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

    @app.post("/api/projects/{project}/docs/{path:path}")
    def docs_move(project: str, path: str, body: DocMove) -> dict:
        """Rename or move a document or a folder — under `user/` only.

        POST rather than a second PUT shape: the addressed thing already
        exists and the request names where it goes, which is an action
        on it rather than a body for it."""
        with _answers(project):
            rel = _docs.move(workspace, project, path, body.to or "",
                             area=_docs.AREA_USER)
            return {"path": rel, "from": path, "action": "move"}

    @app.delete("/api/projects/{project}/docs/{path:path}")
    def docs_delete(project: str, path: str) -> dict:
        """Remove a document, or an EMPTY folder — under `user/` only."""
        with _answers(project):
            rel = _docs.delete(workspace, project, path,
                               area=_docs.AREA_USER)
            return {"path": rel, "action": "delete"}
