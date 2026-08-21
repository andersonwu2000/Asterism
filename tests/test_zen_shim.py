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
    out = zen_shim._stream_once("https://opencode.ai/zen/v1",
                                {"model": "x-preview-f-free", "input": []})
    assert out == {"output": [{"type": "message"}], "usage": {}}
    assert captured["body"]["stream"] is True
    # per-upstream model naming: zen keeps its native id...
    assert captured["body"]["model"] == "x-preview-f-free"
    # ...openrouter gets the stealth id
    zen_shim._stream_once("https://openrouter.ai/api/v1",
                          {"model": "x-preview-f-free", "input": []})
    assert captured["body"]["model"] == "stealth/ox-alpha"


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


def test_zen_call_429_goes_straight_to_rescue(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The daily request cap (429) is expected, not an anomaly: no
    # primary retries, no forensics dump — straight to the rescue tier
    # so the fleet degrades instead of parking.
    calls: list[str] = []

    def fake_stream(base, body):
        calls.append(base)
        if base == zen_shim.ZEN:
            raise urllib.error.HTTPError(
                base, 429, "Too Many Requests", None,
                __import__("io").BytesIO(b'{"error":"cap"}'))
        return {"output": ["rescued"], "usage": {}}

    monkeypatch.setattr(zen_shim, "_stream_once", fake_stream)
    dumped: list = []
    monkeypatch.setattr(zen_shim, "_dump_4xx",
                        lambda e, b: dumped.append(1) or e)
    out = zen_shim._zen_call({"model": "x-preview-f-free", "input": []})
    assert out == {"output": ["rescued"], "usage": {}}
    assert calls == [zen_shim.ZEN, zen_shim.ZEN_RESCUE]
    assert not dumped


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
