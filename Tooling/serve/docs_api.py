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
import hashlib
import json
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..state import project_docs as _docs
from ..state import projects as _projects

#: The addresses that mean "the person at this keyboard". `serve --host`
#: invites a tailnet bind, so this endpoint cannot assume the caller is
#: sitting at the machine it would open a window on.
LOOPBACK = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"})

REMOTE_DETAIL = (
    "a file-manager window opens on the machine running the engine, so "
    "it is offered only to a browser on this machine — here is the path "
    "instead")


def show_in_file_manager(path: Path) -> None:
    """Open the platform's file manager with `path` selected.

    A module-level seam, and the name is the point: a test replaces the
    WHOLE handoff rather than a subprocess call (the `spawn_cli_login`
    precedent). Raises OSError where the platform has no such thing.

    `explorer.exe` exits non-zero on success, routinely — its return
    code says nothing about whether the window opened, so it is not
    read. Nothing here waits on the child either: the caller is an HTTP
    request and a file manager outlives it.
    """
    import subprocess
    import sys
    if sys.platform == "win32":
        # /select, takes the path glued to it, no space — a space makes
        # explorer open the user's Documents folder instead
        subprocess.Popen(["explorer.exe", f"/select,{path}"])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        # no portable "select this file"; the folder is the honest best
        subprocess.Popen(["xdg-open", str(path.parent)])


class RevealBody(BaseModel):
    """Which document to show. The path travels in the BODY for the
    same reason `DocMove`'s does: a URL parser collapses `user/../x`
    before the request is sent, and a path the fence never sees is a
    path the fence never judged."""
    project: str = ""
    path: str = ""


def _etag(data: bytes) -> str:
    """A document's version, as the sha1 of its bytes.

    The bytes rather than the mtime: while a person types, two saves
    inside one filesystem tick are ordinary, and a timestamp cannot tell
    "somebody changed it" from "written again with the same text" — the
    second is not a conflict and must not be reported as one. No
    security claim is being made here; what this guards against is a
    stale tab, not an adversary.
    """
    return hashlib.sha1(data).hexdigest()


class DocBody(BaseModel):
    """A write. `content` is text; `content_base64` carries an image or
    a pdf; `kind: "dir"` makes a folder instead of a file (§3.6: folder
    creation and deletion share the path).

    `base_etag` and `create` are PRECONDITIONS, not content: they say
    what the caller believed about the disk, so a write made on a stale
    belief can be refused instead of silently winning. Omitted, the
    write is the unconditional one this door has always done — the
    editor opts in.
    """
    content: "str | None" = None
    content_base64: "str | None" = None
    kind: str = "file"
    base_etag: "str | None" = None
    create: bool = False


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
        (a wake that died before any ruling, or a refusal filed before
        the 2026-09-06 landing rule) never matches, which is the right
        answer for a listing of files.

        A REFUSED document is on the shelf like any other and carries
        its record the same way; `status` is what tells the two apart,
        and the reviewer's own lines under it are the fired ones.
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
        from ..pipeline.theorist.verdict import verdict_lines
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
                "verdict": (verdict_lines(ruling)
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
            # `etag` on both shapes: it is the version the caller is now
            # holding, and a save that names it can be refused when the
            # disk has moved on. Off the BYTES, so it survives the
            # decode above — a file with a bad byte in it still has one
            # honest version, and `errors="replace"` would hash a
            # different document than the one on disk.
            tag = _etag(raw_bytes)
            if _docs.is_binary(path):
                return {"path": path, "encoding": "base64", "etag": tag,
                        "content_base64":
                            base64.b64encode(raw_bytes).decode()}
            return {"path": path, "encoding": "utf-8", "etag": tag,
                    "content": raw_bytes.decode("utf-8", errors="replace")}

    def _check_preconditions(project: str, path: str,
                             body: DocBody) -> None:
        """Refuse a write whose belief about the disk is out of date.

        409 rather than 422: nothing about the request is malformed —
        the world moved between the read and the save, which is the one
        answer a person can act on, so each refusal names the act. A
        gate that only says no gets an invented way past it (memory:
        `gate_must_name_a_reachable_action`).

        Check-then-write is NOT atomic here. This is a localhost surface
        with one person on it, so the window is the microseconds between
        two lines and the only writer that could enter it is another tab
        of the same browser — a lock file would buy nothing but a new
        way to be stuck. Said out loud rather than left to be discovered.
        """
        if not body.create and body.base_etag is None:
            return  # the unconditional write — no belief to check
        base = _docs.root(workspace, project)
        # the same three fences the write itself goes through: a caller
        # that stats a path the fence has not judged is a caller that
        # answers questions about `../../`
        target = _docs.locate(workspace, project, path,
                              area=_docs.AREA_USER)
        rel = target.relative_to(base).as_posix()
        if body.create and target.exists():
            raise HTTPException(
                status_code=409,
                detail=f"{rel!r} already exists — open it, or pick "
                       f"another name")
        if body.base_etag is not None:
            if not target.exists():
                raise HTTPException(
                    status_code=409,
                    detail=f"{rel!r} was removed since you opened it — "
                           f"save without a base to recreate it")
            # a folder under that name is the WRITE's refusal to make
            # ("name a file inside it instead"), not a version conflict
            if (target.is_file()
                    and _etag(target.read_bytes()) != body.base_etag):
                raise HTTPException(
                    status_code=409,
                    detail=f"{rel!r} changed on disk since you opened "
                           f"it — reload to take the disk's version, or "
                           f"save again without a base to overwrite")

    @app.put("/api/projects/{project}/docs/{path:path}")
    def docs_write(project: str, path: str, body: DocBody) -> dict:
        """Write a document or make a folder — under `user/` only."""
        with _answers(project):
            if (body.kind or "file").strip() == "dir":
                # a folder carries no bytes, so it has no version and
                # `base_etag` / `create` say nothing about it — mkdir
                # stays the idempotent call §3.6 made it
                rel = _docs.mkdir(workspace, project, path,
                                  area=_docs.AREA_USER)
                return {"path": rel, "kind": "dir"}
            _check_preconditions(project, path, body)
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
            # the version the editor now holds, so its next save can name
            # a base without a second read. Hashed from what was HANDED
            # OVER, which is what landed: `project_docs.write` opens with
            # `newline=""` precisely so no `\n` becomes `\r\n` on the way
            # to disk.
            return {"path": rel, "kind": "file",
                    "etag": _etag(content.encode("utf-8")
                                  if isinstance(content, str) else content)}

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

    @app.post("/api/docs/reveal")
    def docs_reveal(body: RevealBody, request: Request) -> dict:
        """Show one document in the machine's own file manager.

        The only endpoint here that acts on the SERVER's desktop rather
        than on its files, so it asks two questions no other one has to.

        Is the caller at this keyboard? A window opens where the engine
        runs, and `serve --host` exists precisely so a remote node's
        cockpit can be read over a tailnet — a tab there must not be
        able to pop a window on the operator's screen. A caller that is
        not loopback gets the path and no window; the console offers it
        to copy, which is the same answer for a platform with no file
        manager.

        Is the path a document? It goes through `project_docs`, the same
        fence every other path in this module goes through, and it must
        EXIST — a window onto a folder that does not hold the file would
        be a worse answer than the refusal.
        """
        with _answers(body.project):
            target = _docs.locate(workspace, body.project, body.path)
            if not target.exists():
                raise KeyError(body.path)
        host = (request.client.host if request.client else "") or ""
        if host not in LOOPBACK:
            return {"path": str(target), "revealed": False,
                    "detail": REMOTE_DETAIL}
        try:
            show_in_file_manager(target)
        except OSError as e:
            return {"path": str(target), "revealed": False,
                    "detail": f"no file manager to open here ({e}) — "
                              f"here is the path instead"}
        return {"path": str(target), "revealed": True}
