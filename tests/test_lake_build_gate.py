"""`lake build` goes through a gate (owner ruling 2026-08-30).

Flagship 00:00Z: the daemon ran 13 `lake build`s at once — two with
byte-identical module lists — each letting Lake fan out over all 16
cores (Lake 5 has no `--jobs`; `LEAN_NUM_THREADS` is the knob), beside
14 elaboration lanes: load 217, 108 batch `lean`s, 4 GB left of 125.
Every daemon-side build funnels through `lake_build_modules`; that one
door now (1) coalesces identical lists, (2) runs one build at a time
under a lease that says how many threads it may use, and (3) reports
queueing and building as different failures.
"""
from __future__ import annotations

import threading
import time
import types

import pytest

from Tooling.pipeline import _lake

# conftest's `_stub_cold_lake_by_default` replaces `lake_build_modules`
# with a (True, "") stub for every test; this module tests the real door
# (with subprocess.run faked), so put the real function back first.
_REAL_LAKE_BUILD_MODULES = _lake.lake_build_modules


@pytest.fixture(autouse=True)
def _real_door(monkeypatch):
    monkeypatch.setattr(_lake, "lake_build_modules", _REAL_LAKE_BUILD_MODULES)


class _FakeRun:
    """Stand-in for subprocess.run: records argv/env, sleeps, succeeds."""

    def __init__(self, sleep=0.0):
        self.calls = []
        self.sleep = sleep
        self.live = 0
        self.max_live = 0
        self._lock = threading.Lock()

    def __call__(self, argv, **kw):
        with self._lock:
            self.live += 1
            self.max_live = max(self.max_live, self.live)
            self.calls.append((list(argv), dict(kw.get("env") or {})))
        try:
            time.sleep(self.sleep)
        finally:
            with self._lock:
                self.live -= 1
        return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")


@pytest.fixture
def fake_run(monkeypatch):
    fr = _FakeRun(sleep=0.15)
    monkeypatch.setattr(_lake.subprocess, "run", fr)
    _lake.install_build_gate(_lake.LocalBuildGate(threads=3))
    yield fr
    _lake.install_build_gate(None)


def _build(ws, mods, out):
    out.append(_lake.lake_build_modules(ws, mods))


def test_identical_module_lists_coalesce_into_one_build(tmp_path, fake_run):
    out = []
    ts = [threading.Thread(target=_build, args=(tmp_path, ["M.A", "M.B"], out))
          for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=10)
    assert len(fake_run.calls) == 1, "the second caller waits for the first build"
    assert out == [(True, "ok"), (True, "ok")]


def test_distinct_lists_serialize_under_the_local_gate(tmp_path, fake_run):
    out = []
    ts = [threading.Thread(target=_build, args=(tmp_path, [m], out))
          for m in ("M.A", "M.B", "M.C")]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=10)
    assert len(fake_run.calls) == 3
    assert fake_run.max_live == 1, "one lake at a time"


def test_lake_runs_with_the_leased_thread_count(tmp_path, fake_run):
    _lake.lake_build_modules(tmp_path, ["M.A"])
    (argv, env), = fake_run.calls
    assert argv[:2] == ["lake", "build"]
    assert env["LEAN_NUM_THREADS"] == "3"


def test_gateway_gate_polls_until_a_lease_is_granted(monkeypatch, tmp_path):
    fr = _FakeRun()
    monkeypatch.setattr(_lake.subprocess, "run", fr)
    replies = [(409, {"retry_after_s": 0.01, "build_busy": 2}),
               (200, {"token": "t1", "threads": 2, "ttl_s": 900})]
    posted = []

    def fake_post(url, payload, timeout):
        posted.append((url, payload))
        if url.endswith("/build/lease"):
            return replies.pop(0)
        return (200, {"ok": True})

    gate = _lake.GatewayBuildGate("http://127.0.0.1:1", owner="daemon-9",
                                  poll_sec=0.01, post=fake_post)
    _lake.install_build_gate(gate)
    try:
        ok, out = _lake.lake_build_modules(tmp_path, ["M.A"])
    finally:
        _lake.install_build_gate(None)
    assert ok
    (argv, env), = fr.calls
    assert env["LEAN_NUM_THREADS"] == "2"
    urls = [u for u, _ in posted]
    assert urls[:2] == ["http://127.0.0.1:1/build/lease"] * 2
    assert urls[-1] == "http://127.0.0.1:1/build/release/t1"
    assert posted[0][1]["owner"] == "daemon-9"


def test_gateway_gate_waits_for_ram_headroom_before_asking_for_lanes(
        monkeypatch, tmp_path):
    fr = _FakeRun()
    monkeypatch.setattr(_lake.subprocess, "run", fr)
    ram = {"ok": [False, False, True]}
    asked = []

    def fake_post(url, payload, timeout):
        asked.append(url)
        if url.endswith("/build/lease"):
            return (200, {"token": "t", "threads": 1, "ttl_s": 900})
        return (200, {})
    gate = _lake.GatewayBuildGate(
        "http://h", owner="d", poll_sec=0.01, post=fake_post,
        ram_ok=lambda n: ram["ok"].pop(0))
    _lake.install_build_gate(gate)
    try:
        assert _lake.lake_build_modules(tmp_path, ["M"])[0]
    finally:
        _lake.install_build_gate(None)
    assert ram["ok"] == [], "polled the RAM check until it said yes"
    assert asked[0].endswith("/build/lease"), "lanes are asked only once RAM is fine"


def test_gateway_gate_queue_timeout_is_named_as_queueing_not_building(
        monkeypatch, tmp_path):
    fr = _FakeRun()
    monkeypatch.setattr(_lake.subprocess, "run", fr)
    gate = _lake.GatewayBuildGate(
        "http://h", owner="d", poll_sec=0.01, queue_timeout_sec=0.05,
        post=lambda u, p, t: (409, {"retry_after_s": 0.01}))
    _lake.install_build_gate(gate)
    try:
        ok, out = _lake.lake_build_modules(tmp_path, ["M"])
    finally:
        _lake.install_build_gate(None)
    assert ok is False
    assert "build queue saturated" in out
    assert "timed out (600s)" not in out
    assert fr.calls == [], "never built"


def test_gateway_unreachable_falls_back_to_the_local_gate(monkeypatch, tmp_path):
    fr = _FakeRun()
    monkeypatch.setattr(_lake.subprocess, "run", fr)

    def dead(url, payload, timeout):
        raise OSError("connection refused")
    gate = _lake.GatewayBuildGate("http://h", owner="d", poll_sec=0.01,
                                  post=dead, local_threads=2)
    _lake.install_build_gate(gate)
    try:
        ok, _ = _lake.lake_build_modules(tmp_path, ["M"])
    finally:
        _lake.install_build_gate(None)
    assert ok
    (argv, env), = fr.calls
    assert env["LEAN_NUM_THREADS"] == "2", "a gateway outage bounds the build locally"


def test_dedupe_preflight_failure_is_recorded_as_degraded(monkeypatch, tmp_path):
    """The pre-flight used to discard `lake_build_modules`' result: a
    600 s timeout left no trace anywhere (flagship 2026-08-30, 0 log
    lines for builds that ran past their limit)."""
    from Tooling.quality import dedupe_probe
    from Tooling.core import degraded
    monkeypatch.setattr(_lake, "lake_build_modules",
                        lambda ws, mods: (False, "lake build M timed out (600s)"))
    seen = []
    monkeypatch.setattr(degraded, "record",
                        lambda ws, kind, detail="": seen.append((kind, detail)))
    dedupe_probe._preflight_build(tmp_path, ["M"])
    assert seen and seen[0][0] == "dedupe_preflight_build"
    assert "timed out" in seen[0][1]
