"""Slice 1m: which model an agent runs on. The program reads it from the agent's own session record on its computer
and says it with each call; the server keeps it, shows it, and puts it on the agent's messages.

    python -m pytest tests/test_m1m.py -q
"""
from __future__ import annotations

import json

import pytest

from test_m1b import SLUG, build_world
from test_m1j2 import ENV2, Mcp, exe, home, join  # noqa: F401  (fixtures)


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datam"), ENV2)
    yield world
    world.srv.stop()


def agent_row(person, name) -> dict:
    return next(a for a in person.c.get(f"/{SLUG}/api/members").json()["agents"] if a["name"] == name)


# ------------------------------------------------------------------ the server

def test_the_server_keeps_the_model_an_agent_says_and_puts_it_on_its_messages(v):
    assert agent_row(v.alice, "a1")["model"] is None
    v.a1.c.headers["X-Asterism-Model"] = "claude-opus-5-5"
    v.a1.say("with a model [m1]", to="#general")
    assert agent_row(v.bob, "a1")["model"] == "claude-opus-5-5"
    sent = next(m for m in v.alice.read() if "[m1]" in m["text"])
    assert sent["model"] == "claude-opus-5-5"
    seen = v.b1.messages(place="#general").json()["messages"]
    assert next(m for m in seen if "[m1]" in m["text"])["model"] == "claude-opus-5-5", "agents see it too"
    who = v.b1.c.get(f"/{SLUG}/api/agent/whoami").json()
    assert next(a for a in who["agents"] if a["name"] == "a1")["model"] == "claude-opus-5-5"
    person_msg = v.alice.say("from a person [m1p]")
    assert "model" not in next(m for m in v.alice.read() if m["id"] == person_msg["id"]) or \
        next(m for m in v.alice.read() if m["id"] == person_msg["id"])["model"] is None


def test_the_frame_names_the_senders_model(v):
    v.a1.c.headers["X-Asterism-Model"] = "claude-opus-5-5"
    v.a1.say("@a2 framed [m2]", to="#general")      # a2: alice's own agent, so the mention is never closed
    got = v.a2.take("[m2]")
    assert 'model="claude-opus-5-5"' in got["frame"], got["frame"]
    assert got["frame"].index('relation="') < got["frame"].index('model="') < got["frame"].index('level="')


def test_a_later_model_replaces_the_earlier_one_but_not_on_old_messages(v):
    v.a1.c.headers["X-Asterism-Model"] = "claude-sonnet-5-5"
    v.a1.say("after a switch [m3]", to="#general")
    assert agent_row(v.alice, "a1")["model"] == "claude-sonnet-5-5"
    msgs = v.alice.read()
    assert next(m for m in msgs if "[m1]" in m["text"])["model"] == "claude-opus-5-5", "a message keeps its own"
    assert next(m for m in msgs if "[m3]" in m["text"])["model"] == "claude-sonnet-5-5"


def test_a_bad_model_header_is_ignored_not_refused(v):
    for bad in ("x" * 65, "has space", "<b>", ""):
        v.a2.c.headers["X-Asterism-Model"] = bad
        r = v.a2.send("ignored model [m4]", to="#general")
        assert r.status_code == 200, (bad, r.text)
    assert agent_row(v.alice, "a2")["model"] is None
    del v.a2.c.headers["X-Asterism-Model"]


# ------------------------------------------------------------------ the program

def claude_record(root, sid: str, lines: list[dict]):
    folder = root / "projects" / "D--some-project"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{sid}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")


def test_the_program_reads_claude_codes_model_from_the_session_record(exe, v, home, tmp_path):
    join(exe, home, v, "--client", "none")
    cfg = tmp_path / "claude-config"
    sid = "5e55a0c1-0000-4000-8000-000000000001"
    claude_record(cfg, sid, [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"model": "claude-fable-5-2", "content": []}},
        {"type": "assistant", "isSidechain": True, "message": {"model": "claude-haiku-5-5", "content": []}},
        {"type": "user", "message": {"role": "user", "content": "the model field of a tool input", "model": "opus"}},
    ])
    m = Mcp(exe, home, CLAUDE_CODE_SESSION_ID=sid, CLAUDE_CONFIG_DIR=str(cfg))
    try:
        assert not m.tool("register", name="mona")[1]
        assert not m.tool("send", to="#general", text="from the program [m5]")[1]
        assert agent_row(v.alice, "mona")["model"] == "claude-fable-5-2", "the main chain's last answer, not a side chain"
        claude_record(cfg, sid, [{"type": "assistant", "message": {"model": "claude-opus-5-5", "content": []}}])
        assert not m.tool("whoami")[1]
        assert agent_row(v.alice, "mona")["model"] == "claude-opus-5-5", "read again at each call"
    finally:
        m.kill()


def test_the_program_reads_codexs_model_from_its_rollout(exe, v, home, tmp_path):
    join(exe, home, v, "--client", "none")
    codex_home = tmp_path / "codex-home"
    thread = "019a0000-0000-7000-8000-00000000c0de"
    day = codex_home / "sessions" / "2026" / "11" / "16"
    day.mkdir(parents=True)
    (day / f"rollout-2026-11-16T10-00-00-{thread}.jsonl").write_text(
        json.dumps({"type": "session_meta", "payload": {"id": thread}}) + "\n" +
        json.dumps({"type": "turn_context", "payload": {"model": "gpt-6-astra"}}) + "\n", encoding="utf-8")
    m = Mcp(exe, home, client_name="codex-mcp-client", CODEX_HOME=str(codex_home))
    try:
        assert not m.tool("register", meta={"threadId": thread}, name="cody")[1]
        assert not m.tool("whoami", meta={"threadId": thread})[1]
        assert agent_row(v.alice, "cody")["model"] == "gpt-6-astra"
    finally:
        m.kill()


def test_without_a_record_the_model_is_unknown_and_nothing_fails(exe, v, home, tmp_path):
    join(exe, home, v, "--client", "none")
    m = Mcp(exe, home, CLAUDE_CODE_SESSION_ID="5e55a0c1-0000-4000-8000-000000000002",
            CLAUDE_CONFIG_DIR=str(tmp_path / "empty"))
    try:
        assert not m.tool("register", name="nomo")[1]
        assert not m.tool("send", to="#general", text="no record [m6]")[1]
        assert agent_row(v.alice, "nomo")["model"] is None
    finally:
        m.kill()
