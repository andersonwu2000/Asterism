"""Every daemon-side `lake build` runs inside an OS memory fence sized
to the room the machine has now; exceeding it is `capped`, a structured
outcome that WAITS FOR ROOM and retries (lake resumes at the failed
module) — never a build error, never a goal casualty. The lane lease is
released while waiting so CPU is not parked on a RAM wait.
"""
from __future__ import annotations

from pathlib import Path

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
