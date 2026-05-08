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
        if url.endswith("/check_build"):
            # Phase 2.5: framework calls /check_build instead of
            # `lake build`. Default stub passes — tests that exercise
            # the failure path must override this fixture locally.
            return _FakeResp(
                b'{"ok": true, "diagnostic_count": 0, "diagnostics": []}'
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
    `lake env lean … #print axioms <name>` probe at promote time. That
    needs a real Lean toolchain + a buildable workspace, which unit
    tests don't provide. Stub at the patched call sites so unit tests
    exercise mark-proved logic without paying the probe overhead.

    Tests that specifically exercise axiom-violation rejection
    (`tests/test_axiom_invariant.py`) override this fixture by
    monkeypatching to a False-returning stub locally."""
    def _stub_ok(*args, **kwargs):
        return True, "axioms ok: [] (test stub)"
    from Tooling.pipeline import _axiom
    from Tooling import verify as _verify_mod
    from Tooling.pipeline import builder as _builder_mod
    from Tooling.pipeline import backward as _backward_mod
    monkeypatch.setattr(_axiom, "axiom_probe_file", _stub_ok)
    monkeypatch.setattr(_axiom, "axiom_probe", _stub_ok)
    # The call sites import via `_axiom.axiom_probe_file`; patching the
    # module-level attribute above suffices for those. `verify.py` uses
    # the symbol via a module-level `from ._axiom import …` so that
    # binding is captured at import — patch it on the verify module too.
    monkeypatch.setattr(_verify_mod, "axiom_probe_file", _stub_ok)
    # Builder + Backward use `_axiom.axiom_probe_file` (via module attr),
    # so the _axiom monkeypatch is enough; explicit re-patches kept off
    # the fast path.
    _ = (_builder_mod, _backward_mod)  # silence unused-import lint
