"""Tooling/lsp_gateway.py — module-level smoke + REST + slot pool.

Phase 2: 1 server + W persistent workers + LRU content swap on tool
call. These tests don't spawn a real `lake serve` (integration-level);
they verify the in-memory machinery: tool registration, session
metadata, REST endpoint contract, contextvar plumbing, slot pool LRU
ordering + lock contention.

End-to-end (gateway subprocess + claude HTTP MCP + real lake serve +
real Mathlib elaborate) lives outside the unit suite — see PN run
validation in Phase 2 acceptance.
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


def test_install_windows_event_loop_policy_on_win32(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Windows, the gateway switches asyncio to Selector policy
    before starting uvicorn — works around the
    IocpProactor.accept WinError 64 race observed in SG run #14
    (2026-05-11) which left the listening socket bound but no longer
    accepting connections."""
    import asyncio
    monkeypatch.setattr(lsp_gateway.sys, "platform", "win32")
    calls = {"policy": None}

    def fake_set_policy(p):
        calls["policy"] = p

    monkeypatch.setattr(asyncio, "set_event_loop_policy", fake_set_policy)
    lsp_gateway._install_windows_event_loop_policy()
    assert isinstance(calls["policy"], asyncio.WindowsSelectorEventLoopPolicy)


def test_install_windows_event_loop_policy_noop_on_non_win32(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On non-Windows platforms the helper is a no-op — Selector vs
    Proactor is a Windows-only consideration; Linux/macOS already use
    epoll/kqueue without this issue."""
    import asyncio
    monkeypatch.setattr(lsp_gateway.sys, "platform", "linux")
    calls = {"n": 0}
    monkeypatch.setattr(asyncio, "set_event_loop_policy",
                        lambda p: calls.__setitem__("n", calls["n"] + 1))
    lsp_gateway._install_windows_event_loop_policy()
    assert calls["n"] == 0


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


# ─── Phase 2: slot pool + LRU + lock contention ───────────────────

def _make_fake_slot(slot_id: int, *, loaded: str | None = None,
                    last_used: float = 0.0) -> lsp_gateway.WorkerSlot:
    """Bare WorkerSlot for in-memory tests — no real LSP."""
    return lsp_gateway.WorkerSlot(
        slot_id=slot_id,
        slot_path=Path(f"/fake/slot_{slot_id}.lean"),
        slot_uri=f"file:///fake/slot_{slot_id}.lean",
        loaded_pipeline_id=loaded,
        last_used_ts=last_used,
    )


def test_acquire_slot_hot_path_no_swap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Slot already loaded with pipeline X's content → acquire WITHOUT
    invoking LSP didChange (the hot path). Verify by stubbing backend
    methods to assert they're never called."""
    # Set up fake state: 2 slots, slot[1] loaded with pipe-A.
    slots = [_make_fake_slot(0, loaded=None, last_used=10.0),
             _make_fake_slot(1, loaded="pipe-A", last_used=20.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, *a, **kw): self.calls.append("didChange")
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw):
            self.calls.append("wait_diag")
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="content for pipe-A",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True) as (s, kind):
        assert s.slot_id == 1  # the one loaded with pipe-A
        assert kind == "hot"
    # No didChange / clear calls — pure hot-path acquire.
    assert fake.calls == []


def test_acquire_slot_cold_path_picks_lru(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """No slot loaded with this pipeline → pick least-recently-used
    AND swap content via didChange. LRU = lowest last_used_ts."""
    slots = [_make_fake_slot(0, loaded="pipe-X", last_used=100.0),  # newest
             _make_fake_slot(1, loaded="pipe-Y", last_used=50.0),
             _make_fake_slot(2, loaded=None, last_used=10.0)]   # LRU
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, p, c, v): self.calls.append(("didChange", v))
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-NEW", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="hello",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True) as (s, kind):
        assert s.slot_id == 2  # LRU
        assert s.loaded_pipeline_id == "pipe-NEW"  # marked after swap
        # Slot 2 starts at loaded=None → first-use warmup, not eviction.
        assert kind == "cold_warmup"
    assert ("didChange", 3) in fake.calls  # version bumped from 2 → 3


def test_acquire_slot_skip_swap_in_for_apply_edit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`swap_in=False` (apply_edit case) skips the didChange-to-mirror
    step; caller will overwrite content anyway. Verify no didChange
    is invoked during acquire."""
    slots = [_make_fake_slot(0, loaded="other-pipe", last_used=10.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, *a, **kw): self.calls.append("didChange")
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="hello",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=False) as (s, kind):
        # Got the slot; no swap-in performed.
        assert s.slot_id == 0
        assert kind == "cold_noswap"
    assert "didChange" not in fake.calls
    assert "clear" not in fake.calls


def test_acquire_slot_lock_excludes_concurrent_acquire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When all slots are locked, second acquire blocks (briefly) and
    fails with timeout. This guards the per-slot exclusion contract."""
    slots = [_make_fake_slot(0)]
    slots[0].lock.acquire()  # leak — simulates another thread holding
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def did_change_full(self, *a, **kw): pass
        def clear_diagnostics(self, *a): pass
        def wait_for_diagnostics(self, *a, **kw): pass
    monkeypatch.setattr(lsp_gateway._state, "backend", _FakeBackend())

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="x",
    )
    # Patch the deadline check by monkeypatching time.monotonic to
    # advance fast; we don't want to sit 120s.
    import time as _t
    real_mono = _t.monotonic()
    seq = iter([real_mono, real_mono + 0.05, real_mono + 130.0])
    monkeypatch.setattr(_t, "monotonic", lambda: next(seq))
    with pytest.raises(RuntimeError, match="no slot available"):
        with lsp_gateway._acquire_slot(meta, swap_in=False):
            pass
    slots[0].lock.release()


def test_mcp_tools_are_async_for_event_loop_safety() -> None:
    """Regression guard for the miniF2F 20-problem pilot v2 deadlock
    (2026-05-12 02:51): FastMCP's `call_fn_with_arg_validation` calls
    sync tool bodies INLINE on the asyncio event loop (verified by
    reading the SDK source — `return fn(**args)` with no thread
    pool). Tools that block (every one calls `_acquire_slot` which
    can poll up to 120s) saturate the event loop under concurrent
    load, blocking /register / /release / /health and deadlocking
    the daemon.

    Fix: wrap each `@mcp.tool()` with `_offload_to_thread` so the
    handler is async + dispatches sync work to `asyncio.to_thread`.

    This test asserts ALL four MCP tools are coroutine functions
    (i.e. the `_offload_to_thread` wrapper is in place). If a future
    refactor accidentally removes the decorator from a tool, this
    test catches it before it ships."""
    import inspect
    from Tooling import lsp_gateway as gw

    for name in ("apply_edit", "goal_at", "errors_at", "validate_file"):
        fn = getattr(gw, name)
        assert inspect.iscoroutinefunction(fn), (
            f"MCP tool `{name}` must be a coroutine function "
            f"(wrap with `_offload_to_thread`) so its sync body "
            f"doesn't block the asyncio event loop."
        )


def test_verify_endpoint_offloads_sync_body_to_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Regression guard for the miniF2F 20-problem pilot deadlock
    (2026-05-12): /verify's sync slot-acquire + LSP RPC work must NOT
    run on the asyncio event loop. If it does, concurrent verify
    requests serialize and starve /register / /release / /health
    handlers (the daemon-side `register_session` urlopen hits its
    120s timeout and the dispatcher worker raises TimeoutError).

    Smoke test: the /verify handler must call asyncio.to_thread on
    `_verify_sync`. We patch `_verify_sync` to a marker function and
    confirm it's invoked off the event loop via `asyncio.to_thread`."""
    import asyncio
    from starlette.requests import Request

    invoked_in_thread: dict[str, object] = {}

    def _stub_verify_sync(target, content, *, write_olean, axioms_for,
                          rpc_timeout):
        # Off-thread invocation: in the main test thread our event loop
        # is running; if to_thread was used we land in a *different*
        # thread.
        import threading
        invoked_in_thread["tid"] = threading.get_ident()
        return {"ok": True, "diagnostic_count": 0, "diagnostics": [],
                "olean_written": False, "olean_path": None,
                "axioms": None, "axiom_error": None}

    monkeypatch.setattr(lsp_gateway, "_verify_sync", _stub_verify_sync)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)

    target = tmp_path / "x.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")

    # Build a minimal ASGI request to feed the async handler
    async def _run():
        scope = {
            "type": "http", "method": "POST", "path": "/verify",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        }
        import json
        body = json.dumps({
            "target_path": str(target),
            "write_olean": False,
        }).encode("utf-8")

        sent = []
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(msg):
            sent.append(msg)
        # Use Request to feed the handler
        req = Request(scope, receive=receive, send=send)
        resp = await lsp_gateway.verify(req)
        return resp

    asyncio.run(_run())

    assert "tid" in invoked_in_thread, "_verify_sync was not called"
    import threading
    main_tid = threading.get_ident()
    assert invoked_in_thread["tid"] != main_tid, (
        f"_verify_sync ran on the main thread (tid={main_tid}); "
        f"event loop would have been blocked. Expected asyncio.to_thread "
        f"to dispatch to a worker thread."
    )


def test_session_release_clears_slot_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Releasing a session clears the loaded_pipeline_id marker on
    any slot still bound to that pipeline. The slot's content stays
    in place (next caller's swap will overwrite); only the OWNERSHIP
    label clears."""
    slots = [_make_fake_slot(0, loaded="pipe-A"),
             _make_fake_slot(1, loaded="pipe-B")]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
    )
    with lsp_gateway._state.sessions_lock:
        lsp_gateway._state.sessions["tok-A"] = meta

    lsp_gateway._release_session_internal("tok-A")

    assert slots[0].loaded_pipeline_id is None  # cleared
    assert slots[1].loaded_pipeline_id == "pipe-B"  # untouched
    with lsp_gateway._state.sessions_lock:
        assert "tok-A" not in lsp_gateway._state.sessions
