"""The spawn environment is an ALLOWLIST, not an inheritance.

Verified 2026-08-08: a daemon started from inside a Claude Code session
passed CLAUDECODE, CLAUDE_CODE_SESSION_ID, CLAUDE_CODE_ENTRYPOINT,
CLAUDE_CODE_SSE_PORT, CLAUDE_PID and CLAUDE_CODE_CHILD_SESSION into
every spawn, because `spawn_env` inherited everything and the providers
only ever ADDED variables. Nothing broke in thousands of spawns — the
cost was that "started from a clean terminal" and "started from inside
an agent session" were two different, invisible configurations, and
CLAUDE_CODE_SSE_PORT pointed at the host session's server.

The risk of the fix is the mirror image: on Windows, omitting SYSTEMROOT
/ TEMP / APPDATA / PATHEXT / COMSPEC / NUMBER_OF_PROCESSORS breaks
process creation or the CLI in ways that never name themselves. So the
last test here does not reason about it — it RUNS both CLIs under the
constructed environment.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from Tooling.llm.envelope import (
    INHERIT_ALL_ENV, _ALLOWED_ENV_NAMES, spawn_env,
)


_HOST_SESSION_LEAK = (
    "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SSE_PORT", "CLAUDE_PID", "CLAUDE_CODE_CHILD_SESSION",
)


def _base() -> "dict[str, str]":
    """A parent environment shaped like the observed one."""
    env = {k: v for k, v in os.environ.items()}
    for name in _HOST_SESSION_LEAK:
        env[name] = "leaked"
    env["SOME_UNRELATED_TOOL_TOKEN"] = "secret"
    env["ASTERISM_FORMALIZER_MODEL"] = "configured"
    return env


def test_the_host_session_variables_do_not_reach_a_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(INHERIT_ALL_ENV, raising=False)
    env = spawn_env(_base())
    for name in _HOST_SESSION_LEAK:
        assert name not in env, f"{name} still leaks into spawns"


def test_unrelated_parent_variables_are_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocklist rots the moment the vendor adds a variable; the
    allowlist's default answer is 'no'."""
    monkeypatch.delenv(INHERIT_ALL_ENV, raising=False)
    assert "SOME_UNRELATED_TOOL_TOKEN" not in spawn_env(_base())


def test_the_framework_namespace_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ASTERISM_*` is read by `core/config` inside every framework
    child (the `asterism_tools` MCP server and the spawn_guard hook are
    both `python -m Tooling.…`), and `ASTERISM_SPAWN_WRITE_ROOTS` IS the
    write fence. Dropping the prefix would move a configured run onto
    defaults in silence."""
    monkeypatch.delenv(INHERIT_ALL_ENV, raising=False)
    env = spawn_env(_base())
    assert env.get("ASTERISM_FORMALIZER_MODEL") == "configured"


@pytest.mark.parametrize("name", [
    "SYSTEMROOT", "TEMP", "APPDATA", "LOCALAPPDATA", "USERPROFILE",
    "PATHEXT", "COMSPEC", "PROGRAMDATA", "NUMBER_OF_PROCESSORS",
])
def test_windows_process_creation_essentials_are_allowlisted(
    name: str,
) -> None:
    """Named individually because each omission is its own obscure
    failure, and a future tightening of the list must trip a test with
    the variable's name in it rather than a length assertion."""
    assert name in _ALLOWED_ENV_NAMES


def test_windows_env_names_match_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Windows environment block is case-insensitive but
    arbitrarily CASED — `SystemRoot`, `ProgramData` and `COMSPEC` all
    appear as whoever set them typed it. An exact-match filter would
    silently drop them."""
    if os.name != "nt":
        pytest.skip("case folding only applies on Windows")
    monkeypatch.delenv(INHERIT_ALL_ENV, raising=False)
    env = spawn_env({"SystemRoot": "C:/Windows", "ProgramData": "C:/PD",
                     "NotAllowed": "x"})
    assert env.get("SystemRoot") == "C:/Windows"
    assert env.get("ProgramData") == "C:/PD"
    assert "NotAllowed" not in env


def test_path_is_still_prepended_with_this_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The allowlist must not disturb the 2026-08-06 fix: a bare
    `python` in an agent's command has to resolve to the framework's
    interpreter, not to whatever venv the operator's shell had."""
    import sys
    from pathlib import Path
    monkeypatch.delenv(INHERIT_ALL_ENV, raising=False)
    env = spawn_env({"PATH": "C:/somewhere/else"})
    own = str(Path(sys.executable).resolve().parent)
    assert env["PATH"].split(os.pathsep)[0] == own


def test_the_escape_hatch_restores_full_inheritance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Documented in `spawn_env`: set it when a spawn breaks in a way
    that smells environmental and you need to know whether the
    allowlist is the cause before spending an hour elsewhere. The FIX
    is then to add the missing name, not to leave the hatch open."""
    monkeypatch.setenv(INHERIT_ALL_ENV, "1")
    env = spawn_env(_base())
    assert env.get("CLAUDE_CODE_SESSION_ID") == "leaked"
    assert env.get("SOME_UNRELATED_TOOL_TOKEN") == "secret"


def test_agy_home_override_still_lands_after_the_filter() -> None:
    """agy's per-spawn HOME is written AFTER `spawn_env` returns, so the
    filter must not be able to strip it. All four names, because Go's
    os.UserHomeDir reads USERPROFILE on Windows."""
    from pathlib import Path
    from Tooling.llm import antigravity_cli as agy
    home = Path("D:/tmp/spawnhome")
    env = agy._spawn_env(home)
    assert env["HOME"] == str(home)
    assert env["USERPROFILE"] == str(home)
    assert env["HOMEDRIVE"] == home.drive
    assert env["PYTHONPATH"]


# ---------------------------------------------------------------------
# The one that actually matters: does the CLI still launch?
# ---------------------------------------------------------------------

def _agy_exe() -> "str | None":
    from Tooling.llm.antigravity_cli import resolve_agy_executable
    return resolve_agy_executable()


@pytest.mark.free_cli_probe
@pytest.mark.parametrize("resolve", [
    pytest.param(lambda: shutil.which("claude"), id="claude"),
    pytest.param(_agy_exe, id="agy"),
])
def test_the_cli_still_runs_under_the_constructed_environment(
    resolve, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--version` is free — no API call, no quota — and it is the
    cheapest thing that still exercises real process creation, DLL
    loading and the CLI's own startup. A missing SYSTEMROOT or PATHEXT
    fails HERE rather than three hours into a run.

    Skipped where the CLI is not installed (a CI box legitimately has
    neither)."""
    exe = resolve()
    if not exe:
        pytest.skip("CLI not installed on this machine")
    monkeypatch.delenv(INHERIT_ALL_ENV, raising=False)
    r = subprocess.run([exe, "--version"], env=spawn_env(),
                       capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, (
        f"{exe} --version failed under the spawn allowlist: "
        f"rc={r.returncode} stderr={(r.stderr or '')[:400]}")
    assert (r.stdout or "").strip()
