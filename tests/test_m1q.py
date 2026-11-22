"""Slice 1q: the log says who calls the connector: the user agent, the names of the x- headers, the client's name at
initialize and the names of a tool call's _meta; their values only while the server is told to trace.

    python -m pytest tests/test_m1q.py -q
"""
from __future__ import annotations

import json

import httpx

from test_m1b import ENV, SLUG, build_world, connector_token

UA, SECRET_HEADER, META_VALUE, CITY = "probe-agent/1.0", "header-value-123", "codex-probe-value", "Taipei"


def call(srv, token, session, method, params):
    h = {"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + token, "User-Agent": UA,
         "x-openai-session": session, "X-Probe-Header": SECRET_HEADER}
    r = httpx.post(f"{srv.url}/{SLUG}/mcp", headers=h, timeout=30,
                   json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    assert r.status_code == 200, r.text
    return r.json()


def both_calls(world, session) -> str:
    token = connector_token(world.srv, world.alice)
    call(world.srv, token, session, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                   "clientInfo": {"name": "probe-client", "version": "9.9"}})
    call(world.srv, token, session, "tools/call", {"name": "whoami", "arguments": {},
                                                   "_meta": {"openai/userAgent": META_VALUE, "zeta": {"city": CITY}}})
    return token


def lines(world, method) -> list[dict]:
    text = (world.srv.data / "log.jsonl").read_text(encoding="utf-8")
    out = [json.loads(x) for x in text.splitlines() if x.strip()]
    return [e for e in out if e.get("event") == "mcp_call" and e.get("method") == method and e.get("ua") == UA]


def test_the_log_names_who_called_and_keeps_the_values_out(tmp_path):
    w = build_world(tmp_path / "q1")
    try:
        token = both_calls(w, "conv-q1")
        init, tool = lines(w, "initialize"), lines(w, "tools/call")
        assert init and tool, "both calls are written down with their user agent"
        assert init[-1]["client"] == "probe-client/9.9"
        assert {"x-openai-session", "x-probe-header"} <= set(init[-1]["hdr"]) and init[-1]["hdr"] == sorted(init[-1]["hdr"])
        assert tool[-1]["meta"] == ["openai/userAgent", "zeta"] and tool[-1]["tool"] == "whoami"
        assert "meta" not in init[-1] and "client" not in tool[-1] and "trace" not in tool[-1]
        log = (w.srv.data / "log.jsonl").read_text(encoding="utf-8")
        for hidden in (SECRET_HEADER, META_VALUE, CITY, "conv-q1", token):
            assert hidden not in log, hidden
    finally:
        w.srv.stop()


def test_values_are_written_only_while_tracing(tmp_path):
    w = build_world(tmp_path / "q2", dict(ENV, ASTERISM_MCP_TRACE="1"))
    try:
        token = both_calls(w, "conv-q2")
        t = lines(w, "tools/call")[-1]["trace"]
        assert t["meta"]["openai/userAgent"] == META_VALUE and CITY in t["meta"]["zeta"]
        assert t["hdr"]["x-probe-header"] == SECRET_HEADER
        seen = t["hdr"]["x-openai-session"]
        assert len(seen) == 8 and all(c in "0123456789abcdef" for c in seen), "the session only as a short digest"
        log = (w.srv.data / "log.jsonl").read_text(encoding="utf-8")
        assert "conv-q2" not in log and token not in log
    finally:
        w.srv.stop()
