"""A Project's papers over HTTP — `/api/projects/{p}/papers`
(human_interface_design.md §3.9).

The workspace-global shelf, and the `#/papers` page that stood on it,
retired 2026-09-03: a paper is a document OF a Project, it lives under
that Project's `_docs/<area>/papers/<id>/`, and the console reads it in
the Documents tab beside everything else the Project holds. What is left
that Documents cannot do on its own is exactly three things, and they
are this module:

  LIST     the shelf as a shelf — meta, bindings, map staleness — so the
           Intent editor and the New form can offer papers by NAME
           instead of by twelve hex characters.
  UPLOAD   a dropped pdf is not a file copy: it is extracted, hashed
           into its content id, and given a `meta.json`. That is
           `shelf.add_paper`, and a plain document PUT would skip it.
  SECTION  one page-anchored slice, for the sign-off pane that shows the
           claim beside the paper text it came from.

Everything else a person does to a paper — read it, delete it, move it —
is a document act, and Documents already does those.

Reads take a Project because a shelf belongs to one (§3.9): the id space
is global, the shelves are not, and two Projects citing one paper hold
two copies. The bind/unbind pair stays where it was, on
`/api/problems/{p}/papers`: a binding is a PROBLEM's citation, not a
Project's.
"""
from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

from fastapi import HTTPException, Request

from ..papers import shelf as _shelf
from ..state import project_docs as _docs
from ..state import projects as _projects

#: Bodies are read whole into memory (papers are tens of MB at most; the
#: fetch cap is 50MB) — an accidental drop of something huge should
#: bounce, not balloon the serve process.
MAX_UPLOAD_BYTES = 100 * 2**20


def project_papers(conn: "sqlite3.Connection | None", workspace: Path,
                   project: str) -> dict:
    """One Project's shelf: every slot's meta, which problems cite it,
    and whether its map is stale. The filesystem is the shelf's SoT; the
    DB only contributes bindings (conn optional so a fresh workspace
    still lists what it holds)."""
    bound: "dict[str, list[dict]]" = {}
    if conn is not None:
        try:
            for r in conn.execute(
                    "SELECT problem, paper_id, origin FROM problem_papers"
                    " ORDER BY problem"):
                bound.setdefault(str(r["paper_id"]), []).append(
                    {"problem": str(r["problem"]),
                     "origin": str(r["origin"])})
        except sqlite3.OperationalError:
            pass
    papers = []
    for entry in _shelf.list_papers(workspace, project=project):
        meta = _shelf.load_meta(workspace, entry.pid, project=project)
        if meta is None:
            continue
        original = next(
            (f.name for f in entry.path.glob("paper.*") if f.is_file()), None)
        papers.append({
            "id": meta.id,
            "source_name": meta.source_name,
            # owner-editable display title; null = filename stands in
            "title": meta.title,
            # provenance: 'user' | 'fetched' | null (pre-provenance)
            "added_by": meta.added_by,
            # which sub-root it is in — the person's or the engine's
            "area": entry.area,
            # the document address, so a row can open in Documents
            "path": entry.path.relative_to(
                _docs.root(workspace, project)).as_posix(),
            "pages": meta.pages,
            "chars": meta.chars,
            "original": original,
            "has_map": (entry.path / "map.md").exists(),
            "map_stale": _shelf.map_is_stale(workspace, meta.id,
                                             project=project),
            "bound": bound.get(meta.id, []),
        })
    papers.sort(key=lambda p: (p["title"] or p["source_name"]).lower())
    return {"project": project, "papers": papers}


def paper_section(workspace: Path, project: str, pid: str,
                  anchor: "str | None") -> "dict | None":
    """One page-anchored section of a shelved paper's extracted text
    (charter §3.2 side-by-side). Page anchors are `## p.N` lines. When
    `anchor` is a page anchor, returns that page's block; otherwise the
    whole text is scanned for the first literal occurrence and the
    surrounding page is returned. None if the paper isn't on this
    Project's shelf."""
    path = _shelf.text_path(workspace, pid, project=project)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    a = (anchor or "").strip()
    # Non-page anchor (free-text ref): locate it, then serve its page.
    if a and not a.startswith("## p.") and a in text:
        page_start = text.rfind("\n## p.", 0, text.index(a))
        if page_start >= 0:
            a = text[page_start + 1:text.index("\n", page_start + 1)]
        else:
            a = ""
    if a.startswith("## p."):
        idx = text.find(a + "\n")
        if idx < 0:
            idx = text.find(a)
        if idx >= 0:
            nxt = text.find("\n## p.", idx + 1)
            content = text[idx:nxt] if nxt > 0 else text[idx:]
            return {"pid": pid, "anchor": a, "found": True,
                    "content": content.strip()}
    # Fallback: unpaged source or unknown anchor — first 4KB as context.
    return {"pid": pid, "anchor": a or None, "found": False,
            "content": text[:4096]}


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount the three endpoints. `ro` is app.py's read-only
    contextmanager, borrowed so the Project check inherits the same
    404/503 semantics every other read has."""

    def _require_project(project: str) -> None:
        try:
            _docs.root(workspace, project)  # validates the NAME only
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        if not (workspace / "asterism.db").exists():
            return
        with ro(workspace) as conn:
            try:
                _projects.require(conn, project)
            except KeyError as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"no project {e.args[0]!r}") from e

    @app.get("/api/projects/{project}/papers")
    def project_papers_ep(project: str) -> dict:
        """This Project's shelf — what the paper pickers offer."""
        _require_project(project)
        if not (workspace / "asterism.db").exists():
            return project_papers(None, workspace, project)
        with ro(workspace) as conn:
            return project_papers(conn, workspace, project)

    @app.get("/api/projects/{project}/papers/{pid}/section")
    def project_paper_section_ep(project: str, pid: str,
                                 anchor: "str | None" = None) -> dict:
        """One page of a paper, for the sign-off pane."""
        _require_project(project)
        d = paper_section(workspace, project, pid, anchor)
        if d is None:
            raise HTTPException(
                status_code=404,
                detail=f"paper {pid!r} is not on {project}'s shelf")
        return d

    @app.post("/api/projects/{project}/papers")
    async def project_paper_upload_ep(project: str, request: Request,
                                      filename: str) -> dict:
        """Shelve a document dropped or picked in the browser, into this
        Project's `user/papers/`. The body is the RAW file bytes (no
        multipart — keeps the install free of a parser dependency); the
        source filename rides the query string.

        Not a document PUT: a paper is extracted, hashed into its
        content id and given a `meta.json`, and `shelf.add_paper` is the
        one place that happens. Re-dropping the same document is a no-op
        returning the existing slot, and `already_shelved` tells the UI
        which happened."""
        _require_project(project)
        # The wire filename is client data: strip path components and
        # the characters Windows refuses so the temp write can't fail
        # or escape (identity never depends on the name anyway).
        name = re.sub(r'[<>:"|?*\x00-\x1f]', "_",
                      Path(filename.replace("\\", "/")).name).strip()
        if name.strip(". ") == "":
            raise HTTPException(status_code=422,
                                detail=f"unusable filename {filename!r}")
        data = await request.body()
        if not data:
            raise HTTPException(status_code=422,
                                detail=f"{name}: empty file")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{name}: {len(data) // 2**20}MB exceeds the "
                       f"{MAX_UPLOAD_BYTES // 2**20}MB upload cap")
        already = _shelf.load_meta(workspace, _shelf.content_id(data),
                                   project=project) is not None
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / name
            tmp.write_bytes(data)
            try:
                meta = _shelf.add_paper(workspace, tmp, project=project,
                                        added_by="user")
            except (_shelf.ScannedPdfError, ValueError) as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
        return {"id": meta.id, "source_name": meta.source_name,
                "pages": meta.pages, "chars": meta.chars,
                "already_shelved": already}
