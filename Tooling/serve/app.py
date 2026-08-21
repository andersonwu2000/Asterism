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
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..state import db
from . import data as _data

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIST = REPO_ROOT / "web" / "dist"

# Paper upload guard: bodies are read whole into memory (papers are
# tens of MB at most; the Scholar fetch cap is 50MB) — an accidental
# drop of something huge should bounce, not balloon the serve process.
_MAX_UPLOAD_BYTES = 100 * 2**20


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
    keep the standing flag. `signer` is the displayed name of the
    signature record (v27) — the record's evidence half (Claude login,
    OS user, host, content seal) is captured server-side, never typed."""
    library: bool | None = None
    signer: str | None = None


class RejectDeclBody(BaseModel):
    decl: str  # slug or Problems.<problem>.<slug> FQN (as review prints)
    reason: str | None = None


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


class PaperRenameBody(BaseModel):
    title: str = ""


class PaperBindBody(BaseModel):
    paper_id: str


class IntentUpdateBody(BaseModel):
    charter: str | None = None
    word: str | None = None
    settings: dict | None = None


class ConfigSetBody(BaseModel):
    key: str
    value: str | int


class DaemonStartBody(BaseModel):
    scope: str | None = None
    once: bool = False


class DaemonStopBody(BaseModel):
    force: bool = False


class ShutdownBody(BaseModel):
    """`force` carries the SAME meaning it has for the daemon: abandon
    in-flight agents instead of draining them. Shutdown refuses while
    the engine is live without it, rather than deciding on the user's
    behalf that their run is expendable."""
    force: bool = False


def _creds_path() -> Path:
    """Claude Code's local session file. Module-level so tests can
    monkeypatch it — a test must never touch the REAL login."""
    return Path.home() / ".claude" / ".credentials.json"


def datetime_now_compact() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def claude_exe() -> "str | None":
    """Resolve the claude CLI. PATH first; then its known install homes
    — the official installer's PATH edit lands in NEW sessions (and on a
    fresh Windows it can miss entirely), so a serve started
    before/during the install would otherwise report 'not installed'
    about a CLI that is sitting right there.

    The knowledge itself now lives with the provider
    (`llm/claude_cli.resolve_claude_executable`, beside
    `resolve_agy_executable`); this stays as the name the accounts panel
    and the login flow already call. Kept module-level so tests can
    monkeypatch it."""
    from ..llm.claude_cli import resolve_claude_executable
    return resolve_claude_executable()


def spawn_claude_login() -> None:
    """Hand off to Claude Code's OWN browser login. `claude auth login`
    opens the user's browser straight to the Anthropic OAuth page and
    finishes through a localhost callback - the user clicks Authorize
    and is done, no `/login` slash-command to know or type. The console
    we spawn is a transient launcher: it closes itself the instant
    `claude` exits, and is visible only as the safety net for Claude
    Code's code-paste fallback (rare - browser can't reach the callback
    on WSL/SSH/blocked ports). We never touch the OAuth secrets; the
    whole flow is Claude Code's. Module-level so the setup wizard's
    one-click flow can trigger it the moment the CLI lands. Raises
    OSError when no console can be spawned on this platform."""
    import subprocess
    import sys
    exe = claude_exe() or "claude"
    args = ["auth", "login", "--claudeai"]
    if sys.platform == "win32":
        if exe.lower().endswith((".cmd", ".bat")):
            # a batch shim must go through cmd; /c (not /k) so the
            # window closes itself once login finishes
            subprocess.Popen(["cmd", "/c", exe, *args],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([exe, *args],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif sys.platform == "darwin":
        cmd = " ".join([exe, *args])
        subprocess.Popen(
            ["osascript", "-e",
             f'tell application "Terminal" to do script "{cmd}"'])
    else:
        raise OSError("no terminal spawner for this platform")


def _schedule_process_exit(delay: float = 0.4) -> None:
    """Exit AFTER the response has flushed — this is the process the
    caller is talking to, so it cannot exit inside the handler.

    A named module-level seam, and the name is the point: a test must be
    able to replace the WHOLE mechanism, not just its last instruction.
    Patching `os._exit` alone does not work here and the failure is
    vicious — `monkeypatch` is undone at teardown while this thread is
    still sleeping, so it wakes into the REAL `os._exit` and kills the
    pytest worker. Under xdist that reads as `node down: Not properly
    terminated` in whatever test happened to be running 0.4s later, six
    different victims across six runs, and never reproducible alone
    because a single-file run was exiting anyway — with code 0, which
    is what `os._exit(0)` leaves behind (found by the engine side,
    2026-08-12; reproduced here before fixing).

    The general shape, worth remembering: a background thread that
    outlives the patch meant to contain it. Anything that defers a side
    effect past the end of a test needs a seam at the SCHEDULING point.
    """
    def _bye() -> None:
        time.sleep(delay)
        os._exit(0)

    threading.Thread(target=_bye, daemon=True).start()


#: How to ASK a backend what it can run. Only agy answers today
#: (`agy models`, ~2.5s, zero tokens); `codex --help` carries `--model`
#: and no listing subcommand, and claude takes any name. This is the
#: third provider fact the console has had to keep on its own side —
#: after install and auth — so it wants declaring (`models_argv`)
#: rather than living here.
_MODELS_ARGV: "dict[str, tuple[str, ...]]" = {"antigravity": ("models",)}

#: the probe costs a subprocess, and the settings page polls
_models_memo: "dict[str, object]" = {"at": 0.0, "value": None}


def _model_groups(workspace: Path, *, probe: bool = False) -> "list[dict]":
    """Every model a seat may be pointed at, grouped by the backend
    that runs it.

    One picker, not two. A seat's backend is not an independent choice
    — it is implied by the model — so offering both invites them to
    disagree (`provider: codex` with `claude-sonnet-5` is a run that
    dies at its first spawn) and draws one fact twice.

    `probe=False` is the POLLED answer and never spawns anything: the
    settings page is read every minute and a subprocess on that path is
    what the side-effect fence exists to catch (it caught this, and it
    was right). Asking a backend to list its models is an action, on its
    own endpoint, memoized — `source` says which answer you are looking
    at, because a declared list is how a retired model name stays
    pickable.
    """
    import subprocess
    import time as _t
    from ..llm import capabilities as _caps
    from ..core import config as _cfg
    now = _t.monotonic()
    if _models_memo["value"] is not None and \
            now - float(_models_memo["at"]) < 600:
        return _models_memo["value"]  # type: ignore[return-value]
    out: "list[dict]" = []
    for name in sorted(_caps.CAPABILITIES):
        cap = _caps.capabilities_for(name)
        if cap.install_method == _caps.INSTALL_NOT_NEEDED:
            continue  # an HTTP endpoint takes whatever the server serves
        exe = None
        if name == "claude":
            exe = claude_exe()
        elif name == "antigravity":
            from ..llm.antigravity_cli import resolve_agy_executable
            exe = resolve_agy_executable()
        else:
            import shutil
            exe = shutil.which(name)
        models = list(_cfg.models_for(name))
        source = "declared"
        argv = _MODELS_ARGV.get(name) if probe else None
        if argv and exe:
            try:
                r = subprocess.run([exe, *argv], capture_output=True,
                                   text=True, timeout=30)
                if r.returncode == 0:
                    # `agy models` prints "<slug>\t<pretty name>"
                    live = [ln.split("\t")[0].strip()
                            for ln in (r.stdout or "").splitlines()
                            if ln.strip() and not ln.startswith(" ")]
                    live = [m for m in live if m and " " not in m]
                    if live:
                        models, source = live, "probe"
            except (OSError, subprocess.SubprocessError):
                pass  # keep the declared list; never blank the picker
        if models:
            out.append({"provider": name, "models": models,
                        "source": source, "installed": exe is not None})
    if probe:
        _models_memo.update(at=now, value=out)
    return out


def create_app(workspace: Path, *, prewarm: bool = False) -> FastAPI:
    workspace = workspace.resolve()
    app = FastAPI(title="Asterism", docs_url=None, redoc_url=None)
    if prewarm:
        # Cold-cache prewarm (serve entrypoint only — tests build apps
        # by the dozen): the first click into a big problem paid 2-3s
        # of cold file scans (citation imports + goal docs read
        # hundreds of L_ files; a cold Windows open costs ms each). One
        # background pass per problem moves that cost to boot, off the
        # user's first impression. Read-only throughout; failures are
        # silence, not startup errors.
        def _prewarm() -> None:
            time.sleep(1.0)  # let uvicorn come up first
            try:
                with _ro(workspace) as conn:
                    names = [str(r["name"]) for r in conn.execute(
                        "SELECT name FROM problems ORDER BY name")]
                for n in names:
                    with _ro(workspace) as conn:
                        _data.problem_detail(conn, workspace, n)
            except Exception:  # noqa: BLE001 — a warmer must never wound
                pass
        threading.Thread(target=_prewarm, daemon=True,
                         name="detail-prewarm").start()

    # mission control (GET /api/run) lives in its own module
    from .run import register as _register_run
    _register_run(app, workspace, _ro)

    # reader's Lean scratch pipeline (POST /api/lean/eval)
    from .lean_eval import register as _register_lean_eval
    _register_lean_eval(app, workspace)

    # explainer chat drawer (POST /api/chat, SSE)
    from .chat import register as _register_chat
    _register_chat(app, workspace)

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
            "antigravity": _agy_status(),
            "providers": _provider_rows(),
            "lean_ready": _lean_ready(),
        }

    def _env_key_present(var: str) -> bool:
        """PRESENCE of an api-key credential — never its value.

        Mirrors the consumer (`llm/zen_shim._key`): the process env
        wins, the workspace `.env` is the fallback. Reports only that
        a non-empty assignment exists; the key itself never crosses
        the HTTP layer — that is the whole reason the console has no
        input field for it (owner ruling, 2026-08-22)."""
        import os
        if os.environ.get(var, "").strip():
            return True
        try:
            for ln in (workspace / ".env").read_text(
                    encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln.startswith(var + "=") and ln[len(var) + 1:].strip():
                    return True
        except OSError:
            pass
        return False

    def _provider_rows() -> "list[dict]":
        """One row per DECLARED backend: what it is, and what this
        machine has of it.

        Written when codex became the third (2026-08-14). The accounts
        panel had a hand-written component per vendor, which is the
        branch-per-backend `llm/capabilities.py` exists to stop — in
        copy rather than in code, and the fourth backend would have
        wanted a fourth component.

        Cheap facts only: `installed` is a path lookup and claude's
        session is a file read. Readiness for an opaque backend costs a
        subprocess (agy's probe is ~2.5s) and this rides the 5s meta
        poll, so it is offered as an action, not measured here.
        """
        from ..llm import capabilities as _caps
        from ..core import config as _cfg
        rows: "list[dict]" = []
        for name in sorted(_caps.CAPABILITIES):
            cap = _caps.capabilities_for(name)
            exe = None
            extra: dict = {}
            if name == "claude":
                exe = claude_exe()
                st = _claude_status()
                extra = {"logged_in": st["logged_in"],
                         "subscription": st["subscription"]}
            elif name == "antigravity":
                from ..llm.antigravity_cli import (agy_identity,
                                                   resolve_agy_executable)
                exe = resolve_agy_executable()
                verdict, path = agy_identity()
                extra = {"identity": verdict,
                         "identity_path": str(path) if path else None}
            elif cap.exe_name is not None:
                # the DECLARED binary — zen rides codex's, so installed
                # means "the carrier is here", never a `zen` that will
                # not exist. Checked before install_method: a provider
                # can have nothing of its own to install and still
                # depend on a binary being present.
                import shutil
                exe = shutil.which(cap.exe_name)
            elif cap.install_method == _caps.INSTALL_NOT_NEEDED:
                # reached over HTTP — there is no binary to find, and
                # saying "not installed" about one would be a lie
                exe = ""
            else:
                # the provider ships a CLI named after itself — codex
                # ships `codex`. Anything else declares exe_name (branch
                # above); the installer bridge follows the same rule.
                import shutil
                exe = shutil.which(name)
            seats = []
            for seat in _cfg.UI_SEATS:
                try:
                    prov = _cfg.get(
                        f"{seat}.provider",
                        env_var=f"ASTERISM_{seat.upper()}_PROVIDER",
                        legacy_env=("ASTERISM_LLM_PROVIDER",),
                        default="claude", workspace=workspace)
                except Exception:  # noqa: BLE001 — display garnish only
                    continue
                if _caps.canonical(prov) == name:
                    seats.append({"seat": seat, "model": str(_cfg.get(
                        f"{seat}.model",
                        env_var=f"ASTERISM_{seat.upper()}_MODEL",
                        default="", workspace=workspace) or "") or None})
            if cap.auth_flow == _caps.AUTH_API_KEY and cap.env_key:
                extra["env_key"] = cap.env_key
                extra["key_present"] = _env_key_present(cap.env_key)
            rows.append({
                "name": name,
                "installed": exe is not None,
                "path": exe or None,
                "install_method": cap.install_method,
                "install_command": cap.install_command,
                "auth_flow": cap.auth_flow,
                "auth_state": cap.auth_state,
                "can_probe": bool(cap.readiness_argv),
                "seats": seats,
                **extra,
            })
        return rows

    def _agy_status() -> dict:
        """The OTHER account the framework can spend: Antigravity
        (`agy`), the subscription path to Gemini models.

        What is knowable from here is narrower than for Claude, and the
        page must not pretend otherwise: agy's credentials do not live
        in a file we can read (a spawn authenticates from a fake HOME
        just fine), so there is no `logged_in` to report. What IS
        knowable — and what a reader actually needs — is whether the
        CLI exists and whether any role is pointed at it, because a
        role on `provider: antigravity` with no `agy` installed is a
        run that fails at its first spawn.
        """
        from ..llm.antigravity_cli import resolve_agy_executable
        from ..llm import capabilities as _caps
        from ..core import config as _cfg
        roles: list[dict] = []
        for role in ("strategist", "adversary", "formalizer", "presearch",
                     "librarian", "scholar", "explainer"):
            try:
                prov = _cfg.get(f"{role}.provider",
                                env_var=f"ASTERISM_{role.upper()}_PROVIDER",
                                legacy_env=("ASTERISM_LLM_PROVIDER",),
                                default="claude", workspace=workspace)
            except Exception:  # noqa: BLE001 — display garnish only
                continue
            # `agy` is a legal spelling of the same seat (llm.get_provider
            # accepts it); comparing the raw string missed it and dropped
            # the role off the panel.
            if _caps.canonical(prov) == "antigravity":
                try:
                    model = _cfg.get(f"{role}.model",
                                     env_var=f"ASTERISM_{role.upper()}_MODEL",
                                     default="", workspace=workspace)
                except Exception:  # noqa: BLE001
                    model = ""
                roles.append({"role": role, "model": str(model) or None})
        exe = resolve_agy_executable()
        return {"installed": exe is not None, "path": exe, "roles": roles}

    _lean_ready_memo: dict = {"at": 0.0, "value": None}

    def _lean_ready() -> dict:
        """The console's SELF-CHECK (owner call): a missing Lean layer
        fails every run as silently as a missing login — and it can
        break long after install (a moved .elan, a cleaned disk). Same
        class as the auth banner, so it rides the same meta poll.
        Filesystem-only on purpose (no subprocess in a 3s-poll path —
        the side-effect fence agrees): which() catches the moved/
        deleted toolchain; a present-but-corrupt lake is the contract
        suite's job at run time. Memoized 60s (rglob walks a tree)."""
        import os
        import shutil
        now = time.monotonic()
        if _lean_ready_memo["value"] is not None and \
                now - _lean_ready_memo["at"] < 60:
            return _lean_ready_memo["value"]
        lake_ok = shutil.which("lake") is not None
        mathlib_ok = False
        build = (workspace / ".lake" / "packages" / "mathlib" / ".lake"
                 / "build" / "lib")
        if build.exists():
            for _p in build.rglob("*.olean"):
                mathlib_ok = True
                break
        server = workspace / ".lake" / "build" / "bin" / (
            "lean-asterism-server.exe" if os.name == "nt"
            else "lean-asterism-server")
        mathlib_ok = mathlib_ok and server.exists()
        value = {"lake": lake_ok, "mathlib": mathlib_ok}
        _lean_ready_memo.update(at=now, value=value)
        return value

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

    @app.post("/api/providers/{name}/check")
    def provider_check(name: str) -> dict:
        """Ask a backend whether the account behind it works.

        An ACTION, not a poll: `auth_state: opaque` means no file holds
        the answer, so the only honest check is making the CLI do
        something that needs the account (agy: `models`, ~2.5s). It is a
        necessary condition, never a sufficient one — nobody has
        measured how these fail with no credentials at all — so the
        answer is what happened, never "signed in".
        """
        from ..llm import capabilities as _caps
        cap = _caps.capabilities_for(name)
        if not cap.readiness_argv:
            raise HTTPException(
                status_code=400,
                detail=f"{name} declares no way to check it from here")
        exe = None
        if _caps.canonical(name) == "claude":
            exe = claude_exe()
        elif _caps.canonical(name) == "antigravity":
            from ..llm.antigravity_cli import resolve_agy_executable
            exe = resolve_agy_executable()
        else:
            import shutil
            exe = shutil.which(cap.exe_name or name)
        if exe is None:
            raise HTTPException(status_code=409,
                                detail=f"{name} is not installed here")
        import subprocess
        try:
            r = subprocess.run([exe, *cap.readiness_argv],
                               capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.SubprocessError) as e:
            return {"ok": False, "detail": f"could not run it: {e}"}
        lines = [ln.strip() for ln in (r.stdout or "").splitlines()
                 if ln.strip()]
        if r.returncode == 0:
            return {"ok": True,
                    "detail": f"reached the service, {len(lines)} line(s) back",
                    "lines": lines[:20]}
        return {"ok": False,
                "detail": (r.stderr or r.stdout or "").strip()[:300]}

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
        """Open Claude Code's own browser login (see
        spawn_claude_login). This is ALSO the account switch: signing
        in as another account overwrites the session, so switching
        needs no prior logout - if the user cancels, the current
        session is untouched. The UI polls /api/meta until the account
        flips. Best-effort per platform; on failure the caller shows
        the manual command."""
        if claude_exe() is None:
            raise HTTPException(
                status_code=409,
                detail="claude CLI is not installed — finish the setup"
                       " wizard (#/setup) first")
        try:
            spawn_claude_login()
        except OSError as e:
            return {"opened": False, "manual": "claude auth login",
                    "detail": str(e)}
        # a switch changes which account's meters are live - drop the
        # memo so the new account's plan windows show without the
        # 2-minute wait
        from .run import reset_quota_memo
        reset_quota_memo()
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

    @app.get("/api/problems/{problem}/programme")
    def problem_programme(problem: str, group: int | None = None) -> dict:
        """Research mode's argument layer: the current adversarially-
        passed Programme + its revision history (bodies of past/
        rejected rows stay in the DB — audit material, not page
        furniture).

        `group` selects one discussion group's chain (v35); omitted, the
        top group's — the problem's own argument. A group belonging to
        another problem is a 404, not somebody else's Programme."""
        with _ro(workspace) as conn:
            known = conn.execute(
                "SELECT 1 FROM problems WHERE name = ?",
                (problem,)).fetchone()
            if known is None:
                raise HTTPException(status_code=404,
                                    detail="unknown problem")
            if group is not None:
                card = _data.group_card(conn, group)
                if card is None or card["problem"] != problem:
                    raise HTTPException(
                        status_code=404,
                        detail=f"group {group} is not part of {problem}")
            try:
                return _data.programme(conn, problem, group)
            except sqlite3.OperationalError:
                return {"current": None, "history": [],
                        "group_id": None, "charter": None, "groups": []}

    @app.get("/api/problems/{problem}/events")
    def problem_events(problem: str) -> dict:
        """The Timeline: one flat log of what happened, to whom.

        Its own endpoint, not a field on the problem read — the detail
        poll runs every few seconds and this is history, which only
        changes when something happens and which nobody is looking at
        unless the tab is open."""
        with _ro(workspace) as conn:
            known = conn.execute(
                "SELECT 1 FROM problems WHERE name = ?",
                (problem,)).fetchone()
            if known is None:
                raise HTTPException(status_code=404,
                                    detail="unknown problem")
            return _data.problem_events(conn, problem)

    @app.get("/api/problems/{problem}/intent")
    def intent_get(problem: str) -> dict:
        """The problem's intent as the UI works with it (v40): the
        charter (goal), the user's word (standing directives), the
        machine settings, plus whether a strategist amend is pending
        (charter edits are locked then — the two writes would race)."""
        from ..state import intent as _intent
        from ..state import settings as _settings
        if not (workspace / "asterism.db").exists():
            raise HTTPException(status_code=404, detail="no DB yet")
        with _ro(workspace) as conn:
            pintent = _intent.read(conn, problem)
            if pintent is None:
                raise HTTPException(status_code=404,
                                    detail=f"unknown problem {problem!r}")
            merged = {
                "axioms_whitelist": list(pintent.axioms_whitelist),
                "forbidden_lemmas": list(pintent.forbidden_lemmas),
                "library": bool(pintent.library),
            }
            merged.update(_settings.read(conn, problem))
            row = conn.execute(
                "SELECT 1 FROM strategist_decisions WHERE problem = ?"
                "   AND decision_kind = 'RequestUserAmend'"
                "   AND outcome = 'awaiting_human' LIMIT 1",
                (problem,)).fetchone()
            pending = row is not None
        return {
            "problem": problem,
            "charter": pintent.charter,
            "word": pintent.word,
            "settings": merged,
            "pending_amend": pending,
        }

    @app.post("/api/problems/{problem}/intent")
    def intent_update(problem: str, body: IntentUpdateBody) -> dict:
        from ..state import intent as _intent
        conn0 = db.connect(workspace / "asterism.db")
        try:
            if body.charter is not None:
                row = conn0.execute(
                    "SELECT 1 FROM strategist_decisions WHERE problem = ?"
                    "   AND decision_kind = 'RequestUserAmend'"
                    "   AND outcome = 'awaiting_human' LIMIT 1",
                    (problem,)).fetchone()
                if row is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="a strategist amend is pending on this"
                               " problem — resolve it in the Inbox first")
                try:
                    _intent.set_charter(conn0, problem, body.charter)
                except ValueError as e:
                    raise HTTPException(status_code=422,
                                        detail=str(e)) from e
            if body.word is not None:
                try:
                    _intent.set_word(conn0, problem, body.word)
                except ValueError as e:
                    raise HTTPException(status_code=422,
                                        detail=str(e)) from e
        finally:
            conn0.close()
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
                # The axiom gate is FIXED AT CREATION: the gate re-reads
                # it per validation, so a mid-life edit would re-tune
                # soundness under live (and past) proofs — the one
                # genuinely dangerous knob. Enforced here, not just
                # hidden in the UI.
                current = {
                    "axioms_whitelist": [], "library": False}
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
                d["signoff"] = _data.signoff_with_seal(conn, problem)
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

    @app.post("/api/papers/upload")
    async def paper_upload(request: Request, filename: str) -> dict:
        """Shelve a document dropped or picked in the browser. The body
        is the RAW file bytes (no multipart — keeps the install free of
        a parser dependency); the source filename rides the query
        string. Content-hash identity: re-dropping the same document is
        a no-op returning the existing slot, and `already_shelved`
        tells the UI which happened."""
        import tempfile
        from ..papers import shelf as _shelf
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
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{name}: {len(data) // 2**20}MB exceeds the "
                       f"{_MAX_UPLOAD_BYTES // 2**20}MB upload cap")
        already = _shelf.load_meta(workspace,
                                   _shelf.content_id(data)) is not None
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / name
            tmp.write_bytes(data)
            try:
                meta = _shelf.add_paper(workspace, tmp, added_by="user")
            except (_shelf.ScannedPdfError, ValueError) as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
        return {"id": meta.id, "source_name": meta.source_name,
                "pages": meta.pages, "chars": meta.chars,
                "already_shelved": already}

    @app.post("/api/papers/{pid}/rename")
    def paper_rename(pid: str, body: PaperRenameBody) -> dict:
        """Set the display title (empty clears back to the filename).
        Display metadata only — identity, text and bindings untouched."""
        from ..papers import shelf as _shelf
        meta = _shelf.set_title(workspace, pid, body.title)
        if meta is None:
            raise HTTPException(status_code=404,
                                detail=f"paper {pid!r} not shelved here")
        return {"id": meta.id, "title": meta.title,
                "source_name": meta.source_name}

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
            if d is not None:
                # the chapter header names its signer - the trust
                # record travels with the reading surface (v27)
                d["signoff"] = _data.signoff_with_seal(conn, problem)
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
        code = _cli.cmd_approve_ingest(argparse.Namespace(
            problem=problem,
            signer=None if body is None else body.signer))
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
        """Author a new problem from the UI: write the problem.json
        seed (+ optional Defs.lean / Root.lean), then run the same init
        chokepoint the CLI uses. Pure-NL creation is instant; a
        Defs/Root submission type-checks first (lake build — minutes).
        On init failure the created directory is rolled back so the
        form can be corrected and resubmitted."""
        import json as _json
        import re as _re
        import shutil as _shutil
        from ..core.cli import init_problem
        from ..state import intent as _intent
        name = body.name.strip()
        if not _re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*", name)                 or len(name) > 120:
            raise HTTPException(
                status_code=422,
                detail="problem name must be dot-separated identifiers, "
                       "e.g. Topology.my_theorem")
        charter = str(body.charter or "").strip()
        if not charter:
            raise HTTPException(status_code=422,
                                detail="the charter (the problem's goal) "
                                       "must not be empty")
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

    @app.post("/api/models/refresh")
    def models_refresh() -> dict:
        """Ask every backend that can be asked what it currently runs.

        An action, not a poll — it spawns (agy's listing is ~2.5s) and
        the settings page reads it once on mount. Worth doing: agy's
        live list was 14 models on gemini-3.7 while the list kept here
        still said gemini-3.6, so a picker without this offers names
        that have moved on.
        """
        return {"groups": _model_groups(workspace, probe=True)}

    @app.get("/api/config")
    def config_get() -> dict:
        from ..core import config as _cfg
        rows = _cfg.ui_settings(workspace)
        # the model picker's options, grouped by the backend that runs
        # them — one control decides both, so they cannot disagree
        groups = _model_groups(workspace)
        for r in rows:
            if str(r["key"]).endswith(".model"):
                r["groups"] = groups
        return {"settings": rows}

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

    @app.post("/api/problems/{problem}/delete")
    def delete_problem_ep(problem: str) -> dict:
        """Destruction tier (owner): the UI gates this behind a
        type-the-name confirm; the REAL guards (bridged refuses,
        engine-busy refuses) live in the chokepoint."""
        from ..core.cli import delete_problem
        rc, msg = delete_problem(workspace, problem)
        if rc == 1:
            raise HTTPException(status_code=404, detail=msg)
        if rc in (2, 3):
            raise HTTPException(status_code=409, detail=msg)
        if rc != 0:
            raise HTTPException(status_code=500, detail=msg)
        return {"deleted": problem}

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

    @app.get("/api/shutdown/preview")
    def shutdown_preview() -> dict:
        """What "quit Asterism" would actually stop, measured now.

        Three processes, and the third is the surprise: the Lean gateway
        is spawned with CREATE_BREAKAWAY_FROM_JOB and has no atexit kill
        because it must OUTLIVE daemon restarts (warming Mathlib costs
        minutes — `lsp/lifecycle.py`). Nothing in the product ever ends
        it, so closing the browser leaves it resident holding its
        toolchain. That is the gap this endpoint exists for; the page
        must be able to name it before it acts.
        """
        from ..core.cli import daemon_status
        d = daemon_status(workspace)
        return {
            "daemon": {"running": bool(d.get("running")),
                       "scope": d.get("scope"),
                       "in_flight": int(d.get("in_flight_leases") or 0)},
            "gateway": {"phase": d.get("gateway")},
            "console": {"pid": os.getpid()},
        }

    @app.post("/api/shutdown")
    def shutdown(body: ShutdownBody) -> dict:
        """Stop everything, in the order that keeps the answer readable.

        The engine first (it is the thing with work in flight), the
        gateway next (it outlives the engine by design), and this
        process LAST — a console that killed itself first could not
        report what happened to the other two.

        Draining is the daemon's own graceful stop and can take as long
        as a spawn (minutes), so this does not wait on it: a live engine
        is a 409 telling the reader to stop the run first, exactly like
        `daemon_stop`'s own contract. Only `force` abandons work.
        """
        import threading
        from ..core.cli import daemon_status, daemon_stop
        stopped: "list[str]" = []
        d = daemon_status(workspace)
        if d.get("running"):
            if not body.force:
                raise HTTPException(
                    status_code=409,
                    detail=(f"the engine is still running"
                            f"{' on ' + str(d.get('scope')) if d.get('scope') else ''}"
                            f" with {int(d.get('in_flight_leases') or 0)} agent(s)"
                            f" in flight — stop the run first, or force"))
            code, msg = daemon_stop(workspace, force=True)
            if code != 0:
                raise HTTPException(status_code=500, detail=msg)
            stopped.append("engine")

        # The gateway answers /health on its own port; its pid comes from
        # there, and the existing helper waits for the port to actually
        # free rather than trusting one missed ping.
        try:
            from ..lsp import lifecycle as _gw
            h = _gw._ping_health(timeout=1.0)
            if h and h.get("pid"):
                _gw._kill_stale_gateway(h["pid"])
                stopped.append("Lean gateway")
        except Exception as e:  # noqa: BLE001 — never block the exit
            print(f"[shutdown] gateway stop: {e}", flush=True)

        stopped.append("console")
        _schedule_process_exit()
        return {"stopped": stopped}

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
