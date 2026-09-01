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
import time

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
                         fence_gb=0.2, cwd=str(tmp_path), cpu_budget_sec=120)
    # Two legal fates for 400M inside a 0.2G fence. A Job Object caps
    # COMMIT, so Windows kills it (capped). A cgroup caps RAM and leaves
    # swap open as the valve (owner ruling: the fence bounds what the
    # build takes from RAM, the OS may page the rest), so a host with
    # swap — the SP7 runs zram — lets it finish with its RAM peak pinned
    # at the fence; only RAM+swap exhaustion is an OOM kill there.
    if over.capped:
        assert over.returncode != 0
    else:
        assert over.returncode == 0 and "held 400" in over.stdout, (
            over.returncode, over.stdout, over.stderr)
        assert over.peak_gb is not None and 0.18 <= over.peak_gb <= 0.2, (
            "an unkilled over-allocation must have been pinned at the fence")
    under = mf.run_fenced([sys.executable, str(script), "20"],
                          fence_gb=0.5, cwd=str(tmp_path), cpu_budget_sec=120)
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
                      cwd=str(tmp_path), cpu_budget_sec=1)
    pid = int(pid_file.read_text())
    assert pid != os.getpid()
    deadline = time.monotonic() + 5
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not psutil.pid_exists(pid), "the fenced tree must die with the timeout"


# ───────────────────────── the two clocks ─────────────────────────
#
# SP7 2026-09-01 23:04Z: the first real fenced build got a 1.23G fence
# for a module whose working set is 3.2G, ran at 31% CPU paging into
# zram, and would have hit the 600s WALL-CLOCK wall as a build error —
# promotion rolled back, brick re-dispatched, ~30 min of formalizer work
# lost. A build that is merely slow because the machine is crowded or
# paging is not a broken build; the budget is the CPU it got, and
# wall-clock is only the net under a tree that never runs (the same
# ruling the elaboration wall took on 2026-08-29).

def test_the_budget_is_cpu_seconds_the_wall_clock_is_only_the_net():
    # slow but computing: 120 CPU-s of a 600 CPU-s budget — not the wall
    assert mf.decide(120.0, 590.0, 600.0, 2400.0) is None
    fired = mf.decide(600.0, 700.0, 600.0, 2400.0)
    assert fired and "CPU-s" in fired
    # a tree that never runs is still caught, loosely
    fired = mf.decide(30.0, 2400.0, 600.0, 2400.0)
    assert fired and "wall-clock" in fired and "2400" in fired
    # both fired at once → the budget, not the net, is what is named
    assert "CPU-s" in mf.decide(600.0, 2400.0, 600.0, 2400.0)
    # no CPU meter (unfenced host): the budget is spent on wall-clock
    assert mf.decide(None, 100.0, 600.0, 2400.0) is None
    fired = mf.decide(None, 600.0, 600.0, 2400.0)
    assert fired and "wall-clock" in fired and "no CPU meter" in fired


def test_the_wall_clock_net_is_the_elaboration_walls_factor():
    from Tooling.lsp.gateway import wall
    assert mf.BUILD_WALL_CLOCK_FACTOR == wall.ELAB_WALL_CLOCK_FACTOR, \
        "one shape for both walls — the copy in mem_fence drifted"


# ───────────────────────── the fence follows the room ─────────────────────────

def test_the_fence_only_ever_grows_and_not_by_noise():
    assert mf.next_fence_gb(1.2, None) is None, "no reading, no raise"
    assert mf.next_fence_gb(1.2, 0.8) is None, "the fence never shrinks"
    assert mf.next_fence_gb(1.2, 1.3) is None, "noise is not worth a syscall"
    assert mf.next_fence_gb(1.2, 3.8) == 3.8


def test_the_linux_scope_is_named_so_its_limit_can_be_raised_in_place():
    cmd = mf.linux_fenced_argv(["lake", "build", "A.B"], fence_bytes=2**30,
                               stats_path="/tmp/x.stats",
                               unit="asterism-build-ab12ef34.scope")
    assert "--unit=asterism-build-ab12ef34.scope" in cmd
    assert cmd[-3:] == ["lake", "build", "A.B"]
    assert mf.linux_set_property_argv("asterism-build-ab12ef34.scope",
                                      3 * 2**30) == [
        "systemctl", "--user", "set-property", "asterism-build-ab12ef34.scope",
        f"MemoryMax={3 * 2**30}"]


def test_cgroup_cpu_seconds_come_from_usage_usec():
    text = ("usage_usec 1500000\nuser_usec 900000\nsystem_usec 600000\n"
            "nr_periods 0\n")
    assert mf.parse_cpu_usage_sec(text) == pytest.approx(1.5)
    assert mf.parse_cpu_usage_sec("nr_periods 0\n") is None
    assert mf.parse_cpu_usage_sec("") is None


# ───────────────────────── the real OS ─────────────────────────

_STEP_ALLOC = (
    "import os, sys, time\n"
    "gate = sys.argv[1]\n"
    "step = 100 * 1024 * 1024\n"
    "held = []\n"
    "for i in range(5):\n"
    "    if i == 1:\n"
    "        while not os.path.exists(gate):\n"
    "            time.sleep(0.05)\n"
    "    b = bytearray(step)\n"
    "    for j in range(0, step, 4096):\n"
    "        b[j] = 1\n"
    "    held.append(b)\n"
    "    time.sleep(0.2)\n"
    "print('held', 100 * len(held))\n")


@pytest.mark.skipif(not mf.fence_supported(), reason="no OS fence here")
def test_the_fence_follows_the_room_upward_while_the_build_runs(tmp_path):
    """The fence is sized at launch from the room the machine has THEN.
    SP7 2026-09-01: the operator closed Chrome mid-build, available rose
    1.2→3.8G, and the frozen fence kept the build paging until a manual
    `set-property` unblocked it. `grow_to` is polled while the build
    runs and the OS limit is raised in place."""
    script = tmp_path / "steps.py"
    script.write_text(_STEP_ALLOC, encoding="utf-8")
    gate = tmp_path / "grown.flag"
    polls = []

    def grow_to():
        polls.append(1)
        if len(polls) >= 2:      # the raise asked for on poll 1 is in effect
            gate.write_text("go", encoding="utf-8")
        return 1.0

    r = mf.run_fenced([sys.executable, str(script), str(gate)], fence_gb=0.2,
                      cwd=str(tmp_path), cpu_budget_sec=120, grow_to=grow_to)
    assert polls, "grow_to must be polled while the build runs"
    assert r.capped is False and r.returncode == 0, (r.returncode, r.stderr)
    assert "held 500" in r.stdout, r.stdout
    assert r.fence_gb == pytest.approx(0.2)
    assert r.fence_final_gb == pytest.approx(1.0), \
        "the fence must end at the room the machine offered, not at launch's"


_SPIN = ("import time\n"
         "t = time.monotonic()\n"
         "while time.monotonic() - t < 120:\n"
         "    sum(i * i for i in range(10000))\n")


@pytest.mark.skipif(not mf.fence_supported(), reason="no OS fence here")
def test_the_cpu_clock_stops_a_build_that_spends_its_budget(tmp_path):
    script = tmp_path / "spin.py"
    script.write_text(_SPIN, encoding="utf-8")
    with pytest.raises(subprocess.TimeoutExpired) as e:
        mf.run_fenced([sys.executable, str(script)], fence_gb=0.5,
                      cwd=str(tmp_path), cpu_budget_sec=1)
    assert "CPU-s" in str(e.value), str(e.value)


@pytest.mark.skipif(not mf.fence_supported(), reason="no OS fence here")
def test_the_wall_clock_net_stops_a_tree_that_never_runs(tmp_path):
    script = tmp_path / "sleep.py"
    script.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    t0 = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as e:
        mf.run_fenced([sys.executable, str(script)], fence_gb=0.5,
                      cwd=str(tmp_path), cpu_budget_sec=1)
    assert "wall-clock" in str(e.value), str(e.value)
    assert "CPU-s" not in str(e.value), \
        "a sleeping tree spent no CPU — the net fired, not the budget"
    # the net is the budget × BUILD_WALL_CLOCK_FACTOR, not the budget
    assert time.monotonic() - t0 >= 1 * mf.BUILD_WALL_CLOCK_FACTOR - 1.0
