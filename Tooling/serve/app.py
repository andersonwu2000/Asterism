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
import re
import sqlite3
import threading
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


class ApproveIngestBody(BaseModel):
    """The Library decision is made HERE, information in hand (owner:
    a human signs; nothing enters the Library automatically). None =
    keep the standing flag."""
    library: bool | None = None


class RejectDeclBody(BaseModel):
    decl: str  # slug or Problems.<problem>.<slug> FQN (as review prints)
    reason: str | None = None


class ProblemCreateBody(BaseModel):
    name: str
    # either a raw manifest, or the structured halves the UI works in
    manifest: str | None = None
    body: str | None = None
    settings: dict | None = None
    defs: str | None = None
    root: str | None = None
    # shelf ids to cite (Papers/<id> — bound with origin='user')
    papers: list[str] | None = None


class PaperAddBody(BaseModel):
    path: str


class PaperBindBody(BaseModel):
    paper_id: str


class ManifestUpdateBody(BaseModel):
    body: str | None = None
    settings: dict | None = None


class ConfigSetBody(BaseModel):
    key: str
    value: str | int


class DaemonStartBody(BaseModel):
    scope: str | None = None
    once: bool = False


class DaemonStopBody(BaseModel):
    force: bool = False


def _creds_path() -> Path:
    """Claude Code's local session file. Module-level so tests can
    monkeypatch it — a test must never touch the REAL login."""
    return Path.home() / ".claude" / ".credentials.json"


def datetime_now_compact() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def claude_exe() -> "str | None":
    """Resolve the claude CLI. PATH first; then its known install
    homes — the official installer's PATH edit lands in NEW sessions
    (and on a fresh Windows it can miss entirely), so a serve started
    before/during the install would otherwise report 'not installed'
    about a CLI that is sitting right there."""
    import os
    import shutil
    p = shutil.which("claude")
    if p:
        return p
    candidates = [Path.home() / ".local" / "bin" / "claude.exe"]
    if os.environ.get("APPDATA"):
        candidates.append(
            Path(os.environ["APPDATA"]) / "npm" / "claude.cmd")
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def spawn_claude_login() -> None:
    """Open the OFFICIAL Claude Code login: a terminal window running
    `claude` (its first-run flow does the OAuth dance and writes the
    credentials). Module-level so the setup wizard's one-click flow
    can pop the window the moment the CLI lands. Raises OSError when
    no terminal can be spawned on this platform."""
    import subprocess
    import sys
    exe = claude_exe() or "claude"
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/k", exe],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif sys.platform == "darwin":
        subprocess.Popen(
            ["osascript", "-e",
             f'tell application "Terminal" to do script "{exe}"'])
    else:
        raise OSError("no terminal spawner for this platform")


def create_app(workspace: Path) -> FastAPI:
    workspace = workspace.resolve()
    app = FastAPI(title="Asterism", docs_url=None, redoc_url=None)

    # mission control (GET /api/run) lives in its own module
    from .run import register as _register_run
    _register_run(app, workspace, _ro)

    # the setup wizard's backend (/api/setup/*)
    from .setup import register as _register_setup
    _register_setup(app, workspace)

    # reader's Lean scratch pipeline (POST /api/lean/eval)
    from .lean_eval import register as _register_lean_eval
    _register_lean_eval(app, workspace)

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
            "claude": _claude_status(),
        }

    def _claude_status() -> dict:
        """Auth awareness, not auth implementation: the login flow
        itself belongs to Claude Code (its OAuth client, its
        credentials file) — the UI only needs to KNOW the state and
        open the official wizard. Cheap checks, polled with meta."""
        import json as _json
        installed = claude_exe() is not None
        creds = _creds_path()
        logged_in = creds.exists()
        subscription = None
        if logged_in:
            try:
                subscription = _json.loads(
                    creds.read_text(encoding="utf-8"))[
                    "claudeAiOauth"].get("subscriptionType")
            except Exception:  # noqa: BLE001 — display garnish only
                pass
        return {"installed": installed, "logged_in": logged_in,
                "subscription": subscription}

    @app.post("/api/claude/logout")
    def claude_logout() -> dict:
        """Log out locally: the credentials file IS the local session,
        so logging out = retiring it (a timestamped backup, never a
        delete — reversible by hand). Claude Code asks for a fresh
        login on its next start; running agents keep the session they
        already hold, NEW agent spawns use whatever is logged in next.
        This is the owner's mid-run account switch (quota reset)."""
        creds = _creds_path()
        if not creds.exists():
            return {"logged_out": False, "detail": "already logged out"}
        stamp = datetime_now_compact()
        creds.rename(creds.with_name(f".credentials.json.bak-{stamp}"))
        # the quota memo still holds the OLD account's meters for up
        # to 2 minutes — flush so the switch is visible immediately
        from .run import reset_quota_memo
        reset_quota_memo()
        return {"logged_out": True}

    @app.post("/api/claude/login")
    def claude_login() -> dict:
        """Open the OFFICIAL login (see spawn_claude_login). The UI
        polls /api/meta until logged_in flips. Best-effort per
        platform; on failure the caller shows the manual command."""
        if claude_exe() is None:
            raise HTTPException(
                status_code=409,
                detail="claude CLI is not installed — finish the setup"
                       " wizard (#/setup) first")
        try:
            spawn_claude_login()
        except OSError as e:
            return {"opened": False, "manual": "claude",
                    "detail": str(e)}
        return {"opened": True}

    # -- reads ----------------------------------------------------------

    @app.get("/api/problems")
    def problems() -> dict:
        if not (workspace / "asterism.db").exists():
            return {"problems": []}  # fresh workspace — empty board
        from ..core.cli import daemon_status
        daemon = daemon_status(workspace)
        with _ro(workspace) as conn:
            return _data.board(conn, daemon=daemon)

    @app.get("/api/problems/{problem}")
    def problem(problem: str) -> dict:
        from ..core.cli import daemon_status
        daemon = daemon_status(workspace)
        with _ro(workspace) as conn:
            d = _data.problem_detail(conn, workspace, problem,
                                     daemon=daemon)
        if d is None:
            raise HTTPException(status_code=404,
                                detail=f"unknown problem {problem!r}")
        return d

    @app.get("/api/problems/{problem}/goals/{goal_id}")
    def goal(problem: str, goal_id: int) -> dict:
        with _ro(workspace) as conn:
            d = _data.goal_detail(conn, problem, goal_id, workspace)
        if d is None:
            raise HTTPException(status_code=404,
                                detail=f"no goal {goal_id} in {problem!r}")
        return d

    @app.get("/api/problems/{problem}/strategies/{strategy_id}")
    def strategy(problem: str, strategy_id: int) -> dict:
        with _ro(workspace) as conn:
            d = _data.strategy_detail(conn, problem, strategy_id)
        if d is None:
            raise HTTPException(
                status_code=404,
                detail=f"no strategy {strategy_id} in {problem!r}")
        return d

    @app.get("/api/problems/{problem}/file")
    def problem_file(problem: str, path: str) -> dict:
        text = _data.read_problem_file(workspace, problem, path)
        if text is None:
            raise HTTPException(status_code=404, detail="no such file")
        return {"path": path, "content": text}

    @app.get("/api/problems/{problem}/manifest")
    def manifest_get(problem: str) -> dict:
        """The Manifest as the UI works with it: structured settings +
        the natural-language body, plus whether a strategist amend is
        pending (manual edits are locked then — the two writes would
        race on the same file)."""
        from ..state import manifest as _mfst
        from ..state import settings as _settings
        path = db.problem_dir(workspace, problem) / "Manifest.md"
        if not path.exists():
            raise HTTPException(status_code=404, detail="no Manifest.md")
        _, body = _mfst.split_raw(path.read_text(encoding="utf-8"))
        # Dual-read (frontmatter dissolve): file parse gives the legacy
        # fallback (frontmatter + `## Lemma hints` body section), DB
        # rows win where present. Read-only — GET never migrates.
        mfst = _mfst.parse(path)
        merged = {
            "axioms_whitelist": list(mfst.axioms_whitelist),
            "forbidden_lemmas": list(mfst.forbidden_lemmas),
            "library": bool(mfst.library),
        }
        pending = False
        if (workspace / "asterism.db").exists():
            with _ro(workspace) as conn:
                merged.update(_settings.read(conn, problem))
                row = conn.execute(
                    "SELECT 1 FROM strategist_decisions WHERE problem = ?"
                    "   AND decision_kind = 'RequestUserAmend'"
                    "   AND outcome = 'awaiting_human' LIMIT 1",
                    (problem,)).fetchone()
                pending = row is not None
        return {
            "problem": problem,
            "body": body,
            "settings": merged,
            "pending_amend": pending,
        }

    @app.post("/api/problems/{problem}/manifest")
    def manifest_update(problem: str, body: ManifestUpdateBody) -> dict:
        from ..state import manifest as _mfst
        if (workspace / "asterism.db").exists():
            with _ro(workspace) as conn:
                row = conn.execute(
                    "SELECT 1 FROM strategist_decisions WHERE problem = ?"
                    "   AND decision_kind = 'RequestUserAmend'"
                    "   AND outcome = 'awaiting_human' LIMIT 1",
                    (problem,)).fetchone()
            if row is not None:
                raise HTTPException(
                    status_code=409,
                    detail="a strategist amend is pending on this Manifest"
                           " — resolve it in the Inbox first")
        # Body (human prose) still lives in Manifest.md; settings go to
        # the DB chokepoint (frontmatter dissolve) — the yaml lines stop
        # changing and stay as legacy fallback for unmigrated problems.
        if body.body is not None:
            rc, msg = _mfst.update_manifest(
                workspace, problem, body=body.body, settings=None)
            if rc != 0:
                raise HTTPException(status_code=422, detail=msg)
        if body.settings:
            from ..state import settings as _settings
            conn = db.connect(workspace / "asterism.db")
            try:
                known = conn.execute(
                    "SELECT library_bridged_at FROM problems WHERE name = ?",
                    (problem,)).fetchone()
                if known is None:
                    raise HTTPException(status_code=404,
                                        detail=f"unknown problem {problem!r}")
                # Mutability classes (owner's inventory, 2026-07-08).
                # The axiom gate is FIXED AT CREATION: ManifestCache
                # hot-reloads and the gate re-reads it per validation,
                # so a mid-life edit would re-tune soundness under
                # live (and past) proofs — the one genuinely dangerous
                # knob. Enforced here, not just hidden in the UI.
                current = {
                    "axioms_whitelist": [], "library": False}
                mpath = db.problem_dir(workspace, problem) / "Manifest.md"
                if mpath.exists():
                    parsed = _mfst.parse(mpath)
                    current["axioms_whitelist"] = list(parsed.axioms_whitelist)
                    current["library"] = bool(parsed.library)
                current.update(_settings.read(conn, problem))
                if "axioms_whitelist" in body.settings:
                    asked = sorted(str(a) for a in
                                   (body.settings["axioms_whitelist"] or []))
                    have = sorted(str(a) for a in current["axioms_whitelist"])
                    if asked != have:
                        raise HTTPException(
                            status_code=409,
                            detail="AXIOMS_LOCKED: the axiom gate is fixed"
                                   " when the problem is created — it never"
                                   " changes mid-life")
                # `library` settles once the harvest bridged: flipping
                # it after that is a no-op wearing a control's face.
                if ("library" in body.settings
                        and known["library_bridged_at"] is not None
                        and bool(body.settings["library"])
                        != bool(current["library"])):
                    raise HTTPException(
                        status_code=409,
                        detail="LIBRARY_SETTLED: this problem's work is"
                               " already in the Library")
                for key, value in body.settings.items():
                    try:
                        _settings.write(conn, problem, key, value)
                    except ValueError as e:
                        raise HTTPException(status_code=422,
                                            detail=str(e)) from e
            finally:
                conn.close()
        return {"problem": problem,
                "message": "OK: saved — the engine picks changes up on"
                           " its next tick"}

    # what the human reads before vouching, per kind (anchor+claim §:
    # data-defs are vouched BY BODY — the construction IS the meaning;
    # propositions are vouched by statement, the kernel owns the proof)
    _ANY_DECL_RE = re.compile(
        r"^(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+)?"
        r"(?:private\s+|protected\s+)?"
        r"(theorem|lemma|def|abbrev|structure|class|instance|inductive)\s+"
        r"([A-Za-z0-9_'₀-₉α-ω.]+)",
        re.M)
    _PROP_KINDS = {"theorem", "lemma"}

    def _vouch_signature(conn, problem: str, name: str,
                         cache: dict) -> "str | None":
        """The vouchable source for one name — statement head for
        propositions, FULL source incl. `:=` body for def-kinds
        (owner: a definition without its body is not readable).
        Read-side display extraction from the proof file, never
        soundness."""
        from .data import _stmt_head
        slug = str(name).split(".")[-1]
        row = conn.execute(
            "SELECT lean_path FROM goals WHERE problem = ? AND slug = ?"
            " ORDER BY id DESC LIMIT 1", (problem, slug)).fetchone()
        if row is None or not row["lean_path"]:
            return None
        path = str(row["lean_path"])
        if path not in cache:
            try:
                cache[path] = (workspace / path).read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                cache[path] = ""
        text = cache[path]
        decls = list(_ANY_DECL_RE.finditer(text))
        for i, m in enumerate(decls):
            if m.group(2).split(".")[-1] != slug:
                continue
            if m.group(1) in _PROP_KINDS:
                return _stmt_head(text, m.start())
            seg = text[m.start():
                       decls[i + 1].start() if i + 1 < len(decls)
                       else len(text)]
            # trim the closing `end Namespace` line off the last decl
            seg = re.sub(r"\n\s*end\s[\w.]*\s*$", "", seg.rstrip())
            return seg.rstrip()
        return None

    @app.get("/api/problems/{problem}/review")
    def review(problem: str) -> dict:
        with _ro(workspace) as conn:
            d = _data.review(conn, problem)
            if d is not None:
                # the vouch surface is small (deliverables ∪ anchors) —
                # attach every entry's readable signature, and normalize
                # anchor/claim entries to records (they arrive as bare
                # names OR {kind, module, name})
                cache: dict = {}
                for dv in d.get("deliverables") or []:
                    prob = str(dv.get("problem") or problem)
                    dv["signature"] = _vouch_signature(
                        conn, prob, str(dv.get("slug") or dv.get("fq")),
                        cache)
                    for key in ("anchors", "claims"):
                        norm = []
                        for e in dv.get(key) or []:
                            rec = dict(e) if isinstance(e, dict) else \
                                {"name": str(e)}
                            rec["signature"] = _vouch_signature(
                                conn, prob, str(rec.get("name", "")), cache)
                            norm.append(rec)
                        dv[key] = norm
        if d is None:
            raise HTTPException(
                status_code=404,
                detail="no review snapshot stored (problem not yet at "
                       "Ingest, or pre-v22 data); use refresh to compute")
        return d

    # review refresh — the ONE path that may touch the gateway (charter
    # §4): an explicit async job, never a GET side effect. One job per
    # problem at a time; state is poll-able.
    refresh_jobs: dict[str, dict] = {}
    refresh_lock = threading.Lock()

    @app.post("/api/problems/{problem}/review/refresh")
    def review_refresh(problem: str) -> dict:
        if not (workspace / "asterism.db").exists():
            raise HTTPException(status_code=404, detail="NO_DATABASE")
        with refresh_lock:
            job = refresh_jobs.get(problem)
            if job and job.get("state") == "running":
                return job
            refresh_jobs[problem] = {"state": "running",
                                     "started_at": db.now()}

        def work() -> None:
            from ..quality import review as _review
            try:
                conn = db.connect(workspace / "asterism.db")
                try:
                    ok = _review.store_review_snapshot(
                        conn, workspace, problem)
                finally:
                    conn.close()
                refresh_jobs[problem] = {
                    "state": "done" if ok else "failed",
                    "finished_at": db.now()}
            except Exception as e:  # noqa: BLE001 — job state, not a crash
                refresh_jobs[problem] = {
                    "state": "failed", "error": str(e),
                    "finished_at": db.now()}

        threading.Thread(target=work, daemon=True).start()
        return refresh_jobs[problem]

    @app.get("/api/problems/{problem}/review/refresh")
    def review_refresh_state(problem: str) -> dict:
        return refresh_jobs.get(problem, {"state": "none"})

    @app.get("/api/inbox")
    def inbox() -> dict:
        if not (workspace / "asterism.db").exists():
            return {"amends": [], "signoffs": []}
        with _ro(workspace) as conn:
            return _data.inbox(conn, workspace)

    @app.get("/api/papers/{pid}/section")
    def paper_sec(pid: str, anchor: str | None = None) -> dict:
        d = _data.paper_section(workspace, pid, anchor)
        if d is None:
            raise HTTPException(status_code=404,
                                detail=f"paper {pid!r} not shelved here")
        return d

    # -- papers bookshelf (top-level page) ------------------------------

    @app.get("/api/papers")
    def papers() -> dict:
        if not (workspace / "asterism.db").exists():
            return _data.papers_list(None, workspace)
        with _ro(workspace) as conn:
            return _data.papers_list(conn, workspace)

    @app.get("/api/papers/{pid}/text")
    def paper_text(pid: str) -> dict:
        from ..papers import shelf as _shelf
        meta = _shelf.load_meta(workspace, pid)
        tp = _shelf.text_path(workspace, pid)
        if meta is None or not tp.exists():
            raise HTTPException(status_code=404,
                                detail=f"paper {pid!r} not shelved here")
        return {"id": pid, "source_name": meta.source_name,
                "pages": meta.pages,
                "text": tp.read_text(encoding="utf-8")}

    @app.get("/api/papers/{pid}/file")
    def paper_file(pid: str):
        """The original document (browser-native PDF viewing)."""
        from ..papers import shelf as _shelf
        pdir = _shelf.paper_dir(workspace, pid)
        original = next(
            (f for f in pdir.glob("paper.*") if f.is_file()), None)
        if original is None:
            raise HTTPException(status_code=404,
                                detail=f"paper {pid!r} has no original file")
        media = "application/pdf" if original.suffix == ".pdf" \
            else "text/plain; charset=utf-8"
        return FileResponse(original, media_type=media,
                            filename=f"{pid}{original.suffix}",
                            content_disposition_type="inline")

    @app.post("/api/papers/add")
    def paper_add(body: PaperAddBody) -> dict:
        """Shelve a local file by path (the CLI paper-add chokepoint).
        Content-hash identity: re-adding the same document is a no-op
        that returns the existing slot."""
        from ..papers import shelf as _shelf
        src = Path(body.path).expanduser()
        if not src.is_file():
            raise HTTPException(status_code=404,
                                detail=f"no such file: {src}")
        try:
            meta = _shelf.add_paper(workspace, src)
        except (_shelf.ScannedPdfError, ValueError) as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {"id": meta.id, "source_name": meta.source_name,
                "pages": meta.pages, "chars": meta.chars}

    @app.delete("/api/papers/{pid}")
    def paper_delete(pid: str) -> dict:
        """Remove a shelf slot. Refused while any problem cites it —
        unbind there first (the bindings are the citations agents rely
        on; deleting under them would orphan every reference)."""
        import shutil
        from ..papers import shelf as _shelf
        pdir = _shelf.paper_dir(workspace, pid)
        if _shelf.load_meta(workspace, pid) is None:
            raise HTTPException(status_code=404,
                                detail=f"paper {pid!r} not shelved here")
        if (workspace / "asterism.db").exists():
            with _ro(workspace) as conn:
                rows = conn.execute(
                    "SELECT problem FROM problem_papers WHERE paper_id = ?"
                    " ORDER BY problem", (pid,)).fetchall()
            if rows:
                names = ", ".join(str(r["problem"]) for r in rows)
                raise HTTPException(
                    status_code=409,
                    detail=f"cited by {names} — unbind it from those"
                           f" problems first")
        shutil.rmtree(pdir)
        return {"message": f"removed Papers/{pid}"}

    @app.get("/api/problems/{problem}/papers")
    def problem_papers(problem: str) -> dict:
        with _ro(workspace) as conn:
            return _data.problem_papers_detail(conn, workspace, problem)

    @app.post("/api/problems/{problem}/papers")
    def problem_paper_bind(problem: str, body: PaperBindBody) -> dict:
        from ..papers import shelf as _shelf
        if _shelf.load_meta(workspace, body.paper_id) is None:
            raise HTTPException(
                status_code=404,
                detail=f"paper {body.paper_id!r} not shelved here")
        conn = db.connect(workspace / "asterism.db")
        try:
            known = conn.execute(
                "SELECT 1 FROM problems WHERE name = ?",
                (problem,)).fetchone()
            if known is None:
                raise HTTPException(status_code=404,
                                    detail=f"unknown problem {problem!r}")
            db.bind_paper(conn, problem=problem, paper_id=body.paper_id,
                          origin="user")
            conn.commit()
        finally:
            conn.close()
        return {"message": f"bound Papers/{body.paper_id} to {problem}"}

    @app.delete("/api/problems/{problem}/papers/{pid}")
    def problem_paper_unbind(problem: str, pid: str) -> dict:
        conn = db.connect(workspace / "asterism.db")
        try:
            removed = db.unbind_paper(conn, problem=problem, paper_id=pid)
        finally:
            conn.close()
        if not removed:
            raise HTTPException(status_code=404,
                                detail="no such binding")
        return {"message": f"unbound Papers/{pid} from {problem}"}

    @app.get("/api/library")
    def library() -> dict:
        if not (workspace / "asterism.db").exists():
            return {"problems": []}
        with _ro(workspace) as conn:
            return _data.library(conn)

    @app.get("/api/library/{problem}")
    def library_chapter(problem: str) -> dict:
        """The harvested Library modules ONE problem contributed —
        the reading surface (curated text), not the engine record."""
        with _ro(workspace) as conn:
            d = _data.library_chapter(conn, workspace, problem)
        if d is None:
            raise HTTPException(status_code=404,
                                detail=f"{problem} has no bridged Library work")
        return d

    @app.get("/api/telemetry/usage")
    def usage() -> dict:
        """Burn figures. While a daemon runs, the window is THIS run
        (since its start time); idle, it's the all-time ledger — the
        response says which, so the UI never mislabels the window."""
        if not (workspace / "asterism.db").exists():
            return {"problems": [], "window": "all", "since": None}
        from ..core.cli import daemon_status
        d = daemon_status(workspace)
        since = d.get("started_at") if d.get("running") else None
        with _ro(workspace) as conn:
            out = _data.telemetry_usage(conn, since=since)
        out["window"] = "run" if since else "all"
        out["since"] = since
        return out

    # -- writes (CLI/state chokepoints only) ----------------------------

    @app.post("/api/inbox/amend/{decision_id}/resolve")
    def resolve_amend(decision_id: int, body: AmendResolveBody) -> dict:
        from ..state import amend as _amend
        if not (workspace / "asterism.db").exists():
            raise HTTPException(status_code=404, detail="NO_DATABASE")
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
    def approve_ingest(problem: str,
                       body: "ApproveIngestBody | None" = None) -> dict:
        import argparse
        from ..core import cli as _cli
        # the harvest decision lands with the signature: write the
        # library flag through the chokepoint BEFORE approving (the
        # librarian scheduler reads it after sign-off, so this is the
        # last honest moment to set it)
        if body is not None and body.library is not None:
            from ..state import settings as _settings
            conn = db.connect(workspace / "asterism.db")
            try:
                _settings.write(conn, problem, "library",
                                bool(body.library))
            finally:
                conn.close()
        code = _cli.cmd_approve_ingest(argparse.Namespace(problem=problem))
        if code != 0:
            raise HTTPException(
                status_code=409,
                detail=f"{problem!r} is not awaiting ingest sign-off")
        # "harvest to Library" means harvest NOW, not on some future
        # run the user has to know to start (owner call: the click IS
        # the go signal). Best-effort: a busy engine doesn't undo the
        # approval — the harvest then rides the next run naturally.
        harvest_run = None
        if body is not None and body.library:
            from ..core.cli import daemon_start
            rc, msg = daemon_start(workspace, scope=problem, once=True)
            harvest_run = "started" if rc == 0 else f"not started: {msg}"
        return {"problem": problem, "action": "approve-ingest",
                "library": None if body is None else body.library,
                "harvest_run": harvest_run}

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

    @app.post("/api/problems/{problem}/reject-decl")
    def reject_decl(problem: str, body: RejectDeclBody) -> dict:
        """Per-deliverable reject (GitHub-PR-review granularity): kills
        the node + every deliverable whose meaning depends on it, via
        the same `asterism reject` chokepoint. May warm the gateway —
        slow like review refresh, and equally explicit."""
        import argparse
        from ..core import cli as _cli
        code = _cli.cmd_reject(argparse.Namespace(
            decl=body.decl, problem=problem, reason=body.reason,
            dry_run=False))
        if code != 0:
            raise HTTPException(
                status_code=409,
                detail=f"reject failed for {body.decl!r} (see server log)")
        return {"problem": problem, "decl": body.decl, "action": "reject"}

    @app.post("/api/problems/create")
    def create_problem_ep(body: ProblemCreateBody) -> dict:
        """Author a new problem from the UI: write Manifest.md
        (+ optional Defs.lean / Root.lean), then run the same init
        chokepoint the CLI uses. Pure-NL creation is instant; a
        Defs/Root submission type-checks first (lake build — minutes).
        On init failure the created directory is rolled back so the
        form can be corrected and resubmitted."""
        import re as _re
        import shutil as _shutil
        from ..core.cli import init_problem
        name = body.name.strip()
        if not _re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*", name)                 or len(name) > 120:
            raise HTTPException(
                status_code=422,
                detail="problem name must be dot-separated identifiers, "
                       "e.g. Topology.my_theorem")
        from ..state import manifest as _mfst
        raw = body.manifest
        if raw is None and body.body is not None:
            st = body.settings or {}
            def _as_list(v: object) -> list:
                return v if isinstance(v, list) else []
            fm: dict[str, object] = {
                "problem": name,
                "axioms_whitelist": _as_list(st.get("axioms_whitelist")) or [
                    "propext", "Quot.sound", "Classical.choice"],
                "forbidden_lemmas": _as_list(st.get("forbidden_lemmas")),
                "library": bool(st.get("library", True)),
            }
            nl = body.body if body.body.startswith("\n") else "\n" + body.body
            raw = _mfst.compose(fm, nl)
        if raw is None or not raw.strip():
            raise HTTPException(status_code=422,
                                detail="Manifest must not be empty")
        pdir = db.problem_dir(workspace, name)
        if pdir.exists():
            raise HTTPException(
                status_code=409,
                detail=f"Problems/{'/'.join(name.split('.'))} already exists")
        created = False
        try:
            pdir.mkdir(parents=True)
            created = True
            (pdir / "Manifest.md").write_text(
                raw, encoding="utf-8", newline="\n")
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
            if body.settings or body.papers:
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

    @app.get("/api/config")
    def config_get() -> dict:
        from ..core import config as _cfg
        return {"settings": _cfg.ui_settings(workspace)}

    @app.post("/api/config")
    def config_set(body: ConfigSetBody) -> dict:
        from ..core import config as _cfg
        rc, msg = _cfg.set_ui_setting(workspace, body.key, body.value)
        if rc != 0:
            raise HTTPException(status_code=422, detail=msg)
        return {"message": msg}

    # -- daemon control --------------------------------------------------

    @app.get("/api/daemon")
    def daemon() -> dict:
        from ..core.cli import daemon_status
        return daemon_status(workspace)

    @app.post("/api/daemon/start")
    def daemon_start_ep(body: DaemonStartBody) -> dict:
        """Start the engine on ONE problem. Scope is required and must
        name an existing problem exactly — the CLI's pattern scopes and
        workspace-wide runs are deliberate operator acts, not one HTTP
        typo away (a no-scope run once swept 148 files off other
        problems)."""
        from ..core.cli import daemon_start
        scope = (body.scope or "").strip()
        if not scope:
            raise HTTPException(
                status_code=400,
                detail="scope is required — start the engine from a"
                       " problem's Run button (one problem at a time)")
        with _ro(workspace) as conn:
            known = conn.execute(
                "SELECT 1 FROM problems WHERE name = ?", (scope,)).fetchone()
        if known is None:
            raise HTTPException(status_code=404,
                                detail=f"unknown problem {scope!r}")
        code, msg = daemon_start(workspace, scope=scope, once=body.once)
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
