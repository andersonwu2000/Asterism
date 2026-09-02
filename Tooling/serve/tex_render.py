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
import os
import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..state import project_docs as _docs
from ..state import projects as _projects

#: What every build is called inside its own directory. One name, so
#: the log, the pdf and the source are found without parsing anything.
JOBNAME = "main"

#: The engines this module knows, in preference order. `latexmk` runs
#: the document to a fixed point itself (references, toc); bare
#: `pdflatex` does not, so it is run TWICE.
ENGINES = ("latexmk", "pdflatex")

#: Said once, here, so the endpoint and its test cannot drift on it.
NO_ENGINE_DETAIL = (
    "no LaTeX engine on this machine — install TeX Live, MiKTeX or "
    "TinyTeX (the console looks for latexmk, then pdflatex, on PATH "
    "each time you press Render)")

#: A document that has not finished in this long is not going to. TeX
#: waits for input forever on some errors even under `nonstopmode`.
TIMEOUT_SEC = 120

#: How much of the log the panel is handed. The interesting line is at
#: the END of a TeX log, always.
LOG_TAIL_LINES = 60
LOG_TAIL_CHARS = 6000


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


def find_engine() -> "tuple[str, str] | tuple[None, None]":
    """(name, absolute path) of the first engine on PATH, or (None,
    None). Looked up on every call — see the module header."""
    for name in ENGINES:
        exe = shutil.which(name)
        if exe:
            return name, exe
    return None, None


def _log_tail(build: Path, stdout: str) -> str:
    """The end of the engine's own log, or of what it printed when it
    wrote none (a toolchain that died before opening the file)."""
    text = ""
    log = build / f"{JOBNAME}.log"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not text.strip():
        text = stdout or ""
    lines = text.splitlines()[-LOG_TAIL_LINES:]
    return "\n".join(lines)[-LOG_TAIL_CHARS:]


def _command(name: str, exe: str) -> "list[list[str]]":
    """The runs one compile takes. The flags are the owner's: never
    stop for input, and stop at the first real error rather than
    limping to a pdf nobody should trust."""
    common = ["-interaction=nonstopmode", "-halt-on-error"]
    if name == "latexmk":
        return [[exe, "-pdf", *common, f"{JOBNAME}.tex"]]
    # pdflatex resolves references on the SECOND pass; one run leaves
    # every \ref reading "??"
    return [[exe, *common, f"{JOBNAME}.tex"]] * 2


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

        build.mkdir(parents=True, exist_ok=True)
        try:
            pdf.unlink()
        except OSError:
            pass
        (build / f"{JOBNAME}.tex").write_text(source, encoding="utf-8",
                                              newline="")
        env = {**os.environ}
        # a trailing separator means "and then the usual places" — drop
        # it and TeX stops finding its own class files
        env["TEXINPUTS"] = (f"{doc_dir}{os.pathsep}"
                            + (os.environ.get("TEXINPUTS") or ""))
        out = ""
        rc = 0
        for cmd in _command(name, exe):
            try:
                r = subprocess.run(cmd, cwd=str(build), env=env,
                                   capture_output=True, text=True,
                                   timeout=TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                return {"status": "failed", "engine": name, "sha1": sha1,
                        "detail": f"{name} did not finish in "
                                  f"{TIMEOUT_SEC}s",
                        "log_tail": _log_tail(build, out)}
            except OSError as e:  # the engine vanished between which() and run
                return {"status": "failed", "engine": name, "sha1": sha1,
                        "detail": str(e), "log_tail": ""}
            out = (r.stdout or "") + (r.stderr or "")
            rc = r.returncode
            if rc != 0:
                break
        if rc != 0 or not pdf.is_file():
            return {"status": "failed", "engine": name, "sha1": sha1,
                    "detail": f"{name} exited {rc}" if rc else
                              f"{name} wrote no pdf",
                    "log_tail": _log_tail(build, out)}
        return {"status": "ok", "engine": name, "sha1": sha1, "pdf": url,
                "log_tail": _log_tail(build, out)}

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
