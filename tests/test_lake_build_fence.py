"""Every daemon-side `lake build` runs inside an OS memory fence sized
to the room the machine has now; exceeding it is `capped`, a structured
outcome that WAITS FOR ROOM and retries (lake resumes at the failed
module) — never a build error, never a goal casualty. The lane lease is
released while waiting so CPU is not parked on a RAM wait.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.core import degraded
from Tooling.core import mem_fence as mf
from Tooling.pipeline import _lake


class _Clock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, s):
        self.t += float(s)


class _Gate:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    def acquire(self, threads, hint="", *, after_capped=False):
        self.acquired += 1
        self.after_capped = after_capped
        return _lake.BuildLease(threads=1, release=self._rel)

    def _rel(self):
        self.released += 1


def _wire(monkeypatch, tmp_path, *, runs, fences):
    """`runs`: FenceResults handed out per `run_fenced` call;
    `fences`: fence readings handed out per `fence_gb_now` call."""
    clock = _Clock()
    gate = _Gate()
    calls = {"run": 0, "fence": 0}
    monkeypatch.setattr(_lake.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(_lake.time, "sleep", clock.sleep)
    monkeypatch.setattr(_lake, "_gate", lambda: gate)

    def fake_run(args, fence_gb, **kw):
        calls["run"] += 1
        r = runs[min(calls["run"] - 1, len(runs) - 1)]
        r.fence_gb = fence_gb
        return r

    def fake_fence(inflight=1):
        calls["fence"] += 1
        return fences[min(calls["fence"] - 1, len(fences) - 1)]
    monkeypatch.setattr(_lake, "run_fenced", fake_run)
    monkeypatch.setattr(_lake, "fence_gb_now", fake_fence)
    monkeypatch.setattr(_lake, "ROOM_WAIT_SEC", 100.0)
    _lake._INFLIGHT.clear()
    # conftest stubs `lake_build_modules` for every test; the door under
    # it — `_run_chunks` — is what these tests exercise
    return clock, gate, calls


def _res(*, rc=0, out="", capped=False, peak=1.0):
    return mf.FenceResult(returncode=rc, stdout=out, stderr="",
                          capped=capped, peak_gb=peak, fence_gb=None)


def test_a_capped_build_waits_for_more_room_and_resumes(monkeypatch, tmp_path):
    clock, gate, calls = _wire(
        monkeypatch, tmp_path,
        runs=[_res(rc=137, capped=True, peak=2.0), _res(rc=0, out="Build completed")],
        fences=[2.0, 2.0, 2.0, 3.0])
    res = _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    ok, out = res
    assert ok is True and "Build completed" in out
    assert res.capped is False
    assert calls["run"] == 2, "lake resumed after room appeared"
    # room is 'strictly more than the fence that was exceeded'
    assert calls["fence"] >= 4
    assert gate.acquired == 2 and gate.released == 2, \
        "the lane lease is released while waiting for RAM"
    assert clock.t > 0, "waited, did not busy-spin"
    led = degraded.snapshot(tmp_path)
    assert led.get("build_capped", {}).get("count") == 1


def test_room_that_never_comes_is_a_capped_outcome_not_a_build_error(
        monkeypatch, tmp_path):
    clock, gate, calls = _wire(
        monkeypatch, tmp_path,
        runs=[_res(rc=137, out="error: lean exited with code 137", capped=True)],
        fences=[1.5])
    res = _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    ok, out = res
    assert ok is False
    assert res.capped is True
    assert out.startswith("build capped"), out
    assert "1.5" in out and "waited" in out
    assert calls["run"] == 1
    assert clock.t >= 100.0
    assert gate.acquired == gate.released == 1


def test_no_room_at_all_waits_before_launching(monkeypatch, tmp_path):
    clock, gate, calls = _wire(
        monkeypatch, tmp_path,
        runs=[_res(rc=0, out="Build completed")],
        fences=[None, None, 1.0])
    res = _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    assert res[0] is True
    assert calls["run"] == 1
    assert clock.t > 0
    assert gate.acquired == 1, "no lane is held while there is no room to build"


def test_a_plain_build_error_is_still_a_build_error(monkeypatch, tmp_path):
    clock, gate, calls = _wire(
        monkeypatch, tmp_path,
        runs=[_res(rc=1, out="error: X.lean:3:1: unknown identifier")],
        fences=[4.0])
    res = _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    assert res[0] is False and res.capped is False
    assert "unknown identifier" in res[1]
    assert calls["run"] == 1
    assert degraded.snapshot(tmp_path).get("build_capped") is None


def test_the_fence_is_shared_by_concurrent_builds(monkeypatch, tmp_path):
    seen = []
    clock, gate, calls = _wire(
        monkeypatch, tmp_path, runs=[_res()], fences=[4.0])

    def counting_fence(inflight=1):
        seen.append(inflight)
        return 4.0
    monkeypatch.setattr(_lake, "fence_gb_now", counting_fence)
    _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    assert seen == [1]
    # a second build in flight halves the room the next one is sized to
    with _lake._inflight_build():
        _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_b"]], "t")
    assert seen[-1] == 2


# ─── the fence follows the room, the wall counts CPU (2026-09-02) ───
#
# First real fenced build, SP7 6.8 GB, 2026-09-01 23:04Z: sized at 1.23G
# with the operator's Chrome open, around a module whose working set is
# 3.2G. lean ran at 31% CPU paging into zram. Chrome closed, available
# rose to 3.8G — the fence stayed at 1.23G, and the 600s WALL-CLOCK wall
# was about to fail the build for being slow.

def test_the_fence_follows_the_room_while_the_build_runs(monkeypatch, tmp_path):
    seen: dict = {}
    _wire(monkeypatch, tmp_path, runs=[_res()], fences=[1.2])

    def record(args, fence_gb, **kw):
        seen["fence"] = fence_gb
        seen["grow_to"] = kw.get("grow_to")
        seen["budget"] = kw.get("cpu_budget_sec")
        return _res()
    monkeypatch.setattr(_lake, "run_fenced", record)
    monkeypatch.setattr(_lake, "fence_gb_now", lambda inflight=1: 1.2)
    _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    assert seen["fence"] == 1.2
    assert seen["budget"] == _lake.LAKE_BUILD_CPU_BUDGET_SEC, \
        "the build's budget is CPU seconds, handed to the fence"
    assert callable(seen["grow_to"]), "the fence must be re-sizable mid-build"
    # the machine frees room: the same callable now offers the new fence
    monkeypatch.setattr(_lake, "fence_gb_now", lambda inflight=1: 3.8)
    assert seen["grow_to"]() == 3.8
    # and it is the SHARED room, not a per-build number
    monkeypatch.setattr(_lake, "fence_gb_now", lambda inflight=1: 3.8 / inflight)
    with _lake._inflight_build(), _lake._inflight_build():
        assert seen["grow_to"]() == pytest.approx(1.9)


def test_a_timed_out_build_names_the_clock_that_fired(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, runs=[_res()], fences=[2.0])

    def walled(args, fence_gb, **kw):
        raise mf.FenceTimeout(list(args), 600.0,
                              "600 CPU-s of the 600 CPU-s budget")
    monkeypatch.setattr(_lake, "run_fenced", walled)
    res = _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    assert res[0] is False and res.capped is False
    assert "timed out" in res[1] and "600 CPU-s" in res[1], res[1]


def test_every_finished_build_reports_its_fence_and_its_clocks(
        monkeypatch, tmp_path, capsys):
    r = mf.FenceResult(returncode=0, stdout="Build completed", stderr="",
                       capped=False, peak_gb=3.2, fence_gb=None,
                       fence_final_gb=3.8, cpu_sec=512.4, wall_sec=690.2)
    _wire(monkeypatch, tmp_path, runs=[r], fences=[1.2])
    _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    lines = [ln for ln in capsys.readouterr().out.splitlines() if "fence" in ln]
    assert lines, "a finished build must say what room it got and what it used"
    assert "fence 1.2→3.8G" in lines[0], lines[0]
    assert "peak 3.2G" in lines[0] and "cpu 512.4s" in lines[0] \
        and "wall 690.2s" in lines[0], lines[0]


def test_a_capped_build_waits_for_room_above_the_fence_it_actually_had(
        monkeypatch, tmp_path):
    """The fence GROWS while the build runs, so the number the OS
    stopped it at is the final one, not the one it launched with.
    Waiting for 'more than the launch fence' would relaunch straight
    back into the wall it just hit."""
    capped = mf.FenceResult(returncode=137, stdout="", stderr="", capped=True,
                            peak_gb=3.0, fence_gb=None, fence_final_gb=3.0)
    clock, gate, calls = _wire(
        monkeypatch, tmp_path,
        runs=[capped, _res(rc=0, out="Build completed")],
        fences=[1.2, 2.0])
    res = _lake._run_chunks(tmp_path, [["Problems.p.proofs.L_a"]], "t")
    assert res.capped is True, "2.0G is not more room than the 3.0G it had"
    assert calls["run"] == 1
    assert "3.0" in res[1], res[1]
