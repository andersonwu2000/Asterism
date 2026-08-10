"""The sandbox venv: build it, and re-prove its isolation every startup.

The isolation claim is "a separate interpreter that cannot see this
framework". That is a fact about a directory on disk, and directories
drift: the base interpreter gets upgraded and a Windows venv stops
working, numpy gets removed, someone helpfully `pip install -e .`s the
project into it. So the claim is not made once at design time — it is
re-checked, and the last two checks ARE the definition of the isolation:

    import Tooling  -> must FAIL
    import numpy    -> must SUCCEED

Same shape as the provider drift guard: a declaration that nobody
re-measures is a declaration that decays into a wish.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

#: Under `.asterism/` (gitignored runtime state), beside the other
#: things the framework builds for itself.
_VENV_DIRNAME = "compute-venv"
_PROBE_TIMEOUT = 60


def _workspace() -> Path:
    return Path(__file__).resolve().parents[2]


def venv_dir() -> Path:
    return _workspace() / ".asterism" / _VENV_DIRNAME


def sandbox_python() -> Path:
    d = venv_dir()
    return (d / "Scripts" / "python.exe" if sys.platform == "win32"
            else d / "bin" / "python")


def _neutral_cwd() -> str:
    """Somewhere that is not the repo.

    The isolation rests on TWO things, and the first version of this file
    only wrote down one. A separate venv keeps the framework off
    `sys.path`… except that `python -c` puts the CURRENT DIRECTORY on it
    as `sys.path[0]`, so a probe run from the repo root imports `Tooling`
    straight off the disk and the check fails for a reason that has
    nothing to do with the venv. (Caught by this module's own gate on
    first run, 2026-08-10.) `sandbox.run` already gives the child a
    throwaway temp cwd; the probes must match it or they are not
    measuring the thing that will actually happen."""
    import tempfile
    return tempfile.gettempdir()


def _run(argv: "list[str]", timeout: int = _PROBE_TIMEOUT
         ) -> "tuple[int, str]":
    from ..core.process_group import no_window_creationflags
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=_neutral_cwd(),
                           creationflags=no_window_creationflags())
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def verify() -> "tuple[bool, str]":
    """Four assertions. The last two are the isolation itself."""
    py = sandbox_python()
    if not py.is_file():
        return False, f"no sandbox interpreter at {py}"
    rc, out = _run([str(py), "-c", "print('alive')"])
    if rc != 0 or "alive" not in out:
        return False, (f"sandbox interpreter will not start (base Python "
                       f"upgraded under it?): {out.strip()[:200]}")
    # THE isolation check. Not "PYTHONPATH is unset" — that proves
    # nothing, because an editable install reaches the interpreter
    # through site-packages instead (measured 2026-08-10).
    rc, out = _run([str(py), "-c", "import Tooling"])
    if rc == 0:
        return False, ("ISOLATION BROKEN: the sandbox can import Tooling, "
                       "which reaches the run database. Was the project "
                       "pip-installed into the sandbox venv?")
    rc, out = _run([str(py), "-c", "import numpy"])
    if rc != 0:
        return False, "numpy missing from the sandbox venv"
    return True, ""


def create() -> "tuple[bool, str]":
    """Build it. Deliberately a framework job, not an installer step: the
    sandbox is an engine dependency, so a dev machine and a user machine
    get the same one without anyone remembering a checkbox."""
    d = venv_dir()
    d.parent.mkdir(parents=True, exist_ok=True)
    rc, out = _run([sys.executable, "-m", "venv", str(d)], timeout=300)
    if rc != 0:
        return False, f"venv creation failed: {out.strip()[:300]}"
    rc, out = _run([str(sandbox_python()), "-m", "pip", "install", "-q",
                    "numpy"], timeout=600)
    if rc != 0:
        return False, f"numpy install failed: {out.strip()[:300]}"
    return verify()


def ensure_ready() -> "tuple[bool, str]":
    """Verify, and build once if it is simply not there yet.

    A BROKEN sandbox is not silently rebuilt: `verify` failing on a venv
    that exists means something changed underneath (a base upgrade, or
    the project installed into it), and rebuilding would erase the
    evidence. Report it and let the operator look."""
    py = sandbox_python()
    if not py.is_file():
        return create()
    return verify()
