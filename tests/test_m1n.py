"""Slice 1n: the connector is not used from Codex. A tool call that comes through the connector from a Codex
conversation (its User-Agent says so) is refused with one sentence pointing to the local tools; ChatGPT's calls and
the protocol's own methods are served as before.

    python -m pytest tests/test_m1n.py -q
"""
from __future__ import annotations

import httpx
import pytest

from test_m1b import DESCRIPTIONS, SLUG, build_world, connector_token

CHATGPT_UA, CODEX_UA = "openai-mcp/1.0.0", "openai-mcp/1.0.0 (Codex)"
CODEX_CONNECTOR = ("This is the Asterism connector of your ChatGPT account. It cannot wake a Codex conversation, so it is "
                   "not used from Codex. Use the Asterism tools of the local MCP server named `asterism-local` instead: "
                   "call its `register` with your agent name and takeover=true, and use only those tools from now on. If "
                   "this conversation has no `asterism-local` tools, ask your user for an agent invitation link (from the "
                   "\"my agents\" page of the project) and follow it.")


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datan"))
    world.token = connector_token(world.srv, world.alice)
    yield world
    world.srv.stop()


def rpc(w, ua, session, method, params=None) -> dict:
    h = {"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + w.token, "User-Agent": ua,
         "x-openai-session": session}
    r = httpx.post(f"{w.srv.url}/{SLUG}/mcp", headers=h, timeout=30,
                   json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
    assert r.status_code == 200, r.text
    return r.json()


def tool(w, ua, session, tool_name, **args) -> tuple[str, bool]:
    res = rpc(w, ua, session, "tools/call", {"name": tool_name, "arguments": args})["result"]
    return res["content"][0]["text"], bool(res.get("isError"))


def agent_names(w) -> set[str]:
    return {a["name"] for a in w.alice.members()["agents"]}


def test_a_tool_call_from_codex_is_refused_with_the_way_to_the_local_tools(w):
    for called, args in (("register", {"name": "cody"}), ("whoami", {}), ("send", {"to": "#general", "text": "hello [n1]"}),
                         ("messages", {}), ("set_status", {"title": "x"})):
        text, bad = tool(w, CODEX_UA, "conv-codex-1", called, **args)
        assert bad and text == CODEX_CONNECTOR, (called, text)
    assert "cody" not in agent_names(w), "nothing was registered"
    assert not [m for m in w.alice.read() if "[n1]" in m["text"]], "nothing was sent"
    text, bad = tool(w, "OpenAI-MCP/2.3 (codex)", "conv-codex-1", "whoami")
    assert bad and text == CODEX_CONNECTOR, "the marker is found whatever its letter case"
    # Only that is refused: ChatGPT is served as before, and the protocol's own methods answer Codex too.
    text, bad = tool(w, CHATGPT_UA, "conv-dot-1", "register", name="dot-n")
    assert not bad and "dot-n" in agent_names(w), text
    init = rpc(w, CODEX_UA, "conv-codex-2", "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                          "clientInfo": {"name": "openai-mcp (Codex)", "version": "1.0.0"}})
    assert "result" in init and init["result"]["serverInfo"], init
    listed = rpc(w, CODEX_UA, "conv-codex-2", "tools/list")["result"]["tools"]
    assert {t["name"] for t in listed} == set(DESCRIPTIONS), "the list is the account's: it cannot differ per client"


def test_an_agent_that_codex_registered_before_is_refused_and_the_local_tools_take_the_name(w):
    """The state the hub was found in: a Codex conversation holds an agent through the connector."""
    text, bad = tool(w, CHATGPT_UA, "conv-codex-3", "register", name="smale")      # registered before the rule
    assert not bad, text
    text, bad = tool(w, CODEX_UA, "conv-codex-3", "send", to="#general", text="still through the connector [n2]")
    assert bad and text == CODEX_CONNECTOR
    assert not [m for m in w.alice.read() if "[n2]" in m["text"]]
    local = httpx.Client(base_url=w.srv.url, timeout=30, headers={
        "Authorization": "Bearer " + w.cred_a, "X-Asterism-Session": "s-smale-local", "X-Asterism-Client": "codex"})
    r = local.post(f"/{SLUG}/api/agent/register", json={"name": "smale", "takeover": True})
    assert r.status_code == 200, r.text
    row = next(a for a in w.alice.members()["agents"] if a["name"] == "smale")
    assert row["kind"] == "codex", "the local tools hold the name now"
