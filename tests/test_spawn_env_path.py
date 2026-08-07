"""Every spawn resolves a bare `python` to the framework's interpreter.

2026-08-06: scholar's `python -m Tooling.papers.fetch` died on
`ModuleNotFoundError: fitz` because the daemon had inherited a shell
PATH with an unrelated venv in front. The agent reported "could not
retrieve the paper" — indistinguishable from a paywall — and two papers
were written off before the environment turned out to be the cause.
"""
import os
import sys
from pathlib import Path

from Tooling.llm.envelope import spawn_env


def test_our_own_interpreter_wins_over_an_inherited_venv():
    env = spawn_env({"PATH": os.pathsep.join(["C:/other/venv/Scripts",
                                              "C:/windows/system32"])})
    first = env["PATH"].split(os.pathsep)[0]
    assert Path(first) == Path(sys.executable).resolve().parent


def test_the_inherited_path_is_kept_behind_it():
    """Prepend, never replace: agy needs powershell reachable, and the
    2026-07-30 attempt to narrow PATH to a shim broke loogle outright."""
    env = spawn_env({"PATH": os.pathsep.join(["C:/other/venv/Scripts",
                                              "C:/windows/system32"])})
    assert "C:/other/venv/Scripts" in env["PATH"]
    assert "C:/windows/system32" in env["PATH"]


def test_applying_it_twice_changes_nothing():
    once = spawn_env({"PATH": "C:/other/venv/Scripts"})
    assert spawn_env(once)["PATH"] == once["PATH"]


def test_an_empty_path_still_gets_the_interpreter():
    env = spawn_env({})
    assert Path(env["PATH"]) == Path(sys.executable).resolve().parent


def test_both_providers_build_their_env_through_it():
    """The whole point is that no provider keeps its own `dict(os.environ)`
    — that is how one of them ends up with the operator's stray venv."""
    for rel in ("Tooling/llm/claude_cli.py", "Tooling/llm/antigravity_cli.py"):
        src = Path(rel).read_text(encoding="utf-8")
        assert "spawn_env()" in src, f"{rel} does not use the shared env"
        assert "env = dict(os.environ)" not in src, (
            f"{rel} still builds a spawn env by hand")
