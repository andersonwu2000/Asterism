"""The human command queue over HTTP — `/api/commands` and the
multi-problem run (human_interface_design.md §3.3, §1.4).

Its own module on the `projects_api.py` precedent: `app.py` is at its
size watermark, and a surface with one read, two writes, two previews
and a shared refusal shape is a natural unit. Every write goes through
`state/commands`, which owns the SQL; this file only translates the
refusal types into the honest HTTP answers — the `resolve_amend` shape:
KeyError = the named thing is not there (404), ValueError = malformed
(422), an existing-but-refused write (409).

Serve does not apply anything. It INSERTs the queue row and hands back
the id; the daemon's tick applies it. That is what makes the command
idempotent, answerable later, and impossible to half-execute inside an
HTTP handler.
"""
from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

from ..state import commands as _commands
from ..state import db
from . import data as _data


class CommandBody(BaseModel):
    """§3.3's row, minus the bookkeeping the queue fills in. `payload`
    carries the strategist decision's own fields (the shape the appliers
    already consume), so the front-end never learns a second vocabulary."""
    problem: str
    kind: str
    payload: dict = {}
    idempotency_key: str = ""
    expected_revision: int | None = None


class PreviewBody(BaseModel):
    problem: str
    kind: str
    payload: dict = {}


class StartManyBody(BaseModel):
    problems: list[str] = []
    once: bool = False


class StartManyPreviewBody(BaseModel):
    """The same list, read rather than run. `project` narrows the board
    read to one shelf — the chip must be the SHELF's own, or the confirm
    window and the row the reader ticked disagree about the task."""
    problems: list[str] = []
    project: "str | None" = None


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount the command endpoints. `ro` is app.py's `_ro` contextmanager
    — borrowed so the reads inherit the same 404/503 semantics."""

    @contextlib.contextmanager
    def _writes():
        if not (workspace / "asterism.db").exists():
            raise HTTPException(status_code=404, detail="NO_DATABASE")
        conn = db.connect(workspace / "asterism.db")
        try:
            yield conn
        except KeyError as e:
            raise HTTPException(
                status_code=404,
                detail=f"no problem {e.args[0]!r}") from e
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        finally:
            conn.close()

    @app.post("/api/commands", status_code=202)
    def post_command(body: CommandBody) -> dict:
        """202: the command is QUEUED, not done. The receipt is the id;
        `GET /api/commands/{id}` carries the outcome once the daemon's
        tick has applied it."""
        with _writes() as conn:
            cid = _commands.enqueue(
                conn, problem=body.problem, kind=body.kind,
                payload=body.payload or {},
                idempotency_key=body.idempotency_key,
                expected_revision=body.expected_revision)
            return {"id": cid, "status": "queued"}

    @app.get("/api/commands/{command_id}")
    def get_command(command_id: int) -> dict:
        """The receipt's other half. A ghost id is a 404 — an empty 200
        would read as "queued, nothing yet"."""
        if not (workspace / "asterism.db").exists():
            raise HTTPException(status_code=404, detail="NO_DATABASE")
        with ro(workspace) as conn:
            row = _commands.get(conn, command_id)
        if row is None:
            raise HTTPException(status_code=404,
                                detail=f"no command {command_id}")
        return row

    @app.post("/api/commands/preview")
    def preview_command(body: PreviewBody) -> dict:
        """What the command would close (§1.3's confirm window). Nothing
        is queued and nothing moves — a read on the read-only connection,
        which is the enforcement, not a promise."""
        if not (workspace / "asterism.db").exists():
            return {"affected": [], "cascade": False, "revision": 0}
        with ro(workspace) as conn:
            return _commands.preview(
                conn, problem=body.problem, kind=body.kind,
                payload=body.payload or {})

    @app.post("/api/daemon/start-many/preview")
    def daemon_start_many_preview(body: StartManyPreviewBody) -> dict:
        """What pressing Run would do to each ticked name (§1.3: every
        command's confirm window shows the preview first).

        One row per name, in the order they were sent, and the row says
        the four things a reader needs: is it a task at all, what state
        is it in, did a person take it off the live path, and would this
        run actually reach it. Nothing here starts anything — a read on
        the read-only connection, which is the enforcement.

        A pattern lands in the same place it lands in the real endpoint:
        `b%` is not a problem name, so it is UNKNOWN rather than quietly
        expanded (the post-incident defence, kept in the preview so the
        reader is never shown a list the run would not honour)."""
        names = [str(n).strip() for n in (body.problems or []) if str(n).strip()]
        from .daemon_cache import daemon_status
        daemon = daemon_status(workspace) if (
            workspace / "asterism.db").exists() else {}
        running = bool(daemon.get("running"))
        scope = daemon.get("scope")
        rows: "list[dict]" = []
        if (workspace / "asterism.db").exists():
            with ro(workspace) as conn:
                known = {str(r["name"]): r for r in
                         _data.board(conn, daemon=daemon,
                                     project=body.project)["problems"]}
                for name in names:
                    row = known.get(name)
                    if row is None:
                        rows.append({"name": name, "found": False,
                                     "status": None, "benched": False,
                                     "effect": "unknown"})
                        continue
                    benched = bool(row.get("benched"))
                    if running and db.scope_matches(conn, scope, name):
                        effect = "running"
                    elif benched:
                        effect = "benched"
                    else:
                        effect = "start"
                    rows.append({"name": name, "found": True,
                                 "status": str(row["status"]),
                                 "benched": benched, "effect": effect})
        else:
            rows = [{"name": n, "found": False, "status": None,
                     "benched": False, "effect": "unknown"} for n in names]
        return {
            "problems": rows,
            "start": [r["name"] for r in rows if r["effect"] == "start"],
            # a run cannot start over a running one — `daemon_start`
            # refuses and the POST is a 409. Said here, before the press.
            "blocked": running,
            "daemon": {"running": running, "scope": scope},
        }

    @app.post("/api/daemon/start-many")
    def daemon_start_many(body: StartManyBody) -> dict:
        """Run several problems at once (§1.4) — by EXPLICIT list only.

        `/api/daemon/start` takes one exact problem name on purpose: a
        pattern one HTTP typo wide once swept 148 files off unrelated
        problems. This endpoint keeps that defence and only relaxes the
        count: every name must exist EXACTLY (no `%`, no prefixes), and
        the scope it starts the daemon with is the same explicit list
        (`db.scope_sql`), so the run covers those problems and no others.
        """
        from ..core.cli import daemon_start
        names = [str(n).strip() for n in (body.problems or []) if str(n).strip()]
        if not names:
            raise HTTPException(
                status_code=422,
                detail="problems is required — name the problems to run")
        if len(set(names)) != len(names):
            raise HTTPException(status_code=422,
                                detail="problems contains duplicates")
        if any(db.SCOPE_SEP in n for n in names):
            raise HTTPException(
                status_code=422,
                detail=f"a problem name cannot contain {db.SCOPE_SEP!r}")
        if not (workspace / "asterism.db").exists():
            raise HTTPException(status_code=404, detail="NO_DATABASE")
        with ro(workspace) as conn:
            known = {str(r[0]) for r in conn.execute(
                "SELECT name FROM problems")}
        missing = [n for n in names if n not in known]
        if missing:
            # A pattern lands here too, and that is the point: `b%` is
            # not a problem, so it is reported as missing rather than
            # quietly expanded.
            raise HTTPException(
                status_code=404,
                detail=f"unknown problem(s): {', '.join(sorted(missing))}")
        scope = db.SCOPE_SEP.join(names)
        code, msg = daemon_start(workspace, scope=scope, once=body.once)
        from .daemon_cache import invalidate as _invalidate_status
        _invalidate_status(workspace)
        if code != 0:
            raise HTTPException(status_code=409, detail=msg)
        return {"message": msg, "scope": scope, "problems": names}
