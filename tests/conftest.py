"""Pytest fixtures shared across test modules."""
from __future__ import annotations

import os
import sqlite3
import pytest

from Tooling.state import db


def pytest_collection_modifyitems(config, items):
    """Drop `real_lake`-marked e2e tests from the default run.

    They spawn a live lake/lean toolchain — slow (seconds to minutes) and only
    runnable where Mathlib is built (the dev workstation). CI runners have no
    Lean, so they cannot run there either; in the routine `pytest` they were
    pure cost — a cold spawn that flakes on timeout, or a `skipif` skip. Keep
    the default run fast and all-green by not collecting them at all (silent —
    no skip/deselect line). Opt in where lake is present with
    `ASTERISM_REAL_LAKE=1 pytest`, or `pytest -m real_lake`."""
    if os.environ.get("ASTERISM_REAL_LAKE") or "real_lake" in (
        config.option.markexpr or ""
    ):
        return
    items[:] = [it for it in items if "real_lake" not in it.keywords]


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
def _skip_lean_contract_gate(monkeypatch: pytest.MonkeyPatch):
    """The daemon-startup framework⇄Lean contract gate (task #12) would run
    its real-toolchain contracts against this conftest's verify stubs and
    fail honestly (stubbed axiom sets are empty) — wedging every e2e that
    drives dispatcher.run(). Unit tests exercise scheduling, not the
    toolchain; the gate has its own Lean-free unit tests
    (test_lean_contracts.py) + real_lake wrappers for the real thing."""
    from Tooling.quality import lean_contracts
    monkeypatch.setattr(lean_contracts, "check_on_startup", lambda ws: True)


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
def _disable_presearch_by_default(monkeypatch: pytest.MonkeyPatch):
    """target-1 pre-search (`_presearch.ensure_presearch`) spawns a per-node
    candidate-lemma agent BEFORE the prover. In unit tests it is irrelevant
    noise, and worse: its spawn reference (`from ..agent import runtime as
    agent`) escaped the pipeline tests' `monkeypatch.setattr(agent,
    "spawn_llm", …)` stub, so it spawned a REAL claude subprocess that blocked
    on subprocess.wait for the full timeout ×3 retry stages — 270s on ONE test,
    ~18 of the 20-min suite. (The import is now unified so it IS stubbable, but
    a running pre-search would still add an extra spawn to exact-count
    assertions.) Disable by default — same rationale as reflection above.
    `test_presearch` tests `_verify`/`presearch_path` directly, not
    `ensure_presearch`, so it is unaffected."""
    monkeypatch.setenv("ASTERISM_PRESEARCH_ENABLED", "false")


@pytest.fixture(autouse=True)
def _stub_gateway_calls_by_default(monkeypatch: pytest.MonkeyPatch,
                                   request: pytest.FixtureRequest):
    """`pipeline._write_mcp_config` POSTs to the long-living gateway
    (`Tooling/lsp_gateway.py`) at /register to obtain a session token,
    and POSTs /release on retry overwrite. Unit tests don't run a real
    gateway, so we stub urllib.request.urlopen to return a fake
    session token + 200 OK release. Production callers (dispatcher
    starts the gateway via gateway_lifecycle.start_gateway) hit the
    real HTTP endpoint.

    `real_lake`-marked tests want the REAL gateway (they opt into a
    live toolchain), so skip stubbing for them entirely."""
    if "real_lake" in request.keywords:
        return
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
def _stub_axiom_probe_by_default(monkeypatch: pytest.MonkeyPatch,
                                 request: pytest.FixtureRequest):
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
    (`tests/test_axiom_invariant.py`) override locally.

    `real_lake`-marked tests want the REAL probe / verify — skip."""
    if "real_lake" in request.keywords:
        return
    def _stub_ok(*args, **kwargs):
        return True, "axioms ok: [] (test stub)"
    from Tooling.pipeline import _axiom
    from Tooling.lsp import lifecycle as _gl
    monkeypatch.setattr(_axiom, "axiom_probe_file", _stub_ok)
    monkeypatch.setattr(_axiom, "axiom_probe", _stub_ok)

    def _stub_verify_file(target_path, *, write_olean=True,
                          axioms_for=None, constants_for=None,
                          decl_info=False,
                          timeout=120.0, workspace=None):
        return {
            "ok": True,
            "diagnostic_count": 0,
            "diagnostics": [],
            "olean_written": write_olean,
            "olean_path": str(target_path),
            "axioms": [] if axioms_for else None,
            "axiom_error": None,
            "pending_anchors": [] if constants_for else None,
            "top_kind": None,
            "top_is_prop": None,
            "top_module": None,
            "closure_error": None,
            # declInfo oracle: the clean-elaborate stub has no decl facts;
            # consumer tests that need them override verify_file locally.
            "decl_info": ({"commands": [], "decls": []} if decl_info
                          else None),
            "decl_info_error": None,
        }
    monkeypatch.setattr(_gl, "verify_file", _stub_verify_file)

    # The own-slot probe path (`_axiom.axiom_gate` / `verify_on_own_slot` when
    # the pipeline holds a session token — which unit tests ALWAYS do, via the
    # /register urlopen stub above). DELEGATE to whatever verify_file is
    # currently stubbed to (resolved at CALL time), so a test that overrides
    # verify_file — to fail a build, inject sorryAx, etc. — also controls the
    # own-slot gate path without having to stub both. CAVEAT: the delegation
    # passes CONTENT where verify_file expects a path — a test stub that
    # discriminates by target_path will misfire on the own-slot path; such
    # tests must stub verify_in_session themselves and discriminate by
    # content (see test_run_forward_dedupe_alias_build_fails_falls_back_…).
    def _stub_verify_in_session(token, content, *, write_olean=False,
                                axioms_for=None, timeout=240.0,
                                workspace=None, _retry_delays=None):
        return _gl.verify_file(
            content, write_olean=write_olean, axioms_for=axioms_for,
            workspace=workspace)
    monkeypatch.setattr(_gl, "verify_in_session", _stub_verify_in_session)
