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


# ---------------------------------------------------------------------
# Memory-capped job for the lake/lean tree (2026-08-08 post-mortem)
# ---------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="Job Objects are win32")
def test_capped_job_fails_oversized_allocation(tmp_path) -> None:
    """The ceiling half of the fix: a member process whose commit
    crosses the per-process cap must fail its allocation instead of
    growing without bound (the runaway lean worker reached 102 GB and
    took the workstation down)."""
    job = process_group.create_capped_job(64)     # 64 MB
    if job is None:
        pytest.skip("capped job unsupported here")
    child = subprocess.Popen(
        [sys.executable, "-c",
         "b = bytearray(300 * 1024 * 1024); print(len(b))"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process_group.assign_to_job(job, child)
        out, _err = child.communicate(timeout=30)
        assert child.returncode != 0, (
            f"300MB allocation under a 64MB cap succeeded: {out!r}")
    finally:
        process_group.terminate_job(job)
        subprocess.run(["taskkill", "/F", "/PID", str(child.pid), "/T"],
                       capture_output=True)


@pytest.mark.skipif(sys.platform != "win32", reason="Job Objects are win32")
def test_capped_job_reaps_reparented_orphan(tmp_path) -> None:
    """The reaper half: a grandchild whose parent already exited is
    invisible to `taskkill /T` (it walks the live parent-child chain),
    which is how one wedged worker outlived 21 backend restarts. Job
    membership survives re-parenting, so `terminate_job` must reap it."""
    from Tooling.agent import sandbox
    job = process_group.create_capped_job(512)
    if job is None:
        pytest.skip("capped job unsupported here")
    # stdin gate: the child spawns its grandchild only after we say go,
    # so assignment to the job deterministically precedes the spawn.
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, subprocess\n"
         "sys.stdin.readline()\n"
         "gc = subprocess.Popen([sys.executable, '-c',"
         " 'import time; time.sleep(60)'])\n"
         "print('GRANDCHILD=' + str(gc.pid), flush=True)\n"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    gc_pid = None
    try:
        assert process_group.assign_to_job(job, child)
        child.stdin.write("go\n")
        child.stdin.flush()
        gc_pid = int(child.stdout.readline().split("=", 1)[1])
        child.wait(timeout=15)          # parent exits; grandchild orphaned
        assert sandbox._pid_alive(gc_pid)
        process_group.terminate_job(job)
        for _ in range(100):            # ≤10s
            if not sandbox._pid_alive(gc_pid):
                break
            time.sleep(0.1)
        assert not sandbox._pid_alive(gc_pid), (
            "re-parented orphan survived terminate_job — the exact "
            "shape that reached 102 GB")
    finally:
        for pid in (gc_pid, child.pid):
            if pid:
                subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"],
                               capture_output=True)
