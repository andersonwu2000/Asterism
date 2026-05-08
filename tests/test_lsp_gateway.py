"""Tooling/lsp_gateway.py — module-level smoke + REST endpoint shape.

Phase 1: K=1 backend, sticky-by-session via X-Asterism-Session header.
These tests don't spawn a real `lake serve` (heavy + integration); they
verify the in-memory machinery: tool registration, session metadata
storage, REST endpoint contract, contextvar plumbing.

End-to-end (gateway subprocess + claude HTTP MCP) is integration-level
and lives outside the unit test suite — see PN run validation in the
Phase 1 acceptance step.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling import lsp_gateway
from Tooling.lsp_gateway import (
    SessionMetadata,
    _ensure_imports,
    _format_diag,
    _release_session_internal,
    _session_ctx,
    _state,
)


def test_four_tools_registered() -> None:
    """The gateway exposes the same 4 tools as the per-spawn server
    (apply_edit / goal_at / errors_at / validate_file) so agents see
    an identical surface."""
    names = {t.name for t in lsp_gateway.mcp._tool_manager.list_tools()}
    assert names == {"apply_edit", "goal_at", "errors_at",
                     "validate_file"}


def test_format_diag_normalizes_lsp_shape() -> None:
    """LSP-wire format: 0-indexed line/col + numeric severity. Our
    format normalizes to 1-indexed line + named severity for readable
    forensic + agent-friendly output."""
    raw = {
        "range": {"start": {"line": 5, "character": 12}},
        "severity": 1,
        "message": "boom",
    }
    formatted = _format_diag(raw)
    assert formatted == {"line": 6, "col": 12,
                         "severity": "error", "message": "boom"}


def test_ensure_imports_idempotent(tmp_path: Path) -> None:
    """`_ensure_imports` prepends Mathlib + Defs imports when missing.
    Repeat calls don't double-add."""
    pdir = tmp_path / "Problems" / "myprob"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text("namespace Foo\nend Foo\n",
                                     encoding="utf-8")
    bare = "theorem t : True := by sorry"
    once = _ensure_imports(bare, "myprob", tmp_path)
    twice = _ensure_imports(once, "myprob", tmp_path)
    assert "import Mathlib" in once
    assert "import Problems.myprob.Defs" in once
    assert once == twice  # idempotent


def test_session_release_idempotent_unknown_token() -> None:
    """`_release_session_internal` on a token not in the session map
    must be a silent no-op — daemon teardown calls it on stale tokens
    and shouldn't throw."""
    _release_session_internal("nonexistent-token-xyz")  # no raise


def test_current_session_uses_contextvar(tmp_path: Path) -> None:
    """Tool bodies resolve their session via _session_ctx contextvar
    (set by SessionHeaderMiddleware on each HTTP request). Verify the
    plumbing without HTTP: directly set the contextvar, register a
    fake session, confirm `_current_session()` returns it."""
    fake = SessionMetadata(
        pipeline_id="pipe-test",
        target_path=tmp_path / "x.lean",
        problem="test",
        workspace=tmp_path,
        log_path=None,
        file_content="",
        file_version=2,
    )
    token = "test-token-abc"
    with _state.sessions_lock:
        _state.sessions[token] = fake
    try:
        ctx = _session_ctx.set(token)
        try:
            assert lsp_gateway._current_session() is fake
        finally:
            _session_ctx.reset(ctx)
        # Outside the contextvar set: returns None.
        assert lsp_gateway._current_session() is None
    finally:
        with _state.sessions_lock:
            _state.sessions.pop(token, None)


def test_session_header_middleware_sets_and_resets_contextvar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SessionHeaderMiddleware.__call__` reads X-Asterism-Session,
    sets the contextvar, calls the inner ASGI app, then resets. Verify
    the lifecycle: app sees the token, post-call returns to None."""
    seen: list = []

    async def app(scope, receive, send):
        seen.append(_session_ctx.get())

    mw = lsp_gateway.SessionHeaderMiddleware(app)
    scope = {
        "type": "http",
        "headers": [(b"x-asterism-session", b"hdr-token-123")],
    }

    import asyncio
    asyncio.run(mw(scope, lambda: None, lambda x: None))

    assert seen == ["hdr-token-123"]
    # After the middleware returns, the contextvar is back to default.
    assert _session_ctx.get() is None


def test_session_header_middleware_no_header_yields_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requests without X-Asterism-Session (e.g. /health) get None
    on the contextvar; tool calls in that scope correctly report
    'no session'."""
    seen: list = []

    async def app(scope, receive, send):
        seen.append(_session_ctx.get())

    mw = lsp_gateway.SessionHeaderMiddleware(app)
    scope = {"type": "http", "headers": []}

    import asyncio
    asyncio.run(mw(scope, lambda: None, lambda x: None))

    assert seen == [None]
