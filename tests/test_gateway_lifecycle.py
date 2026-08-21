"""Tooling/gateway_lifecycle.py — verify_file retry behavior.

These tests cover the in-process retry-with-backoff added 2026-05-11
after observing SG run #14 strategy=252 die because gateway HTTP
endpoint was momentarily unreachable during peak in-flight spawn load.
Before: any URLError / OSError / HTTP 5xx propagated up as
`{"error": ...}` which `verify.verify_strategy` mapped straight to
`"dead"` — wasted a fully-decomposed strategy + proved sub-goals.
After: transient infra failures retry with backoff, return
`transient=True` so the caller can defer to a later dispatcher tick.
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from Tooling.lsp import lifecycle as gateway_lifecycle

# Capture the REAL verify_file / verify_in_session before any test's conftest
# autouse replaces them with stubs. Each test below restores these via the
# module-local autouse `_restore_real_verify_fns` so we exercise the actual
# retry-with-backoff / token-post path, not the conftest happy-path stub.
_REAL_VERIFY_FILE = gateway_lifecycle.verify_file
_REAL_VERIFY_IN_SESSION = gateway_lifecycle.verify_in_session


@pytest.fixture(autouse=True)
def _restore_real_verify_fns(monkeypatch: pytest.MonkeyPatch):
    """Override conftest's `_stub_axiom_probe_by_default` for this file
    only — we need the real verify_file / verify_in_session bodies to test
    their retry / error classification / token-post logic. Applied after
    conftest's autouse, so this monkeypatch wins."""
    monkeypatch.setattr(gateway_lifecycle, "verify_file", _REAL_VERIFY_FILE)
    monkeypatch.setattr(
        gateway_lifecycle, "verify_in_session", _REAL_VERIFY_IN_SESSION)


class _MockResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _make_urlerror(msg: str = "timed out") -> urllib.error.URLError:
    return urllib.error.URLError(msg)


def test_verify_file_returns_response_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Happy path: gateway responds OK → returns parsed body verbatim
    (no transient flag in success path)."""
    target = tmp_path / "f.lean"
    target.write_text("-- stub", encoding="utf-8")

    payload = {"ok": True, "diagnostics": [], "diagnostic_count": 0,
               "olean_written": True, "olean_path": "/dev/null",
               "axioms": None, "axiom_error": None}
    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen",
        lambda req, timeout: _MockResponse(payload))

    out = gateway_lifecycle.verify_file(target, workspace=tmp_path)
    assert out == payload
    assert "transient" not in out


def test_verify_file_decl_info_flag_in_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`decl_info=True` puts the flag in the POST body (so the gateway
    runs the `Asterism.declInfo` RPC); default omits it entirely."""
    target = tmp_path / "f.lean"
    target.write_text("-- stub", encoding="utf-8")
    bodies: list[dict] = []

    def fake_urlopen(req, timeout):
        bodies.append(json.loads(req.data.decode("utf-8")))
        return _MockResponse({"ok": True})

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)

    gateway_lifecycle.verify_file(target, workspace=tmp_path)
    gateway_lifecycle.verify_file(target, decl_info=True,
                                  workspace=tmp_path)
    assert "decl_info" not in bodies[0]
    assert bodies[1]["decl_info"] is True


def test_verify_file_missing_target_marks_non_transient(
    tmp_path: Path,
) -> None:
    """Target file doesn't exist → error with transient=False (logic
    error, not retry-eligible)."""
    out = gateway_lifecycle.verify_file(
        tmp_path / "nope.lean", workspace=tmp_path,
    )
    assert "error" in out
    assert out["transient"] is False


def test_verify_file_retries_on_urlerror_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """First two attempts raise URLError (timeout), third succeeds →
    final return is the success body. Uses near-zero delays to keep
    the test fast."""
    target = tmp_path / "f.lean"
    target.write_text("-- stub", encoding="utf-8")

    payload = {"ok": True}
    calls = {"n": 0}

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _make_urlerror("timed out")
        return _MockResponse(payload)

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(gateway_lifecycle.time, "sleep", lambda s: None)

    out = gateway_lifecycle.verify_file(
        target, workspace=tmp_path,
        _retry_delays=(0.01, 0.01, 0.01),
    )
    assert out == payload
    assert calls["n"] == 3


def test_verify_file_exhausts_retries_returns_transient_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """All attempts (initial + 3 retries = 4 total) raise URLError →
    returns error dict with transient=True."""
    target = tmp_path / "f.lean"
    target.write_text("-- stub", encoding="utf-8")

    calls = {"n": 0}

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        raise _make_urlerror("timed out")

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(gateway_lifecycle.time, "sleep", lambda s: None)

    out = gateway_lifecycle.verify_file(
        target, workspace=tmp_path,
        _retry_delays=(0.01, 0.01, 0.01),
    )
    assert "error" in out
    assert out["transient"] is True
    assert "unreachable" in out["error"]
    # Initial attempt + len(delays) retries = 4 total
    assert calls["n"] == 4


def test_verify_file_http_5xx_retries_as_transient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """HTTPError with 5xx code is server-side transient → retried, and
    if exhausted, returned with transient=True."""
    target = tmp_path / "f.lean"
    target.write_text("-- stub", encoding="utf-8")

    calls = {"n": 0}

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            url="http://x", code=503, msg="Service Unavailable",
            hdrs=None, fp=None,
        )

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(gateway_lifecycle.time, "sleep", lambda s: None)

    out = gateway_lifecycle.verify_file(
        target, workspace=tmp_path,
        _retry_delays=(0.01,),
    )
    assert "error" in out
    assert out["transient"] is True
    assert "503" in out["error"]
    assert calls["n"] == 2  # initial + 1 retry


def test_verify_file_http_4xx_returns_immediately_non_transient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """HTTPError with 4xx code is request error → no retry,
    transient=False."""
    target = tmp_path / "f.lean"
    target.write_text("-- stub", encoding="utf-8")

    calls = {"n": 0}

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            url="http://x", code=400, msg="Bad Request",
            hdrs=None, fp=None,
        )

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)

    out = gateway_lifecycle.verify_file(
        target, workspace=tmp_path,
        _retry_delays=(0.01, 0.01),
    )
    assert "error" in out
    assert out["transient"] is False
    assert "400" in out["error"]
    assert calls["n"] == 1  # no retry on 4xx


# ---------------------------------------------------------------------
# start_gateway: reconcile reused gateway's worker count vs dispatch.pool
# ---------------------------------------------------------------------

class _FakeProc:
    def poll(self): return None
    def terminate(self): pass
    def wait(self, timeout=None): return 0


def test_start_gateway_reuses_when_workers_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Healthy gateway whose workers_total == dispatch.pool AND whose code
    fingerprint matches the current tree → reused (no relaunch, no kill)."""
    monkeypatch.setattr(gateway_lifecycle, "code_fingerprint", lambda: "fp1")
    monkeypatch.setattr(gateway_lifecycle, "_ping_health",
        lambda timeout=1.0: {"backend_ready": True, "workers_total": 4,
                             "pid": 999, "code_fingerprint": "fp1"})
    monkeypatch.setattr(gateway_lifecycle, "_desired_pool", lambda ws: 4)
    killed = {"n": 0}
    monkeypatch.setattr(gateway_lifecycle, "_kill_stale_gateway",
                        lambda pid: killed.__setitem__("n", killed["n"] + 1))

    def _no_launch(*a, **k):
        raise AssertionError("should reuse, not relaunch")
    monkeypatch.setattr(gateway_lifecycle.subprocess, "Popen", _no_launch)

    proc = gateway_lifecycle.start_gateway(tmp_path)
    assert proc.poll() is None          # the reuse stub
    assert killed["n"] == 0


def test_start_gateway_relaunches_on_worker_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Healthy gateway with workers_total != dispatch.pool → kill the stale
    one (by its /health pid) and relaunch a fresh gateway."""
    calls = {"n": 0}

    def ping(timeout=1.0):
        calls["n"] += 1
        # 1st: the reuse check sees the stale 2-worker gateway.
        # later: the post-launch readiness poll sees the fresh 4-worker one.
        if calls["n"] == 1:
            return {"backend_ready": True, "workers_total": 2, "pid": 777,
                    "code_fingerprint": "fp1"}
        return {"backend_ready": True, "workers_total": 4, "pid": 888,
                "code_fingerprint": "fp1"}
    monkeypatch.setattr(gateway_lifecycle, "code_fingerprint", lambda: "fp1")
    monkeypatch.setattr(gateway_lifecycle, "_ping_health", ping)
    monkeypatch.setattr(gateway_lifecycle, "_desired_pool", lambda ws: 4)
    killed = {"pid": None}
    monkeypatch.setattr(gateway_lifecycle, "_kill_stale_gateway",
                        lambda pid: killed.__setitem__("pid", pid))
    monkeypatch.setattr(gateway_lifecycle.subprocess, "Popen",
                        lambda *a, **k: _FakeProc())
    monkeypatch.setattr(gateway_lifecycle.time, "sleep", lambda s: None)

    proc = gateway_lifecycle.start_gateway(tmp_path)
    assert killed["pid"] == 777          # killed the stale gateway by pid
    assert isinstance(proc, _FakeProc)   # relaunched a fresh one


def test_start_gateway_reuses_ram_clamped_gateway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A gateway that RAM-clamped its effective pool below dispatch.pool
    is a healthy match, not drift: the reuse gate compares yaml-to-yaml
    (workers_configured), so it must NOT kill+relaunch — that would
    re-pay the multi-minute warm on every daemon start on the very
    machines the clamp exists for (8 GB, 2026-07-09)."""
    monkeypatch.setattr(gateway_lifecycle, "code_fingerprint", lambda: "fp1")
    monkeypatch.setattr(gateway_lifecycle, "_ping_health",
        lambda timeout=1.0: {"backend_ready": True, "workers_total": 1,
                             "workers_configured": 4,
                             "pid": 999, "code_fingerprint": "fp1"})
    monkeypatch.setattr(gateway_lifecycle, "_desired_pool", lambda ws: 4)
    killed = {"n": 0}
    monkeypatch.setattr(gateway_lifecycle, "_kill_stale_gateway",
                        lambda pid: killed.__setitem__("n", killed["n"] + 1))

    def _no_launch(*a, **k):
        raise AssertionError("should reuse, not relaunch")
    monkeypatch.setattr(gateway_lifecycle.subprocess, "Popen", _no_launch)

    proc = gateway_lifecycle.start_gateway(tmp_path)
    assert proc.poll() is None
    assert killed["n"] == 0


def test_ram_clamped_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """The clamp only ever lowers, floors at 1, budgets the interactive
    slot, and stands aside when RAM is unknowable or the pool is
    already minimal."""
    clamp = gateway_lifecycle.ram_clamped_pool
    # RAM unknown → untouched (today's behaviour)
    monkeypatch.setattr(gateway_lifecycle, "_ram_budget_gb", lambda: None)
    assert clamp(4, 1) == (4, None)
    # plenty of RAM → untouched, no message
    assert clamp(4, 1, budget_gb=32.0) == (4, None)
    # the jtyy case: 8 GB total → budget 4.8, affords 1 slot, the
    # interactive slot takes it, pool floors at 1
    eff, msg = clamp(4, 1, budget_gb=4.8)
    assert eff == 1 and msg is not None
    # desperate RAM still floors at 1, never 0 or negative
    eff, msg = clamp(4, 1, budget_gb=2.0)
    assert eff == 1 and msg is not None
    # pool already 1 → nothing to downsize, no message even on tiny RAM
    assert clamp(1, 1, budget_gb=2.0) == (1, None)
    # mid case (shared-base model: 3 GB shared olean map + 1.0 GB
    # marginal, 2026-08-22 API-key-channel calibration): 7 GB budget
    # → (7−3)/1.0 = 4 slots, 1 interactive → 3
    eff, msg = clamp(4, 1, budget_gb=7.0)
    assert eff == 3 and msg is not None
    # never raises
    assert clamp(2, 1, budget_gb=64.0) == (2, None)


def test_ram_budget_undersold_available(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 'available' badly undersells a working machine (32 GB
    dev box reports ~6 GB while warming 4+1 daily) — the budget takes
    max(available, 60% total) so that box is NOT clamped, while a
    genuinely small 8 GB machine is."""
    monkeypatch.setattr(gateway_lifecycle, "physical_ram_gb",
                        lambda: (5.7, 32.0))
    assert gateway_lifecycle.ram_clamped_pool(4, 1) == (4, None)
    monkeypatch.setattr(gateway_lifecycle, "physical_ram_gb",
                        lambda: (4.0, 8.0))
    eff, msg = gateway_lifecycle.ram_clamped_pool(4, 1)
    assert eff == 1 and msg is not None


def test_start_gateway_relaunches_on_version_skew(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Healthy, pool-matched gateway whose code_fingerprint differs from
    the current tree (or is absent — pre-fingerprint build) → kill +
    relaunch. The gateway outlives daemons by design; after a code change
    the old process answers /health 200 while tool calls 500 (sphere
    daemon #5, 2026-07-05)."""
    for stale_fp in ("OLD", None):
        calls = {"n": 0}

        def ping(timeout=1.0, _fp=stale_fp):
            calls["n"] += 1
            if calls["n"] == 1:
                h = {"backend_ready": True, "workers_total": 4, "pid": 777}
                if _fp is not None:
                    h["code_fingerprint"] = _fp
                return h
            return {"backend_ready": True, "workers_total": 4, "pid": 888,
                    "code_fingerprint": "CURRENT"}
        monkeypatch.setattr(gateway_lifecycle, "code_fingerprint",
                            lambda: "CURRENT")
        monkeypatch.setattr(gateway_lifecycle, "_ping_health", ping)
        monkeypatch.setattr(gateway_lifecycle, "_desired_pool", lambda ws: 4)
        killed = {"pid": None}
        monkeypatch.setattr(gateway_lifecycle, "_kill_stale_gateway",
                            lambda pid: killed.__setitem__("pid", pid))
        monkeypatch.setattr(gateway_lifecycle.subprocess, "Popen",
                            lambda *a, **k: _FakeProc())
        monkeypatch.setattr(gateway_lifecycle.time, "sleep", lambda s: None)

        proc = gateway_lifecycle.start_gateway(tmp_path)
        assert killed["pid"] == 777, f"stale_fp={stale_fp!r}"
        assert isinstance(proc, _FakeProc)


# ---------------------------------------------------------------------
# verify_in_session — claimed-slot verify for framework gates that hold a
# session (Library cleanup). Same shape/transient semantics as verify_file
# but NO retries by default (caller falls back to cold lake on transient).
# ---------------------------------------------------------------------

def test_verify_in_session_posts_token_and_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Happy path: POSTs {token, content} to /verify_session and returns the
    parsed body verbatim."""
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockResponse({"ok": True, "diagnostics": [],
                              "diagnostic_count": 0, "timed_out": False})

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)
    out = gateway_lifecycle.verify_in_session(
        "tok-123", "theorem t : True := trivial\n", workspace=tmp_path)
    assert out["ok"] is True
    assert out.get("timed_out") is False
    assert out.get("transient") is None or "transient" not in out
    assert captured["url"].endswith("/verify_session")
    assert captured["body"]["token"] == "tok-123"
    assert captured["body"]["content"] == "theorem t : True := trivial\n"
    assert captured["body"]["write_olean"] is False  # gate default


def test_verify_in_session_empty_token_non_transient() -> None:
    """No token → logic error, not retry-eligible."""
    out = gateway_lifecycle.verify_in_session("", "x")
    assert out["transient"] is False


def test_verify_in_session_unreachable_fails_fast_transient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Gateway unreachable → ONE attempt (no retry by default), transient=True
    so the caller falls back to cold lake immediately."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        raise _make_urlerror("connection refused")

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)
    # If retries were on, sleep would be hit; assert it's never called.
    monkeypatch.setattr(gateway_lifecycle.time, "sleep",
                        lambda s: (_ for _ in ()).throw(
                            AssertionError("should not retry")))
    out = gateway_lifecycle.verify_in_session(
        "tok-x", "x", workspace=tmp_path)
    assert calls["n"] == 1               # no retry
    assert out["transient"] is True


# ---------------------------------------------------------------------
# register_session — claim a worker slot for a framework-held session
# (the cleanup mechanical span). None on any failure → caller goes cold.
# ---------------------------------------------------------------------

def test_register_session_returns_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    target = tmp_path / "f.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _MockResponse({"session_token": "abc123"})

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)
    tok = gateway_lifecycle.register_session(
        pipeline_id="cleanup-mech:p:F.lean", target_path=target,
        problem="p", workspace=tmp_path)
    assert tok == "abc123"
    assert captured["url"].endswith("/register")
    assert captured["body"]["pipeline_id"] == "cleanup-mech:p:F.lean"


def test_register_session_missing_target_is_none(tmp_path: Path) -> None:
    tok = gateway_lifecycle.register_session(
        pipeline_id="x", target_path=tmp_path / "nope.lean",
        problem="p", workspace=tmp_path)
    assert tok is None


def test_register_session_pool_exhausted_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """HTTP 500 (no free slot) → None so the gate runs cold, never blocks."""
    target = tmp_path / "f.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")

    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 500, "pool exhausted",
                                     {}, None)

    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen", fake_urlopen)
    tok = gateway_lifecycle.register_session(
        pipeline_id="x", target_path=target, problem="p", workspace=tmp_path)
    assert tok is None


def test_register_session_unreachable_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    target = tmp_path / "f.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    monkeypatch.setattr(
        gateway_lifecycle.urllib.request, "urlopen",
        lambda req, timeout: (_ for _ in ()).throw(_make_urlerror("refused")))
    tok = gateway_lifecycle.register_session(
        pipeline_id="x", target_path=target, problem="p", workspace=tmp_path)
    assert tok is None


# ---------------------------------------------------------------------
# _borrow_order — the pipeline=slot rule's borrow-side half (2026-07-03):
# a borrow probe must prefer UNCLAIMED slots (LRU within each group) and
# reach a registered session's slot only as the last resort. Before this
# ordering existed, plain LRU actively preferred the slot of the pipeline
# that had been thinking longest — the 2026-06-29 slot-thrash shape.
# ---------------------------------------------------------------------

def test_borrow_order_prefers_unclaimed_then_lru() -> None:
    from types import SimpleNamespace as S
    from Tooling.lsp.gateway import _borrow_order
    claimed_old = S(claimed_by="pipe-a", last_used_ts=1.0, name="claimed_old")
    claimed_new = S(claimed_by="pipe-b", last_used_ts=9.0, name="claimed_new")
    free_old = S(claimed_by=None, last_used_ts=2.0, name="free_old")
    free_new = S(claimed_by=None, last_used_ts=8.0, name="free_new")
    order = _borrow_order([claimed_old, free_new, claimed_new, free_old])
    assert [s.name for s in order] == [
        "free_old", "free_new",          # unclaimed first, LRU inside
        "claimed_old", "claimed_new",    # claimed only as fallback
    ]


def test_borrow_order_all_claimed_falls_back_to_lru() -> None:
    from types import SimpleNamespace as S
    from Tooling.lsp.gateway import _borrow_order
    a = S(claimed_by="p1", last_used_ts=5.0)
    b = S(claimed_by="p2", last_used_ts=3.0)
    order = _borrow_order([a, b])
    assert order == [b, a]     # liveness: claimed slots still reachable


def test_kill_stale_gateway_needs_consecutive_dead_pings(monkeypatch):
    """2026-07-19 00:24 rc2: one missed 1s /health window was read as
    "port free", the fresh launch raced the still-alive zombie and lost
    the bind. The wait must demand 3 consecutive dead pings AND a
    refused TCP connect."""
    from Tooling.lsp import lifecycle as gwl
    pings = iter([None,            # transient miss — zombie busy
                  {"backend_ready": True},   # zombie answers again
                  None, None, None])         # actually dead now
    monkeypatch.setattr(gwl, "_ping_health",
                        lambda timeout=1.0: next(pings, None))
    connects = iter([True,   # listener still held at first dead streak?
                     False])  # then released
    monkeypatch.setattr(gwl, "_port_accepts_connect",
                        lambda: next(connects, False))
    monkeypatch.setattr(gwl.time, "sleep", lambda s: None)
    monkeypatch.setattr(gwl.os, "kill",
                        lambda pid, sig: None)
    gwl._kill_stale_gateway(4242)  # returns without raising


def test_kill_stale_gateway_raises_when_zombie_immortal(monkeypatch):
    from Tooling.lsp import lifecycle as gwl
    monkeypatch.setattr(gwl, "_ping_health",
                        lambda timeout=1.0: {"backend_ready": True})
    monkeypatch.setattr(gwl.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(gwl.time, "sleep", lambda s: None)
    t = {"now": 0.0}

    def fake_monotonic():
        t["now"] += 5.0
        return t["now"]
    monkeypatch.setattr(gwl.time, "monotonic", fake_monotonic)
    with pytest.raises(RuntimeError, match="did not release port"):
        gwl._kill_stale_gateway(4242)
