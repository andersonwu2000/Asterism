"""Tests for the daemon kill-on-close Job Object (`core.process_group`).

The behaviour test is the point: a grandchild spawned under a process that bound
itself to the job must be reaped when that process is HARD-killed (no `/T`),
proving the OS reaps the orphan tree without any manual cleanup.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from Tooling.core import process_group

_REPO = Path(__file__).resolve().parents[1]


def test_noop_off_win32(monkeypatch) -> None:
    # Non-Windows: every entry point is a graceful no-op (POSIX daemon would use
    # a process group instead; not needed yet).
    monkeypatch.setattr(process_group, "_assigned", False)
    monkeypatch.setattr(process_group.sys, "platform", "linux")
    assert process_group.assign_self_to_kill_on_close_job() is False
    assert process_group.breakaway_creationflags() == 0


def test_breakaway_flag_gated_on_assignment(monkeypatch) -> None:
    # The breakaway flag is only emitted once we actually hold the job — passing
    # CREATE_BREAKAWAY_FROM_JOB when NOT in a breakaway-ok job fails CreateProcess.
    monkeypatch.setattr(process_group, "_assigned", False)
    assert process_group.should_breakaway() is False
    assert process_group.breakaway_creationflags() == 0
    monkeypatch.setattr(process_group, "_assigned", True)
    assert process_group.should_breakaway() is True
    if sys.platform == "win32":
        assert process_group.breakaway_creationflags() == (
            subprocess.CREATE_BREAKAWAY_FROM_JOB)
    else:
        assert process_group.breakaway_creationflags() == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object is win32-only")
def test_hard_kill_reaps_grandchild(tmp_path) -> None:
    from Tooling.agent import sandbox  # _pid_alive(pid) — os.kill(pid, 0)

    child_py = tmp_path / "jobchild.py"
    child_py.write_text(
        "import sys, subprocess, time\n"
        f"sys.path.insert(0, r'{_REPO}')\n"
        "from Tooling.core import process_group\n"
        "ok = process_group.assign_self_to_kill_on_close_job()\n"
        "gc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print('ASSIGNED=' + str(ok), flush=True)\n"
        "print('GRANDCHILD=' + str(gc.pid), flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8")

    child = subprocess.Popen(
        [sys.executable, str(child_py)], cwd=str(_REPO),
        stdout=subprocess.PIPE, text=True)
    gc_pid = None
    try:
        assigned = child.stdout.readline().strip()           # ASSIGNED=...
        gc_line = child.stdout.readline().strip()             # GRANDCHILD=...
        if assigned != "ASSIGNED=True":
            pytest.skip(f"job assign unsupported here ({assigned})")
        gc_pid = int(gc_line.split("=", 1)[1])
        assert sandbox._pid_alive(gc_pid)                     # grandchild up

        # Hard-kill ONLY the child (no /T): the orphaned grandchild must die
        # because the job's last handle closed with the child.
        subprocess.run(["taskkill", "/F", "/PID", str(child.pid)],
                       capture_output=True)
        for _ in range(100):                                  # ≤10s
            if not sandbox._pid_alive(gc_pid):
                break
            time.sleep(0.1)
        assert not sandbox._pid_alive(gc_pid), (
            "grandchild survived the daemon hard-kill — job did not reap it")
    finally:
        for pid in (gc_pid, child.pid):
            if pid:
                subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"],
                               capture_output=True)
        try:
            child.stdout.close()
        except Exception:  # noqa: BLE001
            pass
