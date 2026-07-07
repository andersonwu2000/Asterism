"""The setup wizard's backend — /api/setup/*.

The bootstrap (installer/install.bat) does the least it can: Python,
the engine, a browser. Everything long or decision-shaped lands here,
in the browser, with progress and retries: the Lean toolchain (install
via elan — onto a drive the user picks — or point at an existing
installation), the multi-GB Mathlib cache, Claude Code. Owner's calls:
browser wizard over a native one; detect an existing Lean rather than
installing a second; Windows first.

Design notes
- Read status is cheap and side-effect free; mutations are explicit
  POSTs. Long work runs as named async jobs (the review-refresh
  pattern) with a live log tail the UI polls.
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
    has the package dir but an empty build tree)."""
    build = (workspace / ".lake" / "packages" / "mathlib" / ".lake"
             / "build" / "lib")
    present = False
    if build.exists():
        # any olean at all is a fetched cache; counting all ~5k files
        # per poll would be rude
        for p in build.rglob("*.olean"):
            present = True
            break
    return {"present": present}


def claude_status() -> dict:
    from .app import _creds_path
    return {"installed": shutil.which("claude") is not None,
            "logged_in": _creds_path().exists()}


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


def _start_job(name: str, worker) -> dict:  # noqa: ANN001
    with _jobs_lock:
        j = _jobs.get(name)
        if j and j["state"] == "running":
            return {"state": "running", "log": list(j["log"])}
        j = {"state": "running", "log": deque(maxlen=40)}
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
    """Run a command, feeding each output line to the job log."""
    from ..core.process_group import no_window_creationflags
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
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
    if directory.lower() in current.lower():
        return
    _persist_user_env("Path", f"{directory};{current}", log)
    # and for THIS process, so status flips without a restart (daemons
    # started from serve inherit this environment)
    os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")


# ---------------------------------------------------------------------
# workers
# ---------------------------------------------------------------------

def _install_lean_worker(elan_home: str):  # noqa: ANN001
    def worker(log) -> int:  # noqa: ANN001
        import urllib.request
        log("downloading elan-init...")
        tmp = Path(os.environ.get("TEMP", ".")) / "elan-init.ps1"
        urllib.request.urlretrieve(
            "https://elan.lean-lang.org/elan-init.ps1", tmp)
        env = dict(os.environ)
        env["ELAN_HOME"] = elan_home
        log(f"installing the Lean toolchain into {elan_home} ...")
        rc = _stream(["powershell", "-NoProfile", "-ExecutionPolicy",
                      "Bypass", "-File", str(tmp), "-y"], log, env=env)
        if rc != 0:
            return rc
        bin_dir = str(Path(elan_home) / "bin")
        _persist_user_env("ELAN_HOME", elan_home, log)
        _prepend_user_path(bin_dir, log)
        log("Lean toolchain installed")
        return 0
    return worker


def _fetch_mathlib_worker(workspace: Path):
    def worker(log) -> int:  # noqa: ANN001
        log("fetching the prebuilt math library (several GB on the"
            " first run; incremental after that)...")
        rc = _stream(["lake", "exe", "cache", "get"], log, cwd=workspace)
        log("done" if rc == 0 else f"lake exited {rc}")
        return rc
    return worker


def _install_claude_worker():
    def worker(log) -> int:  # noqa: ANN001
        # official native installer first; npm as the fallback
        log("installing Claude Code (official installer)...")
        rc = _stream(["powershell", "-NoProfile", "-Command",
                      "irm https://claude.ai/install.ps1 | iex"], log)
        if rc == 0 and shutil.which("claude"):
            return 0
        if shutil.which("npm"):
            log("native installer unavailable - trying npm...")
            return _stream(["npm", "install", "-g",
                            "@anthropic-ai/claude-code"], log)
        log("could not install automatically - see docs.claude.com for"
            " the manual install, then re-check")
        return 1
    return worker


# ---------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------

class LakePathBody(BaseModel):
    path: str


class InstallLeanBody(BaseModel):
    elan_home: str | None = None


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
        p = Path(body.path).expanduser()
        exe = p if p.is_file() else \
            p / ("lake.exe" if os.name == "nt" else "lake")
        if not exe.exists():
            raise HTTPException(status_code=422,
                                detail=f"no lake at {exe}")
        version = _run_version(str(exe), ["--version"])
        if version is None:
            raise HTTPException(
                status_code=422,
                detail=f"{exe} exists but `lake --version` failed")
        _prepend_user_path(str(exe.parent), lambda _line: None)
        return {"ok": True, "version": version,
                "path": str(exe)}

    @app.post("/api/setup/install-lean")
    def setup_install_lean(body: "InstallLeanBody | None" = None) -> dict:
        if sys.platform != "win32":
            raise HTTPException(
                status_code=409,
                detail="the wizard installs Lean on Windows only for"
                       " now — run installer/install.sh")
        home = (body.elan_home if body and body.elan_home
                else default_elan_home())
        return _start_job("lean", _install_lean_worker(home))

    @app.post("/api/setup/fetch-mathlib")
    def setup_fetch_mathlib() -> dict:
        if not lake_status()["found"]:
            raise HTTPException(status_code=409,
                                detail="install Lean first")
        return _start_job("mathlib", _fetch_mathlib_worker(workspace))

    @app.post("/api/setup/install-claude")
    def setup_install_claude() -> dict:
        if sys.platform != "win32":
            raise HTTPException(
                status_code=409,
                detail="the wizard installs Claude Code on Windows only"
                       " for now — see installer/install.sh")
        return _start_job("claude", _install_claude_worker())
