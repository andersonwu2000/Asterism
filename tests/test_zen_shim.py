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
    gets a wrap-up turn."""
    # The loop lives inside the HTTP handler, so this is a mechanism
    # pin on the source (the loop itself is exercised by e2e): the cap
    # branch must exist, refuse with the state named, and gate the
    # wrap-up; the approach warning must precede it.
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert "tool budget exhausted" in src
    assert "budget_final" in src
    assert "~10 iterations" in src


def test_wrap_up_turn_can_still_write_its_deliverable() -> None:
    """The first wrap-up shape told the agent to finish and refused
    even write_file — Group 682's strategist obeyed literally: replied
    a tidy final status, wrote no decision.json, died agent_no_output
    (2026-08-24). The teaching message must name only reachable
    actions: write-shaped calls stay executable for a bounded number of
    wrap-up iterations."""
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert zen_shim._WRAPUP_WRITE_TOOLS == {
        "write_file", "apply_edit", "withdraw_stub"}
    assert zen_shim._WRAPUP_WRITE_ITERS >= 1
    # the refusal must advertise the write window it grants
    assert "still run for up to" in src
    # and the wrap-up branch must consult the whitelist
    assert "_WRAPUP_WRITE_TOOLS for it in mine" in src


def test_lookup_crawl_nudge_rearms_every_streak_window() -> None:
    """One nudge per request was calibrated for 80-iteration turns; at
    the 200 cap Group 682's strategist got its single nudge at iter 12
    and crawled loogle unchallenged to the cap (2026-08-24). The nudge
    re-fires on every 12-long lookup-only streak, and it branches on
    the declared toolset (owner call 2026-08-25): Lean-writing seats
    get the write-first check (validate_file, exact?), NL seats are
    told verified names are not their deliverable — the old single
    text spoke patch-language to a strategist with no patch."""
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert "lookup_streak % 12 == 0" in src
    assert "crawl_nudged" not in src, "the once-per-request latch is gone"
    flat = " ".join(src.replace('"', "").split())
    assert "write your deliverable NOW" in flat          # LSP branch
    assert "by exact?" in flat                           # …teaches exact?
    assert "NOT your deliverable" in flat                # NL branch
    assert "has_lsp = any(t.startswith(LSP_NS" in src    # seat signal


def test_channel_choice_reads_env_then_dotenv_then_default(
        tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The upstream choice used to live only in the launching shell's
    environment: a shim restart without the exported vars silently
    reverted the fleet to the default upstream. It now falls back to
    .env (where the channel keys already live); env still wins."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("ASTERISM_ZEN_UPSTREAM=https://dotenv.example/v1\n",
                      encoding="utf-8")
    monkeypatch.delenv("ASTERISM_ZEN_UPSTREAM", raising=False)
    assert zen_shim._cfg("ASTERISM_ZEN_UPSTREAM", "https://default/v1",
                         env_path=str(dotenv)) == "https://dotenv.example/v1"
    monkeypatch.setenv("ASTERISM_ZEN_UPSTREAM", "https://env.example/v1")
    assert zen_shim._cfg("ASTERISM_ZEN_UPSTREAM", "https://default/v1",
                         env_path=str(dotenv)) == "https://env.example/v1"
    monkeypatch.delenv("ASTERISM_ZEN_UPSTREAM", raising=False)
    assert zen_shim._cfg("ASTERISM_ZEN_UPSTREAM", "https://default/v1",
                         env_path=str(tmp_path / "absent")) == \
        "https://default/v1"


def test_the_concurrency_gate_is_fifo_with_direct_handoff() -> None:
    """The first cut polled acquire(timeout=5) and pollers re-joined at
    the back — mid-iteration spawns re-acquired instantly and starved
    the queued ones for 30+ minutes while queue-side heartbeats dressed
    it up as liveness (2026-08-22). The slot must pass head-first."""
    import threading as th
    import collections as co
    # isolate module state — adaptive growth OFF: >60s after module
    # import the grow interval has lapsed and a release with waiters
    # adds a slot, waking BOTH queued threads at once (exactly the
    # adaptive feature; this test pins the FIFO handoff, not it).
    old = (zen_shim._CONC_FREE, list(zen_shim._CONC_WAITERS),
           zen_shim._CONC_AUTO)
    zen_shim._CONC_WAITERS.clear()
    zen_shim._CONC_FREE = 1
    zen_shim._CONC_AUTO = False
    try:
        zen_shim._conc_acquire(None)          # takes the only slot
        got: list = []
        order = []

        def waiter(name):
            zen_shim._conc_acquire(None)
            order.append(name)
            got.append(name)

        t1 = th.Thread(target=waiter, args=("first",), daemon=True)
        t1.start()
        import time as _t
        _t.sleep(0.1)
        t2 = th.Thread(target=waiter, args=("second",), daemon=True)
        t2.start()
        _t.sleep(0.1)
        assert not got, "both queued behind the held slot"
        zen_shim._conc_release()              # head-first: 'first'
        t1.join(timeout=3)
        assert order == ["first"]
        # a barger cannot jump the remaining queue
        zen_shim._conc_release()
        t2.join(timeout=3)
        assert order == ["first", "second"]
        zen_shim._conc_release()
    finally:
        zen_shim._CONC_FREE, waiters = old[0], old[1]
        zen_shim._CONC_AUTO = old[2]
        zen_shim._CONC_WAITERS.clear()
        zen_shim._CONC_WAITERS.extend(waiters)


def test_channel_path_carries_the_turn_time_budget(tmp_path, monkeypatch):
    """At ~20-30s an iteration a 1800s formalizer buys only 65-90 of
    the 200-iteration cap — the wrap-up never fired and turns died at
    the wall salvaging half-states (7 timeouts in one 37-min window,
    friend fleet 2026-08-22). The seat's budget rides the URL."""
    import os as _os
    uuid = "c505e391-1cde-4be4-b3c2-407f89796ef7"
    (tmp_path / ".attempts" / uuid).mkdir(parents=True)
    monkeypatch.setattr(zen_shim, "_REPO", str(tmp_path))
    d, c, b = zen_shim._channel_of_path(f"/a/{uuid}/b/1500/v1/responses")
    assert d == str(tmp_path / ".attempts" / uuid) and b == 1500
    assert c is None
    # budget-less URLs (older generations) keep working
    d2, c2, b2 = zen_shim._channel_of_path(f"/a/{uuid}/v1/responses")
    assert d2 == d and b2 is None


def test_channel_path_carries_the_tool_cwd(tmp_path, monkeypatch):
    """The shim runs tools in-process, so the spawn's problem dir must
    ride the URL (`/c/`) — without it bare problem-file reads resolved
    against the shim's cwd and the basename fallback walked into
    FOREIGN attempts (both fleets, 2026-08-24)."""
    uuid = "c505e391-1cde-4be4-b3c2-407f89796ef7"
    (tmp_path / ".attempts" / uuid / "_presearch").mkdir(parents=True)
    (tmp_path / "Problems" / "Erdos" / "p143").mkdir(parents=True)
    monkeypatch.setattr(zen_shim, "_REPO", str(tmp_path))
    d, c, b = zen_shim._channel_of_path(
        f"/a/{uuid}/_presearch/c/Problems/Erdos/p143/b/315/v1/responses")
    assert d == str(tmp_path / ".attempts" / uuid / "_presearch")
    assert c == str(tmp_path / "Problems" / "Erdos" / "p143")
    assert b == 315
    # the cwd segment is FENCED: outside Problems/ it is dropped,
    # never trusted
    _, c2, _ = zen_shim._channel_of_path(
        f"/a/{uuid}/_presearch/c/Tooling/llm/b/315/v1/responses")
    assert c2 is None
    _, c3, _ = zen_shim._channel_of_path(
        f"/a/{uuid}/_presearch/c/Problems/../Tooling/b/315/v1/responses")
    assert c3 is None


def test_lsp_session_rehandshakes_when_the_token_changes(
        tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A permanent (sid, token) cache outlived a rewritten token: the
    shim kept answering with the dead pair and every LSP call came back
    "no session" for the rest of the run (friend-fleet report,
    2026-08-23). The token is read fresh each call; a changed token
    re-handshakes."""
    calls: list = []

    def fake_mcp(payload, hdr):
        calls.append(payload.get("method"))
        if payload.get("method") == "initialize":
            return {"result": {}}, {"mcp-session-id": f"sid{len(calls)}"}
        return None, {}

    monkeypatch.setattr(zen_shim, "_mcp_http", fake_mcp)
    zen_shim._LSP_SESSIONS.clear()
    att = tmp_path / "att"
    att.mkdir()
    (att / "_gateway_session.token").write_text("tok1", encoding="utf-8")
    s1 = zen_shim._lsp_session_for(str(att))
    assert s1 is not None and s1[1] == "tok1"
    zen_shim._lsp_session_for(str(att))
    assert calls.count("initialize") == 1, "same token stays cached"
    (att / "_gateway_session.token").write_text("tok2", encoding="utf-8")
    s2 = zen_shim._lsp_session_for(str(att))
    assert s2 is not None and s2[1] == "tok2"
    assert calls.count("initialize") == 2, "new token re-handshakes"
    zen_shim._LSP_SESSIONS.clear()


def test_lsp_tool_evicts_and_retries_once_on_a_session_error(
        tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A gateway generation swap invalidates every cached sid, and the
    shim is a detached long-liver now: without eviction the poisoned
    entry answered errors until a shim restart. A JSON-RPC-level error
    from tools/call is the session layer speaking (tool failures ride
    inside `result`) — evict, re-handshake, retry ONCE."""
    att = tmp_path / "att"
    att.mkdir()
    (att / "_gateway_session.token").write_text("tok", encoding="utf-8")
    zen_shim._LSP_SESSIONS.clear()
    zen_shim._LSP_SESSIONS[str(att)] = ("dead-sid", "tok")

    def fake_mcp(payload, hdr):
        m = payload.get("method")
        if m == "initialize":
            return {"result": {}}, {"mcp-session-id": "fresh-sid"}
        if m == "notifications/initialized":
            return None, {}
        if hdr.get("Mcp-Session-Id") == "dead-sid":
            return ({"error": {"code": -32001,
                               "message": "session not found"}}, {})
        return ({"result": {"content": [{"type": "text",
                                         "text": "ok!"}]}}, {})

    monkeypatch.setattr(zen_shim, "_mcp_http", fake_mcp)
    out = zen_shim._run_lsp_tool("validate_file", {}, str(att))
    assert out == "ok!"
    assert zen_shim._LSP_SESSIONS[str(att)][0] == "fresh-sid"
    zen_shim._LSP_SESSIONS.clear()


def test_run_tool_context_is_request_local_not_process_global(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The env-pin under a global lock serialized every tool call — one
    28-minute grep starved twelve spawns (2026-08-23). Two concurrent
    _run_tool calls must each see their OWN attempt dir, in parallel,
    with process env untouched."""
    import os as _os
    import threading
    import time as _time
    from Tooling.llm.spawn_guard import current_attempt_dir

    seen: dict = {}
    gate = threading.Barrier(2, timeout=10)

    class _FakeTools:
        @staticmethod
        def snoop() -> str:
            gate.wait()          # both calls INSIDE the tool at once —
            _time.sleep(0.05)    # impossible under the old global lock
            return str(current_attempt_dir())

    monkeypatch.setattr(zen_shim, "_tools_module", lambda: _FakeTools)

    def run(tag: str, d: str) -> None:
        seen[tag] = zen_shim._run_tool("snoop", {}, d)

    t1 = threading.Thread(target=run, args=("a", "D:/att/a"))
    t2 = threading.Thread(target=run, args=("b", "D:/att/b"))
    t1.start(); t2.start(); t1.join(10); t2.join(10)
    assert seen == {"a": "D:/att/a", "b": "D:/att/b"}
    assert not _os.environ.get("ASTERISM_SPAWN_ATTEMPT_DIR")


def test_tools_snapshot_names_the_running_call_and_its_age(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """With the lock gone a wedged call no longer blocks the channel —
    the oldest-call age in the snapshot is how a leak is FOUND."""
    import threading
    started = threading.Event()
    release = threading.Event()

    class _FakeTools:
        @staticmethod
        def slowpoke() -> str:
            started.set()
            release.wait(10)
            return "done"

    monkeypatch.setattr(zen_shim, "_tools_module", lambda: _FakeTools)
    t = threading.Thread(
        target=zen_shim._run_tool, args=("slowpoke", {}, None))
    t.start()
    assert started.wait(10)
    snap = zen_shim._tools_snapshot()
    assert [r["tool"] for r in snap["tools_running"]] == ["slowpoke"]
    assert snap["oldest_tool_age_sec"] >= 0
    release.set()
    t.join(10)
    assert zen_shim._tools_snapshot()["tools_running"] == []


# --------------------------------------------------------------- adaptive gate

def _gate_state():
    return (zen_shim._CONC_CAP, zen_shim._CONC_FREE,
            list(zen_shim._CONC_WAITERS), zen_shim._CONC_LAST_SHRINK,
            zen_shim._CONC_LAST_GROW, zen_shim._CONC_AUTO)


def _gate_restore(st) -> None:
    (zen_shim._CONC_CAP, zen_shim._CONC_FREE, waiters,
     zen_shim._CONC_LAST_SHRINK, zen_shim._CONC_LAST_GROW,
     zen_shim._CONC_AUTO) = st[0], st[1], st[2], st[3], st[4], st[5]
    zen_shim._CONC_WAITERS.clear()
    zen_shim._CONC_WAITERS.extend(st[2])


def test_adaptive_gate_halves_on_concurrency_429_with_floor() -> None:
    """The upstream's own concurrency verdict is the ONE shrink signal
    (subscription changes must never need a hand-tuned number,
    2026-08-24). Multiplicative decrease, never below the floor."""
    st = _gate_state()
    try:
        zen_shim._CONC_AUTO = True
        zen_shim._CONC_WAITERS.clear()
        zen_shim._CONC_CAP = 16
        zen_shim._CONC_FREE = 16
        zen_shim._conc_note_concurrency_429()
        assert zen_shim._CONC_CAP == 8
        assert zen_shim._CONC_FREE == 8          # debt applied symmetrically
        assert zen_shim._CONC_LAST_SHRINK > 0
        zen_shim._CONC_CAP = zen_shim._CONC_FLOOR
        zen_shim._CONC_FREE = zen_shim._CONC_FLOOR
        zen_shim._conc_note_concurrency_429()
        assert zen_shim._CONC_CAP == zen_shim._CONC_FLOOR
    finally:
        _gate_restore(st)


def test_adaptive_gate_shrink_debt_repays_before_waking_the_queue() -> None:
    """A shrink below the in-flight count must not tear anything down:
    releases repay the negative balance first, and only then does the
    queue head get a slot."""
    import threading as th
    st = _gate_state()
    try:
        zen_shim._CONC_AUTO = True
        zen_shim._CONC_WAITERS.clear()
        zen_shim._CONC_CAP = 4
        zen_shim._CONC_FREE = 0                  # four in flight
        zen_shim._CONC_LAST_SHRINK = 0.0
        got: list = []

        def waiter():
            zen_shim._conc_acquire(None)
            got.append("ran")

        t = th.Thread(target=waiter, daemon=True)
        t.start()
        import time as _t
        _t.sleep(0.1)
        zen_shim._conc_note_concurrency_429()    # cap 4→2, free 0→-2
        assert zen_shim._CONC_CAP == 2
        assert zen_shim._CONC_FREE == -2
        zen_shim._conc_release()                 # repay: -1
        zen_shim._conc_release()                 # repay: 0
        _t.sleep(0.1)
        assert not got, "queue must wait until the debt is repaid"
        zen_shim._conc_release()                 # head-first handoff
        t.join(timeout=3)
        assert got == ["ran"]
    finally:
        _gate_restore(st)


def test_adaptive_gate_grows_only_under_queue_and_clean_window() -> None:
    """Additive increase needs REAL demand (a waiter in line) and a
    clean window (no recent shrink, one step per interval). An idle
    release never probes upward; a fresh shrink pins the cap down."""
    import threading as th
    import time as _t
    st = _gate_state()
    try:
        zen_shim._CONC_AUTO = True
        zen_shim._CONC_WAITERS.clear()
        zen_shim._CONC_CAP = 1
        zen_shim._CONC_FREE = 1
        zen_shim._CONC_LAST_SHRINK = 0.0
        zen_shim._CONC_LAST_GROW = 0.0           # interval long past
        zen_shim._conc_acquire(None)             # the one slot is busy
        zen_shim._conc_release()                 # no waiters -> no grow
        assert zen_shim._CONC_CAP == 1
        zen_shim._conc_acquire(None)
        got: list = []

        def waiter():
            zen_shim._conc_acquire(None)
            got.append("ran")

        t = th.Thread(target=waiter, daemon=True)
        t.start()
        _t.sleep(0.1)
        zen_shim._conc_release()                 # queued demand -> +1
        t.join(timeout=3)
        assert zen_shim._CONC_CAP == 2
        assert got == ["ran"]
        # inside a shrink cooldown the same demand must NOT grow
        zen_shim._CONC_WAITERS.clear()
        zen_shim._CONC_FREE = 0
        zen_shim._CONC_LAST_SHRINK = _t.time()
        zen_shim._CONC_LAST_GROW = 0.0
        t2 = th.Thread(target=waiter, daemon=True)
        t2.start()
        _t.sleep(0.1)
        zen_shim._conc_release()
        t2.join(timeout=3)
        assert zen_shim._CONC_CAP == 2, "cooldown must hold the cap"
        zen_shim._conc_release()
    finally:
        _gate_restore(st)


def test_pinned_gate_never_adapts_and_zero_disables() -> None:
    """ASTERISM_ZEN_CONCURRENCY set = operator pin: no shrink, no
    grow — the old semantics survive verbatim, including 0 = no gate."""
    st = _gate_state()
    old_conc = zen_shim._CONCURRENCY
    try:
        zen_shim._CONC_AUTO = False
        zen_shim._CONC_WAITERS.clear()
        zen_shim._CONC_CAP = 5
        zen_shim._CONC_FREE = 5
        zen_shim._conc_note_concurrency_429()
        assert zen_shim._CONC_CAP == 5, "a pinned cap never shrinks"
        zen_shim._CONCURRENCY = 0
        assert not zen_shim._conc_enabled()
        zen_shim._CONCURRENCY = 5
        assert zen_shim._conc_enabled()
    finally:
        zen_shim._CONCURRENCY = old_conc
        _gate_restore(st)


def test_only_primary_tier_concurrency_429_reaches_the_gate() -> None:
    """Mechanism pin on the source (house style, see the tool-budget
    pin above): the shrink hook must be keyed on the 429 BODY naming
    'concurrent' AND must exclude the rescue tier — OpenRouter's 429s
    say nothing about the Nous account's concurrency."""
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert 'base != ZEN_RESCUE and b"concurrent" in body_head.lower()' in src
    assert "_conc_note_concurrency_429()" in src


def test_port_bind_is_exclusive_only_where_exclusivity_is_real() -> None:
    """Windows SO_REUSEADDR admits a SECOND live listener (the 08-22
    double-bind); POSIX's does not — there it only unblocks a restart
    from a dead process's TIME_WAIT remnants, and hard exclusivity
    makes a systemd restart strike out on its StartLimit (Oracle
    boarding, 2026-08-24). The flag must be platform-conditional."""
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert 'allow_reuse_address = (os.name != "nt")' in src


def test_zen_leg_surfaces_reasoning_as_a_responses_item(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The upstream streams the thinking phase (`delta.reasoning`)
    alongside the answer; dropping it made zen the one black-box seat
    (owner call 2026-08-24). It must come back as a Responses-API
    reasoning item, FIRST, so codex records it in the rollout jsonl —
    and the usage passthrough must carry reasoning_tokens."""
    sse = (
        b'data: {"choices":[{"delta":{"reasoning":"think "}}]}\n'
        b'data: {"choices":[{"delta":{"reasoning":"hard"}}]}\n'
        b'data: {"choices":[{"delta":{"content":"answer"}}]}\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
        b'"usage":{"prompt_tokens":5,"completion_tokens":9,'
        b'"completion_tokens_details":{"reasoning_tokens":4}}}\n'
        b'data: [DONE]\n')
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResponse(sse, {}))
    monkeypatch.setitem(zen_shim._KEY_CACHE, "OPENCODE_ZEN_API_KEY", "k")
    out = zen_shim._stream_once(
        "https://opencode.ai/zen/v1",
        {"model": "x-preview-f-free", "input": []})
    r0 = out["output"][0]
    assert r0["type"] == "reasoning"
    assert r0["id"].startswith("rs_")
    assert r0["summary"] == [{"type": "summary_text", "text": "think hard"}]
    assert out["output"][1]["content"][0]["text"] == "answer"
    assert out["usage"]["output_tokens_details"] == {"reasoning_tokens": 4}
    # no reasoning streamed -> no reasoning item, indices unshifted
    sse2 = (b'data: {"choices":[{"delta":{"content":"plain"}}]}\n'
            b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
            b'"usage":{"prompt_tokens":1,"completion_tokens":1}}\n'
            b'data: [DONE]\n')
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResponse(sse2, {}))
    out2 = zen_shim._stream_once(
        "https://opencode.ai/zen/v1",
        {"model": "x-preview-f-free", "input": []})
    assert out2["output"][0]["type"] == "message"
    assert "output_tokens_details" not in out2["usage"]


def test_replayed_reasoning_items_never_flow_back_upstream(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """codex replays the reasoning item in later turns' input; _to_chat
    must skip it (the free-round-trip half of the visibility design) —
    the thinking text never re-enters the upstream context."""
    sse = (b'data: {"choices":[{"delta":{"content":"ok"}}]}\n'
           b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
           b'"usage":{"prompt_tokens":1,"completion_tokens":1}}\n'
           b'data: [DONE]\n')
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["body"] = __import__("json").loads(req.data)
        return _FakeResponse(sse, {})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setitem(zen_shim._KEY_CACHE, "OPENCODE_ZEN_API_KEY", "k")
    zen_shim._stream_once(
        "https://opencode.ai/zen/v1",
        {"model": "x-preview-f-free",
         "input": [{"type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": "go"}]},
                   {"type": "reasoning", "id": "rs_x",
                    "summary": [{"type": "summary_text",
                                 "text": "secret thinking"}]}]})
    msgs = captured["body"]["messages"]
    assert [m["role"] for m in msgs] == ["user"]
    assert "secret thinking" not in __import__("json").dumps(msgs)


def test_merge_turn_reasoning_carries_the_whole_turn() -> None:
    """The shim's tool loop consumes intermediate responses — where the
    model actually thinks — so only the final iteration's reasoning
    used to reach codex. The merged item must carry every iteration,
    labelled when there is more than one, and vanish when the turn had
    no reasoning at all."""
    assert zen_shim._merge_turn_reasoning([]) is None
    one = zen_shim._merge_turn_reasoning([(0, "only thought")])
    assert one["type"] == "reasoning" and one["id"].startswith("rs_")
    assert one["summary"] == [{"type": "summary_text",
                               "text": "only thought"}]
    many = zen_shim._merge_turn_reasoning(
        [(0, "plan the proof"), (3, "loogle came up dry"),
         (7, "switch to induction")])
    text = many["summary"][0]["text"]
    assert text == ("[iter 0] plan the proof\n\n[iter 3] loogle came up "
                    "dry\n\n[iter 7] switch to induction")


def test_tool_loop_harvests_reasoning_every_iteration() -> None:
    """Mechanism pin on the handler source (house style): the harvest
    must run per iteration inside the loop, and the synthesis must drop
    the final response's own reasoning item in favour of the merged
    whole-turn one."""
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert "turn_reasoning.append((iters, s[\"text\"]))" in src
    assert "_merge_turn_reasoning(turn_reasoning)" in src
    assert 'if it.get("type") != "reasoning"' in src


def test_reasoning_pin_prefers_the_hard_cap(monkeypatch) -> None:
    """Effort bounds the AVERAGE reasoning length but not the tail —
    per-call latency p99=619s max=1868s outlived two formalizer walls
    (sylvester_gallai, 2026-08-24). Nous honors reasoning.max_tokens
    (the keys 400 together, so the cap REPLACES effort); unset, the
    effort pin stands."""
    monkeypatch.setattr(zen_shim, "ZEN_REASONING_MAX_TOKENS", 4096)
    assert zen_shim._reasoning_pin() == {"max_tokens": 4096}
    monkeypatch.setattr(zen_shim, "ZEN_REASONING_MAX_TOKENS", 0)
    assert zen_shim._reasoning_pin() == {"effort": zen_shim.ZEN_EFFORT}
    # the chat translation inherits whatever the pin decided
    monkeypatch.setattr(zen_shim, "ZEN_REASONING_MAX_TOKENS", 512)
    chat = zen_shim._to_chat({"input": []})
    assert chat["reasoning"] == {"max_tokens": 512}


def test_flowing_stream_touches_the_heartbeat(monkeypatch, tmp_path) -> None:
    """Deep-thinking calls run 10-31 minutes while producing real work
    (a 1868s call landed 3 items, sylvester_gallai 2026-08-24), and the
    heartbeat used to move only at iteration boundaries — one deep
    think came within 9 minutes of the 2400s joint-silence kill.
    Chunks arriving IS liveness; the stream must beat every ~20s."""
    sse = (b'data: {"choices":[{"delta":{"reasoning":"a"}}]}\n'
           b'data: {"choices":[{"delta":{"content":"ok"}}]}\n'
           b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
           b'"usage":{"prompt_tokens":1,"completion_tokens":1}}\n'
           b'data: [DONE]\n')
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResponse(sse, {}))
    monkeypatch.setitem(zen_shim._KEY_CACHE, "OPENCODE_ZEN_API_KEY", "k")
    # throttle open: every chunk beats
    monkeypatch.setattr(zen_shim, "_STREAM_BEAT_SEC", -1.0)
    tok = zen_shim._STREAM_ATTEMPT_DIR.set(str(tmp_path))
    try:
        zen_shim._stream_once("https://opencode.ai/zen/v1",
                              {"model": "x-preview-f-free", "input": []})
    finally:
        zen_shim._STREAM_ATTEMPT_DIR.reset(tok)
    assert (tmp_path / "_shim_heartbeat").exists(), (
        "a flowing stream must touch the watchdog's third clock")


def test_turn_trail_renders_bounded_and_absent_when_toolless() -> None:
    """The rollout is the ONLY thing a resume replays, and it carried
    no tool history — a retried agent kept its files but lost its
    EXPERIENCE and re-made last life's mistakes (proven 2026-08-24: a
    resumed agent hand-recomputed a tool result it could not recall).
    The trail is a bounded assistant-message work log; no tools, no
    item."""
    assert zen_shim._render_turn_trail([]) is None
    t = zen_shim._render_turn_trail(
        ['loogle({"query":"Collinear"}) -> no hits',
         'write_file({"path":"new_x.lean"}) -> wrote 2952 chars'])
    assert t.startswith("[tool trail")
    assert "1. loogle" in t and "2. write_file" in t
    big = zen_shim._render_turn_trail(["inspect(x) -> " + "y" * 200] * 100)
    assert len(big) <= zen_shim._TRAIL_TOTAL_CHARS + 200
    assert "middle elided" in big


def test_turn_trail_ships_as_a_message_item_never_a_function_call() -> None:
    """Mechanism pin: a bare function_call in a LIVE response is a
    PENDING call codex executes — double-running apply_edit corrupts
    the patch. The trail must enter the output as an assistant message
    (inert on replay, `_to_chat` carries it verbatim), placed before
    the final answer."""
    src = open(zen_shim.__file__, encoding="utf-8").read()
    assert "_render_turn_trail(turn_trail)" in src
    assert 'turn_trail.append(f"{tool}({_args_s}) -> {_out_s}")' in src
    # the insertion site builds a message item, not a function_call
    i = src.index("trail_text is not None")
    block = src[i:i + 400]
    assert '"type": "message"' in block
    assert '"function_call"' not in block
