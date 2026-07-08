"""The setup wizard's backend — /api/setup/*.

The bootstrap (installer/install.ps1, fronted by "Setup Asterism.exe")
does the least it can: Python, the engine, a browser. Everything long
or decision-shaped lands here, in the browser: the Lean toolchain
(install via elan — onto a drive the user picks — or point at an
existing installation), the multi-GB Mathlib cache, Claude Code.
Owner's calls: browser wizard over a native one; detect an existing
Lean rather than installing a second; Windows first; decisions are
collected UP FRONT and the whole install runs unattended after one
click, so nothing waits on a user who walked away.

Design notes
- Read status is cheap and side-effect free; mutations are explicit
  POSTs. Long work runs as named async jobs (the review-refresh
  pattern) with a live log tail the UI polls. The one-click flow is
  the "all" job: Claude Code first (fast, so its login window opens
  while the user is still at the keyboard), then Lean, then Mathlib
  (the long unattended stretch). Each step is skipped when already
  satisfied, so retry = press the same button again.
- PATH/ELAN_HOME persistence uses [Environment]::SetEnvironmentVariable
  (User scope) via PowerShell — `setx` silently truncates PATH at 1024
  chars, which is how installers eat people's PATHs.
- Lives in its own module (run.py precedent): app.py is a co-edited
  hot file.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel


# ---------------------------------------------------------------------
# cheap checks (GET /api/setup/status)
# ---------------------------------------------------------------------

def _run_version(exe: str, args: "list[str]") -> "str | None":
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True,
                           timeout=15, encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip()
        return out.splitlines()[0] if out else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def lake_status() -> dict:
    path = shutil.which("lake")
    version = _run_version("lake", ["--version"]) if path else None
    return {"found": path is not None and version is not None,
            "path": path, "version": version}


def mathlib_status(workspace: Path) -> dict:
    """Present = the olean cache has actually landed (a bare checkout
    has the package dir but an empty build tree) AND the framework's
    own Lean server is built — the engine's contract suite refuses to
    start without its declInfo/axiom-probe RPCs (a fresh machine has
    the cache but not the binary; seen live in a sandbox run)."""
    build = (workspace / ".lake" / "packages" / "mathlib" / ".lake"
             / "build" / "lib")
    present = False
    if build.exists():
        # any olean at all is a fetched cache; counting all ~5k files
        # per poll would be rude
        for p in build.rglob("*.olean"):
            present = True
            break
    server = workspace / ".lake" / "build" / "bin" / (
        "lean-asterism-server.exe" if os.name == "nt"
        else "lean-asterism-server")
    return {"present": present and server.exists()}


def claude_status() -> dict:
    from .app import _creds_path, claude_exe
    return {"installed": claude_exe() is not None,
            "logged_in": _creds_path().exists()}


def git_status() -> dict:
    """The engine records proofs in git and lake fetches Mathlib's
    sources with it — a fresh machine (no dev tools) does not have
    it."""
    return {"found": shutil.which("git") is not None}


def disks() -> "list[dict]":
    import psutil  # already a dependency
    out = []
    for part in psutil.disk_partitions(all=False):
        if "fixed" not in part.opts and os.name == "nt":
            # skip removable/network drives on Windows
            if "rw" not in part.opts:
                continue
        try:
            u = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        out.append({"mount": part.mountpoint,
                    "free_gb": round(u.free / 1e9, 1),
                    "total_gb": round(u.total / 1e9, 1)})
    return out


def default_elan_home() -> str:
    return os.environ.get("ELAN_HOME") or str(Path.home() / ".elan")


# ---------------------------------------------------------------------
# named async jobs with a live log tail
# ---------------------------------------------------------------------

_jobs: "dict[str, dict]" = {}
_jobs_lock = threading.Lock()


def _job_state(name: str) -> dict:
    with _jobs_lock:
        j = _jobs.get(name)
        if j is None:
            return {"state": "idle", "log": []}
        return {"state": j["state"], "log": list(j["log"]),
                "rc": j.get("rc")}


def _start_job(name: str, worker, log_maxlen: int = 40) -> dict:  # noqa: ANN001
    with _jobs_lock:
        j = _jobs.get(name)
        if j and j["state"] == "running":
            return {"state": "running", "log": list(j["log"])}
        j = {"state": "running", "log": deque(maxlen=log_maxlen)}
        _jobs[name] = j

    def run() -> None:
        try:
            rc = worker(lambda line: j["log"].append(line))
            j["rc"] = rc
            j["state"] = "done" if rc == 0 else "failed"
        except Exception as e:  # noqa: BLE001 — job state, not a crash
            j["log"].append(f"error: {e}")
            j["state"] = "failed"

    threading.Thread(target=run, daemon=True,
                     name=f"setup-{name}").start()
    return {"state": "running", "log": []}


def _stream(cmd: "list[str]", log, cwd: "Path | None" = None,  # noqa: ANN001
            env: "dict | None" = None) -> int:
    """Run a command, feeding each output line to the job log.

    Decoding: console tools write the OEM codepage when piped (winget
    on a zh-TW Windows writes cp950, whose TRAIL bytes land in ASCII
    letters — decoded as utf-8 that turns into a??c?. mojibake, seen
    live in a sandbox run). The 'oem' codec exists on Windows only;
    ASCII-only output (elan, the claude installer) decodes the same
    under both."""
    from ..core.process_group import no_window_creationflags
    # stdin is CLOSED: a tool that stops to ask a question must fail
    # fast (EOF) and show up in the log, never hang the job forever —
    # elan-init's menu did exactly that when its flag was misspelled
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True,
        encoding="oem" if os.name == "nt" else "utf-8",
        errors="replace", creationflags=no_window_creationflags())
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    return proc.wait()


def _persist_user_env(name: str, value: str, log) -> None:  # noqa: ANN001
    """User-scope env var, the non-destructive way (setx truncates
    PATH at 1024 chars)."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"[Environment]::SetEnvironmentVariable('{name}', "
         f"'{value}', 'User')"],
        capture_output=True, timeout=30)
    log(f"persisted {name} for your account")


def _prepend_user_path(directory: str, log) -> None:  # noqa: ANN001
    current = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "[Environment]::GetEnvironmentVariable('Path', 'User')"],
        capture_output=True, text=True, timeout=30,
        encoding="utf-8", errors="replace").stdout.strip()
    if directory.lower() not in current.lower():
        _persist_user_env("Path", f"{directory};{current}", log)
    # ALWAYS repair THIS process too, even when the registry already
    # has the entry — an earlier (failed) run may have persisted it
    # while this process still cannot see the tool; skipping here left
    # `lake` invisible until a restart (seen live in a sandbox run)
    if directory.lower() not in os.environ.get("PATH", "").lower():
        os.environ["PATH"] = directory + os.pathsep + \
            os.environ.get("PATH", "")


# ---------------------------------------------------------------------
# workers
# ---------------------------------------------------------------------

def _download(url: str, dest: Path, log) -> int:  # noqa: ANN001
    """Download via PowerShell (SChannel), NOT urllib: a fresh
    Windows populates its root-CA store lazily on first use, which
    SChannel triggers and OpenSSL-backed Python does not — urllib
    dies with CERTIFICATE_VERIFY_FAILED on exactly the machines this
    wizard exists for (seen live in a Windows Sandbox)."""
    return _stream(
        ["powershell", "-NoProfile", "-Command",
         "$ProgressPreference='SilentlyContinue';"
         "[Net.ServicePointManager]::SecurityProtocol="
         "[Net.SecurityProtocolType]::Tls12;"
         f"Invoke-WebRequest -UseBasicParsing -Uri '{url}'"
         f" -OutFile '{dest}'"], log)


def _step_install_lean(elan_home: str, log) -> int:  # noqa: ANN001
    log("downloading elan-init...")
    tmp = Path(os.environ.get("TEMP", ".")) / "elan-init.ps1"
    rc = _download("https://elan.lean-lang.org/elan-init.ps1", tmp, log)
    if rc != 0 or not tmp.exists():
        log("could not download elan-init")
        return rc or 1
    env = dict(os.environ)
    env["ELAN_HOME"] = elan_home
    log(f"installing the Lean toolchain into {elan_home} ...")
    # the official script's flag is -NoPrompt (there is no -y), and
    # it is [bool]-typed — `-File` passes strings only, which PS
    # refuses to coerce, so invoke via -Command to pass a real $true;
    # the repo's lean-toolchain file pins the actual toolchain later
    rc = _stream(["powershell", "-NoProfile", "-ExecutionPolicy",
                  "Bypass", "-Command",
                  f"& '{tmp}' -NoPrompt $true"], log, env=env)
    if rc != 0:
        return rc
    bin_dir = Path(elan_home) / "bin"
    # trust the WORLD, not the script's exit code (a wrapper exits 0
    # even when the installer under it was killed mid-menu)
    if not (bin_dir / ("lake.exe" if os.name == "nt"
                       else "lake")).exists():
        log(f"elan-init exited cleanly but no lake landed in {bin_dir}"
            " - see the lines above")
        return 1
    _persist_user_env("ELAN_HOME", elan_home, log)
    _prepend_user_path(str(bin_dir), log)
    log("Lean toolchain installed")
    return 0


def _step_fetch_mathlib(workspace: Path, log) -> int:  # noqa: ANN001
    log("fetching the prebuilt math library (several GB on the"
        " first run; incremental after that)...")
    rc = _stream(["lake", "exe", "cache", "get"], log, cwd=workspace)
    if rc != 0:
        log(f"lake exited {rc}")
        return rc
    # the engine talks to Lean through its own server (declInfo /
    # axiom probes); without this build the contract suite rightly
    # refuses to start the daemon
    log("building the engine's Lean server (a few minutes)...")
    rc = _stream(["lake", "build", "lean-asterism-server"], log,
                 cwd=workspace)
    log("done" if rc == 0 else f"lake exited {rc}")
    return rc


def _step_install_claude(log) -> int:  # noqa: ANN001
    from .app import claude_exe

    def _repair_path() -> None:
        # the official installer's own PATH edit lands in NEW
        # sessions (and can miss entirely on a fresh Windows) — put
        # the CLI's home on PATH ourselves so this serve, its daemon
        # spawns, and the login window all find a bare `claude`
        exe = claude_exe()
        if exe and shutil.which("claude") is None:
            _prepend_user_path(str(Path(exe).parent), log)

    # official native installer first; npm as the fallback
    log("installing Claude Code (official installer)...")
    rc = _stream(["powershell", "-NoProfile", "-Command",
                  "irm https://claude.ai/install.ps1 | iex"], log)
    if rc == 0 and claude_exe():
        _repair_path()
        return 0
    if shutil.which("npm"):
        log("native installer unavailable - trying npm...")
        rc = _stream(["npm", "install", "-g",
                      "@anthropic-ai/claude-code"], log)
        if rc == 0 and claude_exe():
            _repair_path()
            return 0
    log("could not install automatically - see docs.claude.com for"
        " the manual install, then re-check")
    return 1


def _step_install_git(log) -> int:  # noqa: ANN001
    log("installing Git (winget)...")
    # pin the community source (matches installer/install.ps1: msstore
    # being unreachable must not turn into an interactive prompt)
    rc = _stream(["winget", "install", "-e", "--id", "Git.Git",
                  "--source", "winget", "--silent",
                  "--accept-package-agreements",
                  "--accept-source-agreements"], log)
    if rc != 0:
        return rc
    # winget's machine-PATH edit lands in new sessions — repair for
    # THIS process so the mathlib fetch right after can spawn git
    for cand in (r"C:\Program Files\Git\cmd",
                 r"C:\Program Files (x86)\Git\cmd"):
        if Path(cand).exists() and shutil.which("git") is None:
            os.environ["PATH"] = cand + os.pathsep + \
                os.environ.get("PATH", "")
    if shutil.which("git") is None:
        log("git installed but not found on PATH - restart Asterism"
            " and press the button again")
        return 1
    log("Git installed")
    return 0


def _setup_all_worker(workspace: Path, elan_home: "str | None"):
    """The one-click flow. Claude Code goes FIRST: it is the quick
    step whose login needs a human, so its window should open while
    the user is still at the keyboard; Lean and the multi-GB Mathlib
    fetch then run unattended. Every step no-ops when already
    satisfied — pressing the button again after a failure only redoes
    what is missing."""
    def worker(log) -> int:  # noqa: ANN001
        failures: "list[str]" = []

        if not claude_status()["installed"]:
            log("— Claude Code —")
            if _step_install_claude(log) != 0:
                failures.append("Claude Code")
        # claude can be installed yet OFF PATH (its installer's PATH
        # edit missing entirely on a fresh Windows) — and the engine
        # spawns agents with the bare name; repair unconditionally,
        # not only on the install-branch
        from .app import claude_exe
        _exe = claude_exe()
        if _exe and shutil.which("claude") is None:
            _prepend_user_path(str(Path(_exe).parent), log)
        st_claude = claude_status()
        if st_claude["installed"] and not st_claude["logged_in"]:
            from .app import spawn_claude_login
            try:
                spawn_claude_login()
                log("a Claude login window just opened - log in there"
                    " whenever you're ready; everything below keeps"
                    " going on its own")
            except OSError:
                log("open a terminal and run `claude` to log in - the"
                    " rest continues on its own")

        if not git_status()["found"]:
            log("— Git —")
            if sys.platform != "win32":
                log("the wizard installs Git on Windows only for now"
                    " - install it with your package manager")
                failures.append("Git")
            elif _step_install_git(log) != 0:
                failures.append("Git")

        if not lake_status()["found"]:
            log("— Lean toolchain —")
            if sys.platform != "win32":
                log("the wizard installs Lean on Windows only for now"
                    " - run installer/install.sh")
                failures.append("Lean")
            elif _step_install_lean(elan_home or default_elan_home(),
                                    log) != 0:
                failures.append("Lean")

        if lake_status()["found"] and \
                not mathlib_status(workspace)["present"]:
            log("— Math library —")
            if _step_fetch_mathlib(workspace, log) != 0:
                failures.append("Mathlib")

        # end-to-end truth check: steps can misreport (an installer
        # exiting 0 after its child died) — re-derive every component
        # from the world before declaring victory
        still_missing = []
        if not claude_status()["installed"]:
            still_missing.append("Claude Code")
        if not git_status()["found"]:
            still_missing.append("Git")
        if not lake_status()["found"]:
            still_missing.append("Lean")
        elif not mathlib_status(workspace)["present"]:
            still_missing.append("Mathlib")
        for name in still_missing:
            if name not in failures:
                failures.append(name)

        if failures:
            log("setup finished with failures: " + ", ".join(failures)
                + " - press the button again to retry just those")
            return 1
        log("all set - only the Claude login needs you, if it still"
            " shows yellow above")
        return 0
    return worker


# ---------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------

class LakePathBody(BaseModel):
    path: str


class InstallLeanBody(BaseModel):
    elan_home: str | None = None


class RunAllBody(BaseModel):
    # lean_mode 'existing' adopts lake_path (validated at POST time,
    # BEFORE the unattended run starts); 'install' uses elan_home
    lean_mode: str = "install"
    elan_home: str | None = None
    lake_path: str | None = None


def _adopt_lake_path(raw: str) -> dict:
    """Validate a user-supplied Lean by RUNNING it, then put it on
    PATH. Shared by the standalone endpoint and the one-click flow."""
    p = Path(raw).expanduser()
    exe = p if p.is_file() else \
        p / ("lake.exe" if os.name == "nt" else "lake")
    if not exe.exists():
        raise HTTPException(status_code=422, detail=f"no lake at {exe}")
    version = _run_version(str(exe), ["--version"])
    if version is None:
        raise HTTPException(
            status_code=422,
            detail=f"{exe} exists but `lake --version` failed")
    _prepend_user_path(str(exe.parent), lambda _line: None)
    return {"ok": True, "version": version, "path": str(exe)}


def register(app, workspace: Path) -> None:  # noqa: ANN001
    @app.get("/api/setup/status")
    def setup_status() -> dict:
        lake = lake_status()
        mathlib = mathlib_status(workspace) if lake["found"] else \
            {"present": False}
        return {
            "repo": str(workspace),
            "platform": sys.platform,
            "lake": lake,
            "mathlib": mathlib,
            "git": git_status(),
            "claude": claude_status(),
            "elan_home": default_elan_home(),
            "disks": disks(),
            # release-download hook (owner: a download link comes
            # later) — null until a release URL exists
            "update": None,
        }

    @app.get("/api/setup/job/{name}")
    def setup_job(name: str) -> dict:
        return _job_state(name)

    @app.post("/api/setup/lake-path")
    def setup_lake_path(body: LakePathBody) -> dict:
        """The user already has Lean: point at it instead of
        installing a second one (owner). Validates by RUNNING it."""
        return _adopt_lake_path(body.path)

    @app.post("/api/setup/run-all")
    def setup_run_all(body: "RunAllBody | None" = None) -> dict:
        """The one-click flow: every decision arrives in this body,
        then the whole install runs unattended (Claude first so its
        login window opens while the user is still around)."""
        b = body or RunAllBody()
        if b.lean_mode == "existing":
            if not b.lake_path:
                raise HTTPException(status_code=422,
                                    detail="lake_path is required for"
                                           " lean_mode=existing")
            _adopt_lake_path(b.lake_path)   # 422s now, not mid-run
        return _start_job(
            "all", _setup_all_worker(workspace, b.elan_home),
            log_maxlen=120)

    @app.post("/api/setup/install-lean")
    def setup_install_lean(body: "InstallLeanBody | None" = None) -> dict:
        if sys.platform != "win32":
            raise HTTPException(
                status_code=409,
                detail="the wizard installs Lean on Windows only for"
                       " now — run installer/install.sh")
        home = (body.elan_home if body and body.elan_home
                else default_elan_home())
        return _start_job(
            "lean", lambda log: _step_install_lean(home, log))

    @app.post("/api/setup/fetch-mathlib")
    def setup_fetch_mathlib() -> dict:
        if not lake_status()["found"]:
            raise HTTPException(status_code=409,
                                detail="install Lean first")
        return _start_job(
            "mathlib", lambda log: _step_fetch_mathlib(workspace, log))

    @app.post("/api/setup/install-claude")
    def setup_install_claude() -> dict:
        if sys.platform != "win32":
            raise HTTPException(
                status_code=409,
                detail="the wizard installs Claude Code on Windows only"
                       " for now — see installer/install.sh")
        return _start_job("claude", _step_install_claude)
