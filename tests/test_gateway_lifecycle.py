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

# Capture the REAL verify_file before any test's conftest autouse
# replaces it with a stub. Each test below restores this via the
# module-local autouse `_restore_real_verify_file` so we exercise the
# actual retry-with-backoff path, not the conftest happy-path stub.
_REAL_VERIFY_FILE = gateway_lifecycle.verify_file


@pytest.fixture(autouse=True)
def _restore_real_verify_file(monkeypatch: pytest.MonkeyPatch):
    """Override conftest's `_stub_axiom_probe_by_default` for this file
    only — we need the real verify_file body to test its retry / error
    classification logic. Applied after conftest's autouse, so this
    monkeypatch wins."""
    monkeypatch.setattr(gateway_lifecycle, "verify_file", _REAL_VERIFY_FILE)


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
    """Healthy gateway whose workers_total == dispatch.pool → reused (no
    relaunch, no kill)."""
    monkeypatch.setattr(gateway_lifecycle, "_ping_health",
        lambda timeout=1.0: {"backend_ready": True, "workers_total": 4,
                             "pid": 999})
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
            return {"backend_ready": True, "workers_total": 2, "pid": 777}
        return {"backend_ready": True, "workers_total": 4, "pid": 888}
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
