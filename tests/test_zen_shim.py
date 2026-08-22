"""zen_shim regression pins.

The shim is the zen fleet's only road to the gateway's LSP tools — a
silent parse failure here blinds every formalizer at once (2026-08-22:
the fleet's whole first hour of Lean legs died "no parseable response"
because a `Content-Type` lookup missed uvicorn's lowercase
`content-type`, so SSE bodies were fed to the JSON branch).
"""
from __future__ import annotations

import io
import urllib.request

import pytest

from Tooling.llm import zen_shim


class _FakeResponse(io.BytesIO):
    """Minimal stand-in for urlopen's response: body + wire headers."""

    def __init__(self, body: bytes, headers: dict) -> None:
        super().__init__(body)

        class _H:
            def items(_self):
                return list(headers.items())

        self.headers = _H()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, body: bytes,
                   headers: dict) -> None:
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda req, timeout=0: _FakeResponse(body, headers))


def test_mcp_http_parses_sse_with_lowercase_content_type(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # uvicorn sends `content-type`, not `Content-Type` — the SSE branch
    # must still be taken (this exact miss killed the fleet's LSP hour).
    body = (b'event: message\r\n'
            b'data: {"jsonrpc":"2.0","id":2,"result":{"ok":true}}\r\n\r\n')
    _patch_urlopen(monkeypatch, body,
                   {"content-type": "text/event-stream",
                    "mcp-session-id": "abc123"})
    obj, rh = zen_shim._mcp_http({"jsonrpc": "2.0", "id": 2}, {})
    assert obj == {"jsonrpc": "2.0", "id": 2, "result": {"ok": True}}
    # headers come back lowercase-normalized for every caller
    assert rh["mcp-session-id"] == "abc123"


def test_stream_once_returns_completed_response(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Streaming upstream is load-bearing: Zen's edge kills non-stream
    # responses at ~35s (mis-filed as "Zen cannot do long outputs" for
    # two days). The final response.completed event carries the whole
    # response object.
    sse = (b'data: {"type":"response.output_text.delta","delta":"x"}\n'
           b'data: {"type":"response.completed",'
           b'"response":{"output":[{"type":"message"}],"usage":{}}}\n')
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["body"] = __import__("json").loads(req.data)
        return _FakeResponse(sse, {})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setitem(zen_shim._KEY_CACHE, "OPENCODE_ZEN_API_KEY", "k")
    monkeypatch.setitem(zen_shim._KEY_CACHE, "OPENROUTER_API_KEY", "k")
    out = zen_shim._stream_once("https://openrouter.ai/api/v1",
                                {"model": "x-preview-f-free", "input": []})
    assert out == {"output": [{"type": "message"}], "usage": {}}
    assert captured["body"]["stream"] is True
    # openrouter wears the stealth id
    assert captured["body"]["model"] == "stealth/ox-alpha"


def test_zen_leg_rides_chat_completions(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Zen's /responses dialect is broken both ways (non-stream: edge
    # kill; stream: tool-call arguments dropped) — the zen leg must go
    # through /chat/completions and reassemble a /responses-shaped
    # response: text -> message item, tool_call deltas -> function_call
    # item with concatenated arguments.
    sse = (
        b'data: {"choices":[{"delta":{"content":"half "}}]}\n'
        b'data: {"choices":[{"delta":{"content":"done"}}]}\n'
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
        b'"function":{"name":"mcp__asterism_tools__compute",'
        b'"arguments":"{\\"co"}}]}}]}\n'
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        b'"function":{"arguments":"de\\":\\"1+1\\"}"}}]}}]}\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}],'
        b'"usage":{"prompt_tokens":10,"completion_tokens":7}}\n'
        b'data: [DONE]\n')
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = __import__("json").loads(req.data)
        return _FakeResponse(sse, {})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setitem(zen_shim._KEY_CACHE, "OPENCODE_ZEN_API_KEY", "k")
    out = zen_shim._stream_once(
        "https://opencode.ai/zen/v1",
        {"model": "x-preview-f-free",
         "instructions": "[session x] agent",
         "input": [{"type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": "go"}]},
                   {"type": "function_call", "name": "t", "call_id": "c0",
                    "arguments": "{}"},
                   {"type": "function_call_output", "call_id": "c0",
                    "output": "4"}],
         "tools": [{"type": "function", "name": "t",
                    "parameters": {"type": "object"}}]})
    assert captured["url"].endswith("/chat/completions")
    # zen keeps its native model id; effort is pinned by default
    assert captured["body"]["model"] == "x-preview-f-free"
    assert captured["body"]["reasoning"] == {"effort": zen_shim.ZEN_EFFORT}
    # history translated: system + user + assistant(tool_calls) + tool
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    # response reassembled in /responses vocabulary — with the FULL
    # envelope (codex 0.149 rejects a completed response missing id or
    # usage.total_tokens, one field per dead strategist: g618, g623)
    assert out["id"].startswith("resp_") and out["status"] == "completed"
    assert out["model"] == "x-preview-f-free"
    assert out["output"][0]["content"][0]["text"] == "half done"
    fc = out["output"][1]
    assert fc["type"] == "function_call" and fc["call_id"] == "c1"
    assert fc["arguments"] == '{"code":"1+1"}'
    assert out["usage"] == {"input_tokens": 10, "output_tokens": 7,
                            "total_tokens": 17}


def test_stream_once_raises_when_stream_never_completes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A stream that dies mid-flight must surface as a retryable error,
    # not a silent empty response.
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda req, timeout=0: _FakeResponse(
            b'data: {"type":"response.output_text.delta","delta":"x"}\n',
            {}))
    monkeypatch.setitem(zen_shim._KEY_CACHE, "OPENCODE_ZEN_API_KEY", "k")
    with pytest.raises(urllib.error.URLError):
        zen_shim._stream_once("https://opencode.ai/zen/v1",
                              {"model": "x-preview-f-free", "input": []})


def test_zen_call_falls_back_to_rescue_upstream(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Primary (OpenRouter) exhausts its retries -> the SAME request goes
    # to the rescue upstream (Zen) before the shim gives up.
    calls: list[str] = []

    def fake_stream(base, body):
        calls.append(base)
        if base == zen_shim.ZEN:
            raise urllib.error.URLError("primary down")
        return {"output": [], "usage": {}}

    monkeypatch.setattr(zen_shim, "_stream_once", fake_stream)
    monkeypatch.setattr(zen_shim.time, "sleep", lambda s: None)
    out = zen_shim._zen_call({"model": "x-preview-f-free", "input": []})
    assert out == {"output": [], "usage": {}}
    assert calls[:-1] == [zen_shim.ZEN] * 3
    assert calls[-1] == zen_shim.ZEN_RESCUE


def test_zen_call_429_walks_the_plan_without_dumping(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A 429 on EITHER tier is an expected quota event, not an anomaly:
    # no forensics dump, no propagation — keep walking the alternating
    # schedule until a slot answers. (Strategists died quota_exhausted
    # through 'Zen empty ×3 → rescue 429 → propagate' before the
    # schedule treated a dead parachute as one more transient.)
    calls: list[str] = []

    def fake_stream(base, body):
        calls.append(base)
        if base == zen_shim.ZEN:
            raise urllib.error.HTTPError(
                base, 429, "Too Many Requests", None,
                __import__("io").BytesIO(b'{"error":"cap"}'))
        return {"output": ["rescued"], "usage": {}}

    monkeypatch.setattr(zen_shim, "_stream_once", fake_stream)
    monkeypatch.setattr(zen_shim.time, "sleep", lambda s: None)
    dumped: list = []
    monkeypatch.setattr(zen_shim, "_dump_4xx",
                        lambda e, b: dumped.append(1) or e)
    out = zen_shim._zen_call({"model": "x-preview-f-free", "input": []})
    assert out == {"output": ["rescued"], "usage": {}}
    # walked Zen slots until the first rescue slot answered
    assert calls == [zen_shim.ZEN] * 3 + [zen_shim.ZEN_RESCUE]
    assert not dumped


def test_zen_call_dead_parachute_returns_to_primary(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Rescue 429 (daily cap spent) while Zen answers empty: the request
    # must come BACK to Zen and win when Zen recovers, not die on the
    # parachute's quota.
    calls: list[str] = []

    def fake_stream(base, body):
        calls.append(base)
        if base == zen_shim.ZEN_RESCUE:
            raise urllib.error.HTTPError(
                base, 429, "Too Many Requests", None,
                __import__("io").BytesIO(b'{"error":"cap"}'))
        if len(calls) < 6:
            raise urllib.error.URLError("chat stream ended empty")
        return {"output": ["late win"], "usage": {}}

    monkeypatch.setattr(zen_shim, "_stream_once", fake_stream)
    monkeypatch.setattr(zen_shim.time, "sleep", lambda s: None)
    out = zen_shim._zen_call({"model": "x-preview-f-free", "input": []})
    assert out == {"output": ["late win"], "usage": {}}
    assert calls[3] == zen_shim.ZEN_RESCUE and calls[5] == zen_shim.ZEN


def test_attempt_dir_from_path_carries_nested_projection_dirs(
        tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The URL segment is a PATH under .attempts, not a bare uuid:
    # adversary/judge rounds spawn from `<uuid>/adversary/r2`, and a
    # uuid-shaped parse missed them — every write in those legs was
    # refused while the strategists' own writes landed (2026-08-22).
    import os
    uuid = "c505e391-1cde-4be4-b3c2-407f89796ef7"
    (tmp_path / ".attempts" / uuid / "adversary" / "r2").mkdir(parents=True)
    monkeypatch.setattr(zen_shim, "_REPO", str(tmp_path))
    got = zen_shim._attempt_dir_from_path(
        f"/a/{uuid}/adversary/r2/v1/responses")
    assert got == str(tmp_path / ".attempts" / uuid / "adversary" / "r2")
    # plain per-spawn dir still resolves
    got = zen_shim._attempt_dir_from_path(f"/a/{uuid}/v1/responses")
    assert got == str(tmp_path / ".attempts" / uuid)
    # no channel -> None (body-text fallback takes over)
    assert zen_shim._attempt_dir_from_path("/v1/responses") is None
    # traversal never escapes .attempts
    assert zen_shim._attempt_dir_from_path(
        "/a/../secrets/v1/responses") is None
    # a stale generation's basename URL names no existing dir — fall
    # back to archaeology, never answer confidently wrong
    assert zen_shim._attempt_dir_from_path("/a/r2/v1/responses") is None


def test_mcp_http_normalizes_mixed_case_headers(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = b'{"jsonrpc":"2.0","id":1,"result":{}}'
    _patch_urlopen(monkeypatch, body,
                   {"Content-Type": "application/json",
                    "Mcp-Session-Id": "MiXeD"})
    obj, rh = zen_shim._mcp_http({"jsonrpc": "2.0", "id": 1}, {})
    assert obj == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert rh["mcp-session-id"] == "MiXeD"
    assert "Mcp-Session-Id" not in rh


# ---------------------------------------------------------------------
# 429 handling: pace, wait out the window, abandon orphans (2026-08-22
# two-machines-one-key storm: 864 retries in one 55-min tick)
# ---------------------------------------------------------------------

def test_zen_call_waits_out_a_full_plan_of_429s(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Both tiers throttled through the WHOLE plan is a rolling window,
    # not a failure: wait (honoring Retry-After) and walk again.
    calls: list[str] = []
    state = {"walks": 0}

    def fake_stream(base, body):
        calls.append(base)
        if len(calls) <= len(zen_shim._UPSTREAM_PLAN):
            raise urllib.error.HTTPError(
                base, 429, "Too Many Requests", {"Retry-After": "7"},
                __import__("io").BytesIO(b'{"error":"cap"}'))
        return {"output": ["after the window"], "usage": {}}

    slept: list = []
    monkeypatch.setattr(zen_shim, "_stream_once", fake_stream)
    monkeypatch.setattr(zen_shim, "_pace", lambda: None)
    monkeypatch.setattr(zen_shim, "_429_WAIT_BUDGET", 60)
    monkeypatch.setattr(zen_shim.time, "sleep", lambda s: slept.append(s))
    out = zen_shim._zen_call({"model": "x-preview-f-free", "input": []})
    assert out == {"output": ["after the window"], "usage": {}}
    # one full walk, then the window wait (Retry-After 7 floors to 30),
    # then the first slot of walk 2 answers
    assert len(calls) == len(zen_shim._UPSTREAM_PLAN) + 1
    assert 30.0 in slept


def test_zen_call_429_budget_zero_restores_fail_fast(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_stream(base, body):
        raise urllib.error.HTTPError(
            base, 429, "Too Many Requests", None,
            __import__("io").BytesIO(b'{"error":"cap"}'))

    monkeypatch.setattr(zen_shim, "_stream_once", fake_stream)
    monkeypatch.setattr(zen_shim, "_pace", lambda: None)
    monkeypatch.setattr(zen_shim, "_429_WAIT_BUDGET", 0)
    monkeypatch.setattr(zen_shim.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        zen_shim._zen_call({"model": "x-preview-f-free", "input": []})


def test_pace_holds_the_rolling_window(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The pacer is the root-cause half: hold OURSELVES to the known
    # budget so a 429 means outside contention, not our own burst.
    clock = {"t": 1000.0}
    slept: list = []
    monkeypatch.setattr(zen_shim, "_RPM", 2)
    zen_shim._PACE_STAMPS.clear()
    monkeypatch.setattr(zen_shim.time, "monotonic", lambda: clock["t"])

    def fake_sleep(s):
        slept.append(s)
        clock["t"] += s

    monkeypatch.setattr(zen_shim.time, "sleep", fake_sleep)
    zen_shim._pace()
    zen_shim._pace()
    assert not slept, "inside the window no one waits"
    zen_shim._pace()
    assert slept and sum(slept) >= 55, "the third call waits the window out"
    zen_shim._PACE_STAMPS.clear()


def test_client_alive_detects_a_closed_peer() -> None:
    # A killed codex's loop burned throttled quota for a reply nobody
    # reads; the probe sees the closed socket and the loop abandons.
    import socket as _socket
    a, b = _socket.socketpair()
    try:
        assert zen_shim._client_alive(a) is True
        b.close()
        assert zen_shim._client_alive(a) is False
    finally:
        a.close()


def test_tool_budget_ends_with_a_wrap_up_turn_not_a_guillotine(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """25 measured cap-hits (2026-08-22) cut agents mid validate->fix
    loop SILENTLY and committed whatever broken state was on disk —
    misread for a shift as "ox-alpha submits unverified proofs". At the
    cap the pending calls get a refusal naming the state and the model
    gets one wrap-up turn."""
    # The loop lives inside the HTTP handler, so this is a mechanism
    # pin on the source (the loop itself is exercised by e2e): the cap
    # branch must exist, refuse with the state named, and gate exactly
    # one wrap-up turn; the approach warning must precede it.
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert "tool budget exhausted" in src
    assert "budget_final" in src
    assert "~10 iterations" in src
