"""A spawn the framework killed must not wear the vendor's exit code.

`request_shutdown` kills every live subprocess to unblock the pool, and
until 2026-08-15 the corpse came back with whatever the OS gave it: on
codex a SILENT rc=1 with an empty stderr, which reads exactly like a CLI
that failed on its own. The pre-spawn gate already answered SHUTDOWN for
a spawn that never started, so the SAME event wore two labels depending
only on which side of the start the kill landed on — measured across the
provider_probe legs, where teardown takes the last pipeline's feedback
turn every time: rc=129 once, rc=1 twice.

The registry is shared (codex and agy register into `claude_cli`'s own
set), so the fix and this test cover every backend, and the dispatcher's
log line no longer calls a codex process "claude".
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from Tooling.llm import claude_cli, codex_cli
from Tooling.llm.base import SpawnRC

ROOT = Path(__file__).resolve().parents[1]


def _fn_src(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return ast.get_source_segment(
                path.read_text(encoding="utf-8"), node) or ""
    raise AssertionError(f"{path.name}: no {name!r}")


@pytest.mark.parametrize("path,fn", [
    (ROOT / "Tooling" / "llm" / "claude_cli.py", "_run_proc"),
    (ROOT / "Tooling" / "llm" / "codex_cli.py", "_classify"),
])
def test_a_killed_spawn_is_reported_as_shutdown(path, fn) -> None:
    src = _fn_src(path, fn)
    assert "is_shutdown_requested()" in src, (
        f"{path.name}::{fn} must ask, AFTER the wait, whether the "
        f"framework is the one that killed this process — otherwise our "
        f"own teardown is indistinguishable from a vendor failure")
    assert "SpawnRC.SHUTDOWN" in src
    # …and the name must RESOLVE there. The first cut of this fix put
    # the check in codex's `_classify` and the import in `_run_proc`,
    # which would have raised NameError on the one path no unit test
    # exercises: a real teardown. Resolvable = the module defines it
    # (claude_cli does) or this function imports it (codex must).
    defines_it = "def is_shutdown_requested(" in path.read_text(
        encoding="utf-8")
    imports_it = any("is_shutdown_requested" in line and "import" in line
                     for line in src.splitlines())
    assert defines_it or imports_it, (
        f"{path.name}::{fn} uses `is_shutdown_requested` but neither its "
        f"module defines it nor its body imports it — NameError at the "
        f"one moment it is called")


@pytest.mark.parametrize("path,fn", [
    (ROOT / "Tooling" / "llm" / "claude_cli.py", "_run_proc"),
    (ROOT / "Tooling" / "llm" / "codex_cli.py", "_classify"),
])
def test_the_check_is_guarded_on_a_nonzero_rc(path, fn) -> None:
    """A spawn that FINISHED as shutdown fired keeps its success — the
    work is on disk and discarding it would be the more expensive
    mistake."""
    src = _fn_src(path, fn)
    assert "rc != 0 and is_shutdown_requested()" in src


@pytest.mark.parametrize("path,fn", [
    (ROOT / "Tooling" / "llm" / "codex_cli.py", "_classify"),
])
def test_the_check_precedes_the_marker_tables(path, fn) -> None:
    """A half-written buffer that happens to carry the word "quota"
    must not let our own kill be read as an exhausted window — that
    would put a real backoff on a framework-initiated teardown."""
    src = _fn_src(path, fn)
    assert (src.index("rc != 0 and is_shutdown_requested()")
            < src.index("_QUOTA_MARKERS"))


def test_the_live_process_registry_is_shared_by_every_provider() -> None:
    """The reason the fix belongs in both places and the log line may
    not say "claude": codex registers into the same set."""
    assert codex_cli.CodexCliProvider is not None
    src = (ROOT / "Tooling" / "llm" / "codex_cli.py").read_text("utf-8")
    assert "_live_procs" in src and "from .claude_cli import" in src
    assert hasattr(claude_cli, "_live_procs")


def test_no_shutdown_message_calls_an_arbitrary_backend_claude() -> None:
    """It killed a codex process and said "claude" — which is how the
    label was noticed at all (08-15)."""
    for rel in ("Tooling/core/dispatcher.py", "Tooling/core/cli.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "in-flight claude " not in text, (
            f"{rel}: the kill reaches every provider, so the message "
            f"must not name one")


def test_shutdown_rc_is_the_declared_one() -> None:
    assert SpawnRC.SHUTDOWN == 129
