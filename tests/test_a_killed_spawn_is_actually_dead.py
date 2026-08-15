"""`Popen.kill()` does not kill an npm-installed CLI.

On Windows it is `TerminateProcess` on the DIRECT CHILD, and for a CLI
installed by npm that child is `cmd.exe` — the shim — with the agent two
levels below (`cmd.exe → node.exe → <vendor>.exe`). Killing the shim
leaves the agent running.

Measured 2026-08-15 on the union_closed run: a codex spawn killed at
02:32:35 kept reasoning and calling tools until 02:37:33, and at
02:34:35 called the gateway's `withdraw_stub` — deleting a stub file
that the framework was, at that moment, reading as the dead spawn's
salvage. The FileNotFoundError then came back to the agent as
"your Lean failed to build".

So this is not a tidiness bug: a spawn the framework has recorded as
dead goes on mutating the workspace, and the framework attributes what
it finds to whoever comes next. Job Objects reap the whole tree —
membership survives re-parenting, which is why `taskkill /T` was never
enough either (`core/process_group.py`).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from Tooling.core import process_group
from Tooling.llm import claude_cli

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = [ROOT / "Tooling" / "llm" / "claude_cli.py",
             ROOT / "Tooling" / "llm" / "codex_cli.py"]


def test_no_provider_kills_a_spawn_by_the_handle_it_holds() -> None:
    """The enumeration IS the audit: a new provider that calls
    `proc.kill()` on a spawn has to either route through the tree kill
    or delete a line from this list."""
    for path in PROVIDERS:
        src = path.read_text(encoding="utf-8")
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "proc.kill()" in stripped:
                # The one legal site is the fallback INSIDE the tree
                # kill itself.
                assert path.name == "claude_cli.py" and i < 130, (
                    f"{path.name}:{i} kills a spawn by its own handle — "
                    f"on an npm-installed CLI that reaps the `cmd.exe` "
                    f"shim and leaves the agent running. Use "
                    f"`kill_proc_tree`")


@pytest.mark.parametrize("path", PROVIDERS, ids=lambda p: p.name)
def test_every_spawn_is_put_in_a_job(path) -> None:
    src = path.read_text(encoding="utf-8")
    assert "create_capped_job(None)" in src, (
        f"{path.name}: a spawn must be created inside a Job Object — "
        f"`None` asks for a reaper with no memory ceiling")
    assert "assign_to_job(job, proc)" in src


def test_a_job_with_no_memory_cap_is_still_kill_on_close() -> None:
    """`per_process_mb=None` must not silently become a 0-byte limit —
    that would make every allocation in the tree fail instantly. It is
    the flag that has to go, not the number."""
    src = (ROOT / "Tooling" / "core" / "process_group.py").read_text("utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef)
              and n.name == "create_capped_job")
    body = ast.get_source_segment(src, fn) or ""
    assert "if per_process_mb is not None:" in body
    # KILL_ON_JOB_CLOSE is unconditional; the memory flag is not.
    assert "flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in body


def test_the_registry_is_the_one_home_for_killing() -> None:
    """Every provider registers into the same set, so the tree kill
    lives with the set — not copied per provider."""
    assert hasattr(claude_cli, "track_proc")
    assert hasattr(claude_cli, "untrack_proc")
    assert hasattr(claude_cli, "kill_proc_tree")
    codex = (ROOT / "Tooling" / "llm" / "codex_cli.py").read_text("utf-8")
    assert "track_proc(proc, job)" in codex
    assert "untrack_proc(proc)" in codex


def test_shutdown_reaps_trees(monkeypatch: pytest.MonkeyPatch) -> None:
    """`request_shutdown` is the dispatcher's teardown path; it must go
    through the tree kill for every live spawn."""
    reaped: list = []

    class _Proc:
        def kill(self):
            reaped.append("handle-only")

    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})
    p = _Proc()
    claude_cli.track_proc(p, job=None)          # no job (non-Windows path)
    try:
        assert claude_cli.request_shutdown() == 1
    finally:
        claude_cli._reset_shutdown_for_tests()
    # With no job the fallback is the bare handle — correct off-Windows,
    # where the direct child IS the agent.
    assert reaped == ["handle-only"]


def test_terminate_job_is_what_a_tracked_job_uses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list = []
    monkeypatch.setattr(process_group, "terminate_job",
                        lambda job: called.append(job) or True)
    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})

    class _Proc:
        def kill(self):
            called.append("BARE KILL — the tree would have survived")

    p = _Proc()
    claude_cli.track_proc(p, job="job-handle")
    claude_cli.kill_proc_tree(p)
    assert called == ["job-handle"]
