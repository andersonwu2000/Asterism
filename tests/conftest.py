"""Pytest fixtures shared across test modules."""
from __future__ import annotations

import sqlite3
import pytest

from Tooling import db


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory DB with full schema, ready for cascade tests."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _disable_reflection_by_default(monkeypatch: pytest.MonkeyPatch):
    """Most tests stub `agent.spawn_llm` and assert the exact number of
    spawn invocations (cold + warm retries + F55 postmortem). The
    Phase-7 reflection spawn (BRIEF/LESSONS feature) would add one more
    spawn per terminal pipeline, breaking those counts. Disable by
    default; tests that specifically exercise reflection re-enable via
    `monkeypatch.delenv` or a localized setenv."""
    monkeypatch.setenv("ASTERISM_LESSONS_REFLECTION_ENABLED", "false")


@pytest.fixture(autouse=True)
def _stub_gateway_calls_by_default(monkeypatch: pytest.MonkeyPatch):
    """`pipeline._write_mcp_config` POSTs to the long-living gateway
    (`Tooling/lsp_gateway.py`) at /register to obtain a session token,
    and POSTs /release on retry overwrite. Unit tests don't run a real
    gateway, so we stub urllib.request.urlopen to return a fake
    session token + 200 OK release. Production callers (dispatcher
    starts the gateway via gateway_lifecycle.start_gateway) hit the
    real HTTP endpoint."""
    import io
    import urllib.request

    class _FakeResp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self._body

    def _fake_urlopen(req, timeout=None):
        # Fake responses for the endpoints framework code hits.
        url = getattr(req, "full_url", str(req))
        if url.endswith("/register"):
            return _FakeResp(b'{"session_token": "test-stub-token"}')
        if "/release/" in url:
            return _FakeResp(b'{"ok": true}')
        if url.endswith("/verify"):
            # Verify-unification: framework's gateway-side verify
            # entry point. Default stub passes — tests that exercise
            # the failure path must override the higher-level
            # `gateway_lifecycle.verify_file` directly. (HTTP-level
            # stub is kept as belt-and-braces in case a test forgets
            # to patch the function-level call.)
            return _FakeResp(
                b'{"ok": true, "diagnostic_count": 0, "diagnostics": [],'
                b' "olean_written": true, "olean_path": null,'
                b' "axioms": null, "axiom_error": null}'
            )
        # Anything else (e.g. /health from gateway_lifecycle.start_gateway)
        # — raise URLError so tests don't accidentally see a "fake healthy"
        # gateway. End-to-end tests that need start_gateway to work must
        # stub it directly.
        raise urllib.error.URLError("(test) no real gateway running")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)


@pytest.fixture(autouse=True)
def _stub_axiom_probe_by_default(monkeypatch: pytest.MonkeyPatch):
    """Builder / verify_strategy / `_try_promote_sorry_free` run a real
    `#print axioms <name>` probe at promote time. After the verify-
    unification migration this goes through `gateway_lifecycle.verify_file`,
    which needs the gateway running + a real Lean toolchain. Unit tests
    don't provide that, so stub two layers:

      1. `_axiom.axiom_probe(_file)` — direct callers (Builder Phase 1
         hint, library.promote, etc.) bypass the gateway entirely.
      2. `gateway_lifecycle.verify_file` — verify_strategy / Builder
         Phase 2 verify go through this directly. Stub returns the
         shape `verify_file` produces on a clean elaborate.

    Tests exercising axiom-violation rejection
    (`tests/test_axiom_invariant.py`) override locally."""
    def _stub_ok(*args, **kwargs):
        return True, "axioms ok: [] (test stub)"
    from Tooling.pipeline import _axiom
    from Tooling import gateway_lifecycle as _gl
    monkeypatch.setattr(_axiom, "axiom_probe_file", _stub_ok)
    monkeypatch.setattr(_axiom, "axiom_probe", _stub_ok)

    def _stub_verify_file(target_path, *, write_olean=True,
                          axioms_for=None, timeout=120.0,
                          workspace=None):
        return {
            "ok": True,
            "diagnostic_count": 0,
            "diagnostics": [],
            "olean_written": write_olean,
            "olean_path": str(target_path),
            "axioms": [] if axioms_for else None,
            "axiom_error": None,
        }
    monkeypatch.setattr(_gl, "verify_file", _stub_verify_file)
