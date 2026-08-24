"""Oracle ARM64 readiness P0#2 — POSIX process-group lifecycle for LLM
spawns.

Off-Windows, `kill_proc_tree` used to fall straight to bare
`proc.kill()` — TerminateProcess-equivalent on the DIRECT CHILD only.
For `claude`/`codex` (npm-installed CLIs whose real agent process sits
two levels below the shim) that reaps the wrong process and leaves the
agent running (see `tests/test_a_killed_spawn_is_actually_dead.py` for
the Windows half of the same bug and its Job Object fix). This suite
covers the POSIX fix: every LLM spawn gets its own session/process
group (`start_new_session=True`), and `kill_proc_tree` on POSIX does
SIGTERM the group -> bounded grace -> SIGKILL the group, falling back
to `proc.kill()` only when the group can't be resolved or every signal
call fails.

Runs on Windows CI (per repo convention): the POSIX branch is reached
by monkeypatching `os.name` plus the POSIX-only `os` entry points
(`getpgid`, `killpg`) that don't exist on this platform at all —
`raising=False` on those `setattr` calls is required for that reason,
not a laxness.
"""
from __future__ import annotations

import signal
from pathlib import Path

import pytest

from Tooling.llm import claude_cli

ROOT = Path(__file__).resolve().parents[1]
SPAWN_SITES = [ROOT / "Tooling" / "llm" / "claude_cli.py",
               ROOT / "Tooling" / "llm" / "codex_cli.py"]


class _FakeProc:
    """Stands in for `subprocess.Popen` in these tests: `.pid` is
    fixed, `.poll()`/`.kill()` are scriptable, no real process."""

    def __init__(self, pid: int = 4242):
        self.pid = pid
        self.poll_results: "list[object]" = []
        self.kill_calls = 0

    def poll(self):
        if self.poll_results:
            return self.poll_results.pop(0)
        return None

    def kill(self):
        self.kill_calls += 1


# ---------------------------------------------------------------------
# Spawn sites: own session/process group on POSIX
# ---------------------------------------------------------------------

@pytest.mark.parametrize("path", SPAWN_SITES, ids=lambda p: p.name)
def test_llm_spawns_get_their_own_posix_session(path) -> None:
    """`start_new_session=True` (gated on `os.name != "nt"`) must reach
    the spawn's `subprocess.Popen` call — without it, `killpg` in
    `kill_proc_tree` has no process group to target and silently falls
    back to the single-process kill this whole item exists to fix."""
    src = path.read_text(encoding="utf-8")
    assert 'popen_kwargs["start_new_session"] = True' in src
    assert '**popen_kwargs' in src


# ---------------------------------------------------------------------
# kill_proc_tree POSIX branch
# ---------------------------------------------------------------------

def test_kill_proc_tree_dispatches_to_the_posix_group_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})
    monkeypatch.setattr(claude_cli.os, "name", "posix")
    called: list = []
    monkeypatch.setattr(claude_cli, "_kill_proc_group_posix",
                        lambda proc: called.append(proc) or True)
    proc = _FakeProc()
    assert claude_cli.kill_proc_tree(proc) is True
    assert called == [proc]


def test_windows_path_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows keeps the bare `proc.kill()` fallback exactly as before
    — this item must not touch the win32 branch at all."""
    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})
    monkeypatch.setattr(claude_cli.os, "name", "nt")
    proc = _FakeProc()
    assert claude_cli.kill_proc_tree(proc) is True
    assert proc.kill_calls == 1


def test_posix_term_then_grace_then_kill_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The process never exits on its own: SIGTERM must be sent to the
    GROUP first, then (after the grace window) SIGKILL to the same
    group — never the reverse, and never a bare `proc.kill()` while the
    group calls are succeeding."""
    calls: list = []
    monkeypatch.setattr(claude_cli.os, "getpgid",
                        lambda pid: 9999, raising=False)
    monkeypatch.setattr(claude_cli.os, "killpg",
                        lambda pgid, sig: calls.append((pgid, sig)),
                        raising=False)
    proc = _FakeProc()  # poll() always returns None: never exits
    # grace_sec=0.0 so the bounded wait costs no real time in the suite
    # (deadline == "now"; the loop condition is false on first check).
    assert claude_cli._kill_proc_group_posix(proc, grace_sec=0.0) is True
    # `signal.SIGKILL` does not exist on the Windows build this suite
    # runs on — `claude_cli._SIGKILL` is the module's Windows-safe pin
    # of the POSIX signal number (see its docstring/comment).
    assert calls == [(9999, signal.SIGTERM), (9999, claude_cli._SIGKILL)]
    assert proc.kill_calls == 0  # group calls succeeded — no fallback


def test_posix_exit_during_grace_skips_sigkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A process that dies during the grace window must not also get
    SIGKILL — the wait is there so a cooperative exit is the common
    case, not decoration."""
    calls: list = []
    monkeypatch.setattr(claude_cli.os, "getpgid",
                        lambda pid: 9999, raising=False)
    monkeypatch.setattr(claude_cli.os, "killpg",
                        lambda pgid, sig: calls.append((pgid, sig)),
                        raising=False)
    proc = _FakeProc()
    proc.poll_results = [0]  # already exited by the first grace check
    assert claude_cli._kill_proc_group_posix(proc, grace_sec=5.0) is True
    assert calls == [(9999, signal.SIGTERM)]


def test_posix_unresolvable_group_falls_back_to_bare_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`os.getpgid` raising (process already reaped, or it never got
    its own session) must fall back to `proc.kill()` rather than
    propagate — a shutdown path cannot afford to raise."""
    killpg_calls: list = []
    monkeypatch.setattr(
        claude_cli.os, "getpgid",
        lambda pid: (_ for _ in ()).throw(ProcessLookupError()),
        raising=False)
    monkeypatch.setattr(claude_cli.os, "killpg",
                        lambda pgid, sig: killpg_calls.append((pgid, sig)),
                        raising=False)
    proc = _FakeProc()
    assert claude_cli._kill_proc_group_posix(proc) is True
    assert killpg_calls == []
    assert proc.kill_calls == 1


def test_posix_signal_failures_fall_back_to_bare_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both `killpg` calls raising (the group is already gone) must
    still fall back to `proc.kill()` instead of silently reporting
    success while nothing was actually signaled."""
    monkeypatch.setattr(claude_cli.os, "getpgid",
                        lambda pid: 9999, raising=False)

    def _raise(pgid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(claude_cli.os, "killpg", _raise, raising=False)
    proc = _FakeProc()  # never exits during the (zero-length) grace
    assert claude_cli._kill_proc_group_posix(proc, grace_sec=0.0) is True
    assert proc.kill_calls == 1


def test_posix_branch_only_taken_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`kill_proc_tree` must gate the POSIX helper on `os.name`, not
    call it unconditionally — the win32 dev box must keep exercising
    the Job Object path in production."""
    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})
    monkeypatch.setattr(claude_cli.os, "name", "nt")
    called: list = []
    monkeypatch.setattr(claude_cli, "_kill_proc_group_posix",
                        lambda proc, **kw: called.append(proc) or True)
    proc = _FakeProc()
    claude_cli.kill_proc_tree(proc)
    assert called == []  # POSIX helper must not run on "nt"
