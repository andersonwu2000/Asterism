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

import asyncio
import json
from pathlib import Path

import pytest

from Tooling.lsp import gateway as lsp_gateway
from Tooling.lsp.gateway import (
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


# ─── Phase 2: slot pool + 1:1 binding + lock contention ───────────

def _make_fake_slot(
    slot_id: int, *,
    claimed_by: str | None = None,
    content_pipeline_id: str | None = None,
    last_used: float = 0.0,
) -> lsp_gateway.WorkerSlot:
    """Bare WorkerSlot for in-memory tests — no real LSP. Defaults
    leave the slot unclaimed and content-less (post-warmup state)."""
    return lsp_gateway.WorkerSlot(
        slot_id=slot_id,
        slot_path=Path(f"/fake/slot_{slot_id}.lean"),
        slot_uri=f"file:///fake/slot_{slot_id}.lean",
        claimed_by=claimed_by,
        content_pipeline_id=content_pipeline_id,
        last_used_ts=last_used,
    )


def test_acquire_slot_hot_path_no_swap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Pipeline's claimed slot already has its content didChanged in
    (hot state) → acquire returns 'hot' WITHOUT invoking LSP
    didChange. Verify by stubbing backend methods."""
    slots = [_make_fake_slot(0),
             _make_fake_slot(1, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A",
                             last_used=20.0)]
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
        assert s.slot_id == 1  # the slot claimed for pipe-A
        assert kind == "hot"
    # No didChange / clear calls — pure hot-path acquire.
    assert fake.calls == []


def test_acquire_slot_first_tool_call_cold_warmup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """First tool call after register_session: slot is claimed but its
    content_pipeline_id doesn't match yet (still in warmup state or
    holds a prior claim's stale content). Acquire didChanges this
    pipeline's content in and returns 'cold_warmup'."""
    slots = [_make_fake_slot(0),
             _make_fake_slot(1, claimed_by="pipe-NEW",
                             content_pipeline_id=None, last_used=10.0)]
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
        assert s.slot_id == 1               # the claimed slot
        assert s.content_pipeline_id == "pipe-NEW"  # set after swap
        assert kind == "cold_warmup"
    assert ("didChange", 3) in fake.calls   # version bumped from 2 → 3


def test_acquire_slot_skip_swap_in_for_apply_edit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`swap_in=False` (apply_edit case) skips the didChange-to-mirror
    step; caller will overwrite content via its own RPC. Acquire
    returns 'cold_noswap' without invoking didChange."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id=None, last_used=10.0)]
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
        assert s.slot_id == 0
        assert kind == "cold_noswap"
    assert "didChange" not in fake.calls
    assert "clear" not in fake.calls


def test_acquire_slot_no_claim_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """If `_acquire_slot` is called for a pipeline that has no
    `register_session`-claimed slot, fail loudly (rather than silently
    seizing some other pipeline's slot)."""
    slots = [_make_fake_slot(0, claimed_by="pipe-OTHER",
                             content_pipeline_id="pipe-OTHER"),
             _make_fake_slot(1, claimed_by=None)]
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
    with pytest.raises(RuntimeError, match="no slot claimed"):
        with lsp_gateway._acquire_slot(meta, swap_in=False):
            pass


def test_acquire_slot_lock_excludes_concurrent_acquire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When the pipeline's claimed slot is locked (concurrent tool call
    from the same pipeline), second acquire waits briefly then times
    out. Guards the per-slot mutual-exclusion contract."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A")]
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
    import time as _t
    real_mono = _t.monotonic()
    seq = iter([real_mono, real_mono + 0.05, real_mono + 130.0])
    monkeypatch.setattr(_t, "monotonic", lambda: next(seq))
    with pytest.raises(RuntimeError, match="still busy"):
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
    from Tooling.lsp import gateway as gw

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


def test_session_release_clears_slot_claim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Releasing a session clears the `claimed_by` marker on the
    pipeline's claimed slot. `content_pipeline_id` stays in place —
    the next claim will didChange its own content in regardless, so
    eagerly clearing buys nothing."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A"),
             _make_fake_slot(1, claimed_by="pipe-B",
                             content_pipeline_id="pipe-B")]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
    )
    with lsp_gateway._state.sessions_lock:
        lsp_gateway._state.sessions["tok-A"] = meta

    lsp_gateway._release_session_internal("tok-A")

    assert slots[0].claimed_by is None              # released
    assert slots[0].content_pipeline_id == "pipe-A"  # left untouched
    assert slots[1].claimed_by == "pipe-B"          # other slot untouched
    with lsp_gateway._state.sessions_lock:
        assert "tok-A" not in lsp_gateway._state.sessions


def test_register_session_claims_free_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """register_session eagerly claims a free worker slot (1:1 binding).
    The claim is recorded on the first slot whose `claimed_by is None`."""
    target = tmp_path / "x.lean"
    target.write_text("dummy", encoding="utf-8")
    slots = [_make_fake_slot(0, claimed_by="other-pipe"),
             _make_fake_slot(1, claimed_by=None)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)

    token, err = lsp_gateway._register_session_internal(
        pipeline_id="pipe-A", target_path=target,
        problem="p", workspace=tmp_path, log_path=None,
    )
    assert err is None
    assert token
    assert slots[0].claimed_by == "other-pipe"  # unchanged
    assert slots[1].claimed_by == "pipe-A"      # claimed


def _setup_validate_session(monkeypatch, tmp_path, backend):
    """Wire a claimed slot + session + ready backend so `validate_file`
    can run against an in-memory FakeBackend. Returns a reset callback."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A")]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway._state, "backend", backend)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda *a, **kw: None)
    monkeypatch.setattr(lsp_gateway, "_ensure_imports",
                        lambda content, problem, ws: content)
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="theorem t : True := trivial\n",
    )
    with lsp_gateway._state.sessions_lock:
        lsp_gateway._state.sessions["tok-A"] = meta
    ctx = lsp_gateway._session_ctx.set("tok-A")
    return ctx


class _DiagBackend:
    """Minimal backend for validate_file: `wait` behavior is injectable;
    `diagnostics_for` returns a fixed list."""
    def __init__(self, *, wait_raises=None, diags=None):
        self._wait_raises = wait_raises
        self._diags = diags or []
    def clear_diagnostics(self, *a, **kw): pass
    def did_change_full(self, *a, **kw): pass
    def wait_for_diagnostics(self, *a, **kw):
        if self._wait_raises is not None:
            raise self._wait_raises
    def diagnostics_for(self, *a, **kw): return list(self._diags)


def test_validate_file_timeout_reports_indeterminate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """#102 — when elaboration doesn't confirm within the wait budget,
    validate_file must NOT report a false ok:true. It reports ok:false +
    timed_out + an error, even though no error diagnostics arrived."""
    backend = _DiagBackend(wait_raises=TimeoutError("budget"))
    ctx = _setup_validate_session(monkeypatch, tmp_path, backend)
    try:
        out = json.loads(asyncio.run(lsp_gateway.validate_file(
            "theorem t : True := by sorry\n")))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)
    assert out["ok"] is False
    assert out["timed_out"] is True
    assert "error" in out
    assert out["diagnostic_count"] == 0  # no diagnostics, yet not "clean"


def test_validate_file_clean_when_no_diags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Regression guard: the normal path (wait completes, zero error
    diagnostics) still returns ok:true with no timed_out marker."""
    backend = _DiagBackend(wait_raises=None, diags=[])
    ctx = _setup_validate_session(monkeypatch, tmp_path, backend)
    try:
        out = json.loads(asyncio.run(lsp_gateway.validate_file(
            "theorem t : True := trivial\n")))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)
    assert out["ok"] is True
    assert "timed_out" not in out


def test_acquire_slot_borrow_mode_uses_any_free_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Probe mode (`borrow=True`) bypasses the claim check — used by the
    /verify endpoint which has no registered session. Grabs any free
    slot (LRU first), didChanges in, clears content_pipeline_id so
    the slot's registered owner reloads on its next acquire."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A",
                             last_used=20.0),
             _make_fake_slot(1, claimed_by=None,
                             content_pipeline_id=None,
                             last_used=10.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, p, c, v): self.calls.append(("didChange", v))
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="verify:probe-xyz", target_path=tmp_path / "x.lean",
        problem="", workspace=tmp_path, log_path=None,
        file_content="probe content",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True, borrow=True) as (s, kind):
        # LRU is slot 1 (last_used=10.0 < 20.0)
        assert s.slot_id == 1
        assert kind == "cold_warmup"
    # After release: content_pipeline_id cleared so the owner (if any)
    # re-loads on next acquire.
    assert slots[1].content_pipeline_id is None
    # Slot 0 (other pipeline's claim) untouched.
    assert slots[0].claimed_by == "pipe-A"
    assert slots[0].content_pipeline_id == "pipe-A"


def test_acquire_slot_borrow_evicts_when_no_unclaimed_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When all slots are claimed by registered sessions, borrow mode
    still proceeds — it locks any unlocked slot, didChanges the probe
    content, then clears `content_pipeline_id` so the claimed owner
    pays one cold_warmup on its next acquire."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A",
                             last_used=20.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, p, c, v): self.calls.append("didChange")
        def clear_diagnostics(self, *a): pass
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="verify:probe-xyz", target_path=tmp_path / "x.lean",
        problem="", workspace=tmp_path, log_path=None,
        file_content="probe content",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True, borrow=True) as (s, kind):
        assert s.slot_id == 0
        assert kind == "cold_warmup"
    # Owner's claim preserved; content_pipeline_id cleared so the next
    # acquire by pipe-A re-loads pipe-A's content (one cold_warmup).
    assert slots[0].claimed_by == "pipe-A"
    assert slots[0].content_pipeline_id is None


def test_register_session_fails_when_pool_exhausted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """If every worker slot is already claimed (dispatch.pool >
    workers count — a configuration error), register_session refuses
    instead of silently sharing a slot."""
    target = tmp_path / "x.lean"
    target.write_text("dummy", encoding="utf-8")
    slots = [_make_fake_slot(0, claimed_by="pipe-X"),
             _make_fake_slot(1, claimed_by="pipe-Y")]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)

    token, err = lsp_gateway._register_session_internal(
        pipeline_id="pipe-Z", target_path=target,
        problem="p", workspace=tmp_path, log_path=None,
    )
    assert token == ""
    assert err is not None
    assert "pool exhausted" in err


# ---------------------------------------------------------------------
# Stale-claim sweep (#118 follow-up — gateway activity-TTL leak fix)
# ---------------------------------------------------------------------

def _build_fake_pool(monkeypatch: pytest.MonkeyPatch,
                     tmp_path: Path, n: int = 2) -> list:
    """Stub out _state.workers with `n` fresh WorkerSlot rows. Yields
    the slots for inspection. Cleans sessions on exit (per-test)."""
    from Tooling.lsp.gateway import WorkerSlot
    slots = [WorkerSlot(slot_id=i,
                        slot_path=tmp_path / f"slot_{i}.lean",
                        slot_uri=f"file:///slot_{i}",
                        file_version=0)
             for i in range(n)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    return slots


def _make_meta(tmp_path: Path, *, pipeline_id: str,
               last_active: float) -> SessionMetadata:
    return SessionMetadata(
        pipeline_id=pipeline_id,
        target_path=tmp_path / f"{pipeline_id}.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="", last_active=last_active,
    )


def test_sweep_reclaims_session_inactive_beyond_ttl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Session whose `last_active` is older than `_LEASE_TTL_SEC`
    must be popped + its claimed slot freed."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=2)
    now = _t.monotonic()
    stale = _make_meta(tmp_path, pipeline_id="pipe-stale",
                       last_active=now - lsp_gateway._LEASE_TTL_SEC - 1.0)
    slots[0].claimed_by = "pipe-stale"
    with _state.sessions_lock:
        _state.sessions["stale-tok"] = stale
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 1
        assert "stale-tok" not in _state.sessions
        assert slots[0].claimed_by is None
    finally:
        with _state.sessions_lock:
            _state.sessions.pop("stale-tok", None)


def test_sweep_preserves_fresh_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Session with `last_active` newer than TTL stays put."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=2)
    now = _t.monotonic()
    fresh = _make_meta(tmp_path, pipeline_id="pipe-fresh",
                       last_active=now - 1.0)
    slots[0].claimed_by = "pipe-fresh"
    with _state.sessions_lock:
        _state.sessions["fresh-tok"] = fresh
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 0
        assert "fresh-tok" in _state.sessions
        assert slots[0].claimed_by == "pipe-fresh"
    finally:
        with _state.sessions_lock:
            _state.sessions.pop("fresh-tok", None)
        slots[0].claimed_by = None


def test_sweep_handles_mixed_stale_and_fresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Real-world steady-state: some slots are active mid-spawn, some
    are leaks from prior crashes. Sweep reclaims only the stale ones."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=4)
    now = _t.monotonic()
    fresh = _make_meta(tmp_path, pipeline_id="pipe-fresh",
                       last_active=now - 5.0)
    stale1 = _make_meta(tmp_path, pipeline_id="pipe-stale1",
                        last_active=now - lsp_gateway._LEASE_TTL_SEC - 10)
    stale2 = _make_meta(tmp_path, pipeline_id="pipe-stale2",
                        last_active=now - lsp_gateway._LEASE_TTL_SEC - 999)
    slots[0].claimed_by = "pipe-fresh"
    slots[1].claimed_by = "pipe-stale1"
    slots[2].claimed_by = "pipe-stale2"
    # slots[3] genuinely free
    with _state.sessions_lock:
        _state.sessions.update({
            "fresh-tok": fresh, "stale1-tok": stale1, "stale2-tok": stale2,
        })
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 2
        assert "fresh-tok" in _state.sessions
        assert "stale1-tok" not in _state.sessions
        assert "stale2-tok" not in _state.sessions
        # Fresh slot untouched; stale slots freed.
        assert slots[0].claimed_by == "pipe-fresh"
        assert slots[1].claimed_by is None
        assert slots[2].claimed_by is None
        assert slots[3].claimed_by is None
    finally:
        with _state.sessions_lock:
            for t in ("fresh-tok", "stale1-tok", "stale2-tok"):
                _state.sessions.pop(t, None)
        for s in slots:
            s.claimed_by = None


def test_sweep_no_op_on_empty_session_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Steady-state hot path: no sessions → no work, no errors."""
    _build_fake_pool(monkeypatch, tmp_path, n=4)
    assert lsp_gateway._sweep_stale_claims() == 0


def test_sweep_orphan_session_without_matching_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Defensive: session in `sessions` whose pipeline_id matches no
    slot (e.g. mid-state corruption) still gets popped — sweep doesn't
    require slot match to drop the session entry."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=2)
    now = _t.monotonic()
    orphan = _make_meta(tmp_path, pipeline_id="pipe-orphan",
                        last_active=now - lsp_gateway._LEASE_TTL_SEC - 1)
    # No slot has claimed_by="pipe-orphan"
    with _state.sessions_lock:
        _state.sessions["orphan-tok"] = orphan
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 1
        assert "orphan-tok" not in _state.sessions
        # Slots untouched (none matched).
        assert all(s.claimed_by is None for s in slots)
    finally:
        with _state.sessions_lock:
            _state.sessions.pop("orphan-tok", None)
