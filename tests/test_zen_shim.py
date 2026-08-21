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
