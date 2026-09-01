"""OS memory fence around a cold `lake build` (owner ruling 2026-09-02).

The #234 admission gate asked "will the peak fit?" and needed a number
to answer — 3.7G measured once, 4.5 locked every build out, 4.0 was
pushed through by the operator's browser the same day. The fence asks
nothing up front: the build runs inside a cgroup / Job Object sized to
the room the machine has RIGHT NOW (measured available minus the
ledger's own pressure line, shared among in-flight builds), the OS
enforces it, and exceeding it is a structured `capped` outcome — not a
crushed machine, not a build error.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from Tooling.core import mem_fence as mf
import Tooling.core.ram_ledger as rl


# ───────────────────────── sizing ─────────────────────────

def test_fence_is_the_room_above_the_pressure_line(monkeypatch):
    monkeypatch.setattr(rl, "total_gb", lambda: 32.0)
    monkeypatch.setattr(rl, "available_gb", lambda: 10.0)
    # pressure_low(32) = max(1.5 + 2, 0.06 * 32) = 3.5
    monkeypatch.delenv("ASTERISM_RAM_PRESSURE_LOW_GB", raising=False)
    monkeypatch.setattr(rl, "_env_override_gb", lambda name: None)
    assert mf.fence_gb_now() == pytest.approx(6.5)


def test_fence_is_shared_among_inflight_builds(monkeypatch):
    monkeypatch.setattr(rl, "total_gb", lambda: 32.0)
    monkeypatch.setattr(rl, "available_gb", lambda: 10.0)
    monkeypatch.setattr(rl, "_env_override_gb", lambda name: None)
    assert mf.fence_gb_now(inflight=2) == pytest.approx(3.25)


def test_no_room_means_no_fence_not_a_zero_fence(monkeypatch):
    monkeypatch.setattr(rl, "total_gb", lambda: 32.0)
    monkeypatch.setattr(rl, "available_gb", lambda: 3.0)
    monkeypatch.setattr(rl, "_env_override_gb", lambda name: None)
    assert mf.fence_gb_now() is None


# ───────────────────────── linux command shape ─────────────────────────

def test_linux_wrapper_is_a_user_scope_with_memorymax_and_the_verbatim_command():
    cmd = mf.linux_fenced_argv(["lake", "build", "A.B"], fence_bytes=3 * 2**30,
                               stats_path="/tmp/x.stats")
    assert cmd[:3] == ["systemd-run", "--user", "--scope"]
    assert f"MemoryMax={3 * 2**30}" in cmd
    assert "MemorySwapMax" not in " ".join(cmd), \
        "swap is the excess valve — the fence bounds RAM, the OS may page"
    assert cmd[-3:] == ["lake", "build", "A.B"]


def test_linux_stats_parse_reads_peak_and_oom_kills():
    text = "3221225472\nlow 0\nhigh 0\nmax 12\noom 3\noom_kill 1\n"
    peak, kills = mf.parse_linux_stats(text)
    assert peak == 3221225472 and kills == 1
    assert mf.parse_linux_stats("") == (None, 0)


def test_classification_is_structural_not_textual():
    # an OOM kill inside the fence = capped, whatever rc lake reported
    assert mf.classify(rc=1, oom_kills=1, stats_seen=True) is True
    # a plain build error with no kill = not capped
    assert mf.classify(rc=1, oom_kills=0, stats_seen=True) is False
    # the shell that writes the stats was itself killed: SIGKILL rc + no
    # stats is the only fingerprint left
    assert mf.classify(rc=137, oom_kills=0, stats_seen=False) is True
    assert mf.classify(rc=-9, oom_kills=0, stats_seen=False) is True
    assert mf.classify(rc=0, oom_kills=0, stats_seen=False) is False


# ───────────────────────── the real OS ─────────────────────────

_ALLOC = ("import sys\n"
          "n = int(sys.argv[1])\n"
          "buf = bytearray(n * 1024 * 1024)\n"
          "for i in range(0, len(buf), 4096):\n"
          "    buf[i] = 1\n"
          "print('held', n)\n")


@pytest.mark.skipif(not mf.fence_supported(), reason="no OS fence here")
def test_the_os_enforces_the_fence(tmp_path):
    script = tmp_path / "alloc.py"
    script.write_text(_ALLOC, encoding="utf-8")
    over = mf.run_fenced([sys.executable, str(script), "400"],
                         fence_gb=0.2, cwd=str(tmp_path), timeout=120)
    assert over.capped is True, (over.returncode, over.stdout, over.stderr)
    assert over.returncode != 0
    under = mf.run_fenced([sys.executable, str(script), "20"],
                          fence_gb=0.5, cwd=str(tmp_path), timeout=120)
    assert under.capped is False and under.returncode == 0
    assert "held 20" in under.stdout
    assert under.peak_gb is not None and under.peak_gb > 0.0


@pytest.mark.skipif(not mf.fence_supported(), reason="no OS fence here")
def test_a_timed_out_fenced_build_leaves_no_process_behind(tmp_path):
    import os
    import time
    import psutil
    script = tmp_path / "sleep.py"
    pid_file = tmp_path / "pid.txt"
    script.write_text(
        "import os, time, sys\n"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "time.sleep(60)\n", encoding="utf-8")
    with pytest.raises(subprocess.TimeoutExpired):
        mf.run_fenced([sys.executable, str(script)], fence_gb=0.5,
                      cwd=str(tmp_path), timeout=3)
    pid = int(pid_file.read_text())
    assert pid != os.getpid()
    deadline = time.monotonic() + 5
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not psutil.pid_exists(pid), "the fenced tree must die with the timeout"
