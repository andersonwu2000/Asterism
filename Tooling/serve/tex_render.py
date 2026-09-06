"""A `.tex` document, compiled — `/api/projects/{p}/tex`
(human_interface_design.md §1.2-2: "tex 比照 Overleaf：伺服器端 TeX 引擎
編譯成 PDF 預覽，無引擎時面板明說").

Its own module on the `docs_api.py` precedent: `app.py` is at its size
watermark, and a surface that shells out to a toolchain has a lifecycle
of its own — discovery, a build directory, a log tail — that belongs
nowhere near the read endpoints.

THE ENGINE IS DISCOVERED AT CALL TIME, never at import. This
installation runs on machines that have TeX (a Windows box with
TinyTeX) and on machines that do not (SP7), and the same process may
gain one while it is up. `shutil.which` on each request is cheap and it
is the only answer that is true when it is given; an absent engine is
not an error but a FACT the panel states — `{"status": "no_engine"}`,
so the reader is told plainly rather than shown a failed build.

TWO DOORS, because a browser cannot POST into an `<iframe>`: the POST
compiles and answers with the render's address, and a GET serves the
bytes at that address. The address is the content's sha1, which makes
the cache and the URL the same fact — ask twice for the same document
and the second ask is a directory listing, not a build.

Nothing here writes into the Project. The build runs in
`.asterism/tmp/tex/<project>/<sha1>/`, and `state/project_docs` owns
every path that names a document, so a `.tex` outside the docs root
cannot be compiled any more than it could be read.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core import tex_engine
from ..core.tex_engine import (  # re-exported: this module's own surface
    ENGINES, JOBNAME, NO_ENGINE_DETAIL, TIMEOUT_SEC, find_engine)
from ..state import project_docs as _docs
from ..state import projects as _projects

__all__ = ["ENGINES", "JOBNAME", "NO_ENGINE_DETAIL", "TIMEOUT_SEC",
           "find_engine", "register"]


class TexBody(BaseModel):
    """`path` names the document (fenced by `state/project_docs`);
    `content` renders what is in the editor rather than what is on
    disk, which is what makes the panel follow the writing. `force`
    rebuilds a render the cache already holds — the reader's own
    Render press, for the case where an `\\input`ed sibling changed and
    this document's bytes did not."""
    path: str = ""
    content: "str | None" = None
    force: bool = False


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount the two endpoints. `ro` is app.py's `_ro` contextmanager —
    borrowed so the Project check inherits the same 404/503 semantics."""

    def _require_project(project: str) -> None:
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

    def _cache_dir(project: str, sha1: str) -> Path:
        return (workspace / ".asterism" / "tmp" / "tex" / project / sha1)

    @app.post("/api/projects/{project}/tex")
    def tex_render(project: str, body: TexBody) -> dict:
        """Compile one `.tex` document and answer with its render.

        Three honest answers and no exceptions between them: there is no
        engine, the engine failed (with the tail of its log), or here is
        the pdf."""
        _require_project(project)
        try:
            # the fence FIRST, and for both branches: a request that
            # carries its own text still names a place, and joining that
            # string ourselves is how `../../escape.tex` gets compiled
            doc_dir = _docs.locate(workspace, project, body.path).parent
            source = (body.content if body.content is not None
                      else _docs.read(workspace, project, body.path
                                      ).decode("utf-8", errors="replace"))
        except KeyError as e:
            raise HTTPException(
                status_code=404,
                detail=f"no document {e.args[0]!r}") from e
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        name, exe = find_engine()
        if name is None or exe is None:
            return {"status": "no_engine", "engine": None,
                    "detail": NO_ENGINE_DETAIL}

        # The key is the content AND where it is read from — an
        # `\input` resolves against the document's folder, so two files
        # with identical bytes in different folders are two renders.
        h = hashlib.sha1()
        h.update(str(doc_dir).encode("utf-8", "replace"))
        h.update(b"\0")
        h.update(source.encode("utf-8", "replace"))
        sha1 = h.hexdigest()
        build = _cache_dir(project, sha1)
        pdf = build / f"{JOBNAME}.pdf"
        url = f"/api/projects/{project}/tex/{sha1}.pdf"
        if pdf.is_file() and not body.force:
            return {"status": "ok", "engine": name, "sha1": sha1,
                    "pdf": url, "log_tail": ""}

        res = tex_engine.compile_into(build, source, doc_dir, name, exe)
        tail = "\n".join(
            res.log.splitlines()[-tex_engine.LOG_TAIL_LINES:]
        )[-tex_engine.LOG_TAIL_CHARS:]
        if res.status != "ok":
            return {"status": "failed", "engine": name, "sha1": sha1,
                    "detail": res.detail, "log_tail": tail}
        return {"status": "ok", "engine": name, "sha1": sha1, "pdf": url,
                "log_tail": tail}

    @app.get("/api/projects/{project}/tex/{name}")
    def tex_pdf(project: str, name: str) -> FileResponse:
        """The bytes at the address the POST handed back. A sha1 with no
        render behind it is a 404 — an empty 200 would leave the panel
        showing a blank page and calling it a document."""
        _require_project(project)
        stem = name[:-4] if name.endswith(".pdf") else name
        if not stem or any(ch not in "0123456789abcdef" for ch in stem):
            raise HTTPException(status_code=404, detail="no such render")
        pdf = _cache_dir(project, stem) / f"{JOBNAME}.pdf"
        if not pdf.is_file():
            raise HTTPException(status_code=404, detail="no such render")
        return FileResponse(pdf, media_type="application/pdf",
                            headers={"Cache-Control": "no-cache"})
