"""FastAPI app factory for `asterism serve`.

One serve process = one workspace (fixed at create_app time). Reads
open a fresh `db.connect_readonly` per request; writes call the same
CLI/state chokepoints the terminal uses. Binds 127.0.0.1, no auth
(charter §1-4 — hosted form adds it later, not pre-built).

Empty states are first-class: a workspace whose DB doesn't exist yet
serves an empty board (fresh install), while a schema-behind DB serves
503 UPGRADE_REQUIRED (running `asterism run` migrates it) — the UI
renders both with explicit copy instead of a white screen.
"""
from __future__ import annotations

import asyncio
import contextlib
import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..state import db
from . import data as _data

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIST = REPO_ROOT / "web" / "dist"


@contextlib.contextmanager
def _ro(workspace: Path):
    """Read-only connection or a structured HTTP error.

    Missing DB file → 404 NO_DATABASE (fresh workspace, UI shows the
    getting-started empty state). Schema behind → 503 UPGRADE_REQUIRED.
    """
    path = workspace / "asterism.db"
    if not path.exists():
        raise HTTPException(status_code=404, detail="NO_DATABASE")
    try:
        try:
            conn = db.connect_readonly(path)
        except sqlite3.OperationalError:
            # WAL + mode=ro can transiently refuse while a writer holds
            # the recovery lock; one short retry absorbs it.
            time.sleep(0.15)
            conn = db.connect_readonly(path)
    except db.SchemaBehind as e:
        raise HTTPException(
            status_code=503,
            detail=f"UPGRADE_REQUIRED: database schema v{e.found} < "
                   f"expected v{e.expected}; run the engine once to migrate")
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"DB_UNAVAILABLE: {e}")
    try:
        yield conn
    finally:
        conn.close()


class AmendResolveBody(BaseModel):
    action: str  # accept | reject
    body: str | None = None
    reason: str | None = None


class RejectIngestBody(BaseModel):
    reason: str | None = None


class DaemonStartBody(BaseModel):
    scope: str | None = None
    once: bool = False


class DaemonStopBody(BaseModel):
    force: bool = False


def create_app(workspace: Path) -> FastAPI:
    workspace = workspace.resolve()
    app = FastAPI(title="Asterism", docs_url=None, redoc_url=None)

    # -- meta ---------------------------------------------------------

    @app.get("/api/meta")
    def meta() -> dict:
        from ..core.cli import daemon_status
        db_state = "ok"
        inbox_n = 0
        if not (workspace / "asterism.db").exists():
            db_state = "missing"
        else:
            try:
                with _ro(workspace) as conn:
                    inbox_n = _data.inbox_count(conn)
            except HTTPException as e:
                detail = str(e.detail)
                if detail.startswith("UPGRADE_REQUIRED"):
                    db_state = "behind"
                elif detail == "NO_DATABASE":
                    db_state = "missing"
                else:
                    db_state = "unavailable"
        return {
            "workspace": str(workspace),
            "db": db_state,
            "daemon": daemon_status(workspace),
            "inbox_count": inbox_n,
        }

    # -- reads ----------------------------------------------------------

    @app.get("/api/problems")
    def problems() -> dict:
        if not (workspace / "asterism.db").exists():
            return {"problems": []}  # fresh workspace — empty board
        with _ro(workspace) as conn:
            return _data.board(conn)

    @app.get("/api/problems/{problem}")
    def problem(problem: str) -> dict:
        with _ro(workspace) as conn:
            d = _data.problem_detail(conn, workspace, problem)
        if d is None:
            raise HTTPException(status_code=404,
                                detail=f"unknown problem {problem!r}")
        return d

    @app.get("/api/problems/{problem}/goals/{goal_id}")
    def goal(problem: str, goal_id: int) -> dict:
        with _ro(workspace) as conn:
            d = _data.goal_detail(conn, problem, goal_id)
        if d is None:
            raise HTTPException(status_code=404,
                                detail=f"no goal {goal_id} in {problem!r}")
        return d

    @app.get("/api/problems/{problem}/file")
    def problem_file(problem: str, path: str) -> dict:
        text = _data.read_problem_file(workspace, problem, path)
        if text is None:
            raise HTTPException(status_code=404, detail="no such file")
        return {"path": path, "content": text}

    @app.get("/api/problems/{problem}/review")
    def review(problem: str) -> dict:
        with _ro(workspace) as conn:
            d = _data.review(conn, problem)
        if d is None:
            raise HTTPException(
                status_code=404,
                detail="no review snapshot stored (problem not yet at "
                       "Ingest, or pre-v22 data); use refresh to compute")
        return d

    @app.get("/api/inbox")
    def inbox() -> dict:
        if not (workspace / "asterism.db").exists():
            return {"amends": [], "signoffs": []}
        with _ro(workspace) as conn:
            return _data.inbox(conn, workspace)

    @app.get("/api/library")
    def library() -> dict:
        if not (workspace / "asterism.db").exists():
            return {"problems": []}
        with _ro(workspace) as conn:
            return _data.library(conn)

    @app.get("/api/telemetry/usage")
    def usage() -> dict:
        if not (workspace / "asterism.db").exists():
            return {"problems": []}
        with _ro(workspace) as conn:
            return _data.telemetry_usage(conn)

    # -- writes (CLI/state chokepoints only) ----------------------------

    @app.post("/api/inbox/amend/{decision_id}/resolve")
    def resolve_amend(decision_id: int, body: AmendResolveBody) -> dict:
        from ..state import amend as _amend
        conn = db.connect(workspace / "asterism.db")
        try:
            try:
                return _amend.resolve_amend(
                    conn, workspace, decision_id, action=body.action,
                    body=body.body, reason=body.reason)
            except ValueError as e:
                raise HTTPException(status_code=409, detail=str(e))
        finally:
            conn.close()

    @app.post("/api/problems/{problem}/approve-ingest")
    def approve_ingest(problem: str) -> dict:
        import argparse
        from ..core import cli as _cli
        code = _cli.cmd_approve_ingest(argparse.Namespace(problem=problem))
        if code != 0:
            raise HTTPException(
                status_code=409,
                detail=f"{problem!r} is not awaiting ingest sign-off")
        return {"problem": problem, "action": "approve-ingest"}

    @app.post("/api/problems/{problem}/reject-ingest")
    def reject_ingest(problem: str, body: RejectIngestBody) -> dict:
        import argparse
        from ..core import cli as _cli
        code = _cli.cmd_reject_ingest(argparse.Namespace(
            problem=problem, reason=body.reason))
        if code != 0:
            raise HTTPException(
                status_code=409,
                detail=f"{problem!r} is not awaiting ingest sign-off")
        return {"problem": problem, "action": "reject-ingest"}

    # -- daemon control --------------------------------------------------

    @app.get("/api/daemon")
    def daemon() -> dict:
        from ..core.cli import daemon_status
        return daemon_status(workspace)

    @app.post("/api/daemon/start")
    def daemon_start_ep(body: DaemonStartBody) -> dict:
        from ..core.cli import daemon_start
        code, msg = daemon_start(workspace, scope=body.scope, once=body.once)
        if code != 0:
            raise HTTPException(status_code=409, detail=msg)
        return {"message": msg}

    @app.post("/api/daemon/stop")
    def daemon_stop_ep(body: DaemonStopBody) -> dict:
        from ..core.cli import daemon_stop
        code, msg = daemon_stop(workspace, force=body.force)
        if code != 0:
            raise HTTPException(status_code=500, detail=msg)
        return {"message": msg}

    # -- SSE log tail -----------------------------------------------------

    @app.get("/api/events/stream")
    async def events_stream() -> StreamingResponse:
        """Tail the current daemon log. Follows the daemon-current.txt
        pointer and switches files when a new daemon run rotates it."""
        pointer = workspace / ".asterism" / "logs" / "daemon-current.txt"

        async def gen():
            current: Path | None = None
            fh = None
            try:
                while True:
                    target: Path | None = None
                    try:
                        target = Path(
                            pointer.read_text(encoding="utf-8").strip())
                    except OSError:
                        target = None
                    if target != current:
                        if fh is not None:
                            fh.close()
                            fh = None
                        current = target
                        if current is not None and current.exists():
                            fh = open(current, "r", encoding="utf-8",
                                      errors="replace")
                            # Start near the end: last ~8KB of history.
                            fh.seek(0, 2)
                            back = min(fh.tell(), 8192)
                            fh.seek(fh.tell() - back)
                            if back:
                                fh.readline()  # drop the partial line
                    if fh is not None:
                        while True:
                            line = fh.readline()
                            if not line:
                                break
                            yield f"data: {line.rstrip()}\n\n"
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1.0)
            finally:
                if fh is not None:
                    fh.close()

        return StreamingResponse(gen(), media_type="text/event-stream")

    # -- static SPA (built web/dist; dev mode uses the Vite proxy) --------

    if WEB_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"),
                  name="assets")

        @app.get("/favicon.svg", include_in_schema=False)
        def favicon() -> FileResponse:
            return FileResponse(WEB_DIST / "favicon.svg")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            # index.html must never be cached: it names the hashed asset
            # bundles, and a stale copy pins users to a dead JS build.
            return FileResponse(
                WEB_DIST / "index.html",
                headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/", include_in_schema=False)
        def index_missing() -> PlainTextResponse:
            return PlainTextResponse(
                "Asterism API is running, but the UI build is missing.\n"
                "Build it once with: cd web && npm install && npm run build\n",
                status_code=200)

    return app
