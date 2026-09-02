"""Problem authoring over HTTP — `POST /api/problems/create`, plus the
bench pair that takes an existing problem off the live path and back
(`POST /api/problems/{p}/bench` | `/unbench`).

Its own module for the reason `projects_api.py` / `docs_api.py` /
`run.py` are: `app.py` IS the route table and sits at its size
watermark, and one write with a body model, a rollback and two
validation gates is a natural unit. Moved out of `app.py` verbatim
(2026-09-03) when the endpoint gained its `project` field.

The write itself goes nowhere new: the seed file, then the same
`init_problem` chokepoint the CLI runs, then the state writers for the
explicit creation-time inputs. Nothing here holds SQL of its own.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

from ..state import db


class ProblemCreateBody(BaseModel):
    name: str
    # the problem's goal (required) + the user's standing directives
    # (optional) — DB-resident intent (v40, Manifest.md retired)
    charter: str | None = None
    word: str | None = None
    settings: dict | None = None
    defs: str | None = None
    root: str | None = None
    # shelf ids to cite (Papers/<id> — bound with origin='user')
    papers: list[str] | None = None
    # the Project to file it under (§3.1). Absent = the shelf the name's
    # first segment defaults to; the DIRECTORY is unaffected either way.
    project: str | None = None


def register(app, workspace: Path) -> None:  # noqa: ANN001 — FastAPI app

    @app.post("/api/problems/{problem}/bench")
    def bench_problem_ep(problem: str) -> dict:
        """Stop this task without stopping the run: the problem takes
        no further dispatch and no Strategist seat, keeping every goal,
        revision and last word (bench is not a reset)."""
        return _set_benched(workspace, problem, True)

    @app.post("/api/problems/{problem}/unbench")
    def unbench_problem_ep(problem: str) -> dict:
        """Back on the live path at the next daemon tick."""
        return _set_benched(workspace, problem, False)

    @app.post("/api/problems/create")
    def create_problem_ep(body: ProblemCreateBody) -> dict:
        """Author a new problem from the UI: write the problem.json
        seed (+ optional Defs.lean / Root.lean), then run the same init
        chokepoint the CLI uses. Pure-NL creation is instant; a
        Defs/Root submission type-checks first (lake build — minutes).
        On init failure the created directory is rolled back so the
        form can be corrected and resubmitted."""
        import json as _json
        import shutil as _shutil
        from ..core.cli import init_problem
        from ..state import intent as _intent
        # One spelling of one rule: a problem name is dot-separated
        # Project-name segments (state/projects.py, v48).
        from ..state import projects as _projects
        name = body.name.strip()
        if not _projects.PROBLEM_NAME_RE.fullmatch(name) \
                or len(name) > _projects.NAME_MAX:
            raise HTTPException(
                status_code=422,
                detail="problem name must be dot-separated identifiers, "
                       "e.g. Topology.my_theorem")
        charter = str(body.charter or "").strip()
        if not charter:
            raise HTTPException(status_code=422,
                                detail="the charter (the problem's goal) "
                                       "must not be empty")
        # An explicit shelf is checked HERE, before anything is made: a
        # 404 raised after `mkdir` would leave the half-built problem
        # behind and the author's retry would meet "already exists".
        if body.project:
            _require_project(workspace, body.project)
        pdir = db.problem_dir(workspace, name)
        if pdir.exists():
            raise HTTPException(
                status_code=409,
                detail=f"Problems/{'/'.join(name.split('.'))} already exists")
        created = False
        try:
            pdir.mkdir(parents=True)
            created = True
            seed: dict = {"problem": name, "charter": charter}
            if body.word and body.word.strip():
                seed["word"] = body.word.strip()
            (pdir / _intent.SEED_FILENAME).write_text(
                _json.dumps(seed, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n")
            if body.defs and body.defs.strip():
                (pdir / "Defs.lean").write_text(
                    body.defs, encoding="utf-8", newline="\n")
            if body.root and body.root.strip():
                (pdir / "Root.lean").write_text(
                    body.root, encoding="utf-8", newline="\n")
            rc, msg = init_problem(workspace, name)
            if rc != 0:
                _shutil.rmtree(pdir, ignore_errors=True)
                raise HTTPException(status_code=422, detail=msg)
            # Explicit creation-time inputs are authoritative in the DB
            # (init's lazy migration reads the PARSED file):
            if body.settings or body.papers or body.project:
                from ..state import settings as _settings
                conn2 = db.connect(workspace / "asterism.db")
                try:
                    for key in _settings.SETTING_KEYS:
                        if body.settings and key in body.settings:
                            try:
                                _settings.write(conn2, name, key,
                                                body.settings[key])
                            except ValueError:
                                pass  # form junk never blocks creation
                    for pid in body.papers or []:
                        db.bind_paper(conn2, problem=name, paper_id=pid,
                                      origin="user")
                    if body.project:
                        # after init: registration files it under the
                        # prefix's Project first, and the author's
                        # choice is the one that stands
                        _projects.file_under(conn2, name, body.project)
                    conn2.commit()
                finally:
                    conn2.close()
            return {"problem": name, "message": msg}
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 — surface, don't 500-blank
            if created:
                _shutil.rmtree(pdir, ignore_errors=True)
            raise HTTPException(status_code=500,
                                detail=f"create failed: {e}")


def _set_benched(workspace: Path, problem: str, benched: bool) -> dict:
    """One chokepoint with `asterism bench` (`state/db/bench.py`): the
    flag flips, the unleased queue rows are flushed, in-flight work
    finishes on its own. Idempotent, so the console's button never has
    to read the current state before it is safe to press. A workspace
    with no DB has no problem to bench — and answering 404 from the
    missing FILE keeps this write from creating one."""
    path = workspace / "asterism.db"
    detail = f"unknown problem {problem!r}"
    if not path.exists():
        raise HTTPException(status_code=404, detail=detail)
    conn = db.connect(path)
    try:
        known = db.set_benched(conn, problem, benched=benched)
    finally:
        conn.close()
    if known is None:
        raise HTTPException(status_code=404, detail=detail)
    return {"problem": problem, "benched": benched}


def _require_project(workspace: Path, name: str) -> None:
    """404 unless the named Project exists. A missing DB answers the
    same way: with no `projects` table there is no shelf to file on."""
    from ..state import projects as _projects
    path = workspace / "asterism.db"
    detail = f"no project {name!r} — create it first, or leave the " \
             f"field empty to file under the name's first segment"
    if not path.exists():
        raise HTTPException(status_code=404, detail=detail)
    conn = db.connect_readonly(path)
    try:
        _projects.require(conn, name)
    except KeyError:
        raise HTTPException(status_code=404, detail=detail)
    finally:
        conn.close()
