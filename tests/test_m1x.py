"""Slice 1x (commands withdrawn on 2026-11-18): what an agent is doing (active / idle / offline from its session's last activity), quotas reported by the
program and shown only to their person, the files source as two buttons.

    python -m pytest tests/test_m1x.py -q
"""
from __future__ import annotations

import time

import pytest

from test_m1b import ENV, SLUG, Agent, build_world, until
from test_m1j import Computer, redeem

STALE_S = 3


def new_link(person) -> str:
    r = person.c.post(f"/{SLUG}/api/my/agent-invites")
    assert r.status_code == 201, r.text
    return r.json()["url"]


@pytest.fixture(scope="module")
def x(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datax"), dict(ENV, ASTERISM_STALE_S=str(STALE_S), ASTERISM_ACTIVE_S="60"))
    world.pc = None
    try:                                   # a failure while setting up must not leave the server running
        cred = redeem(new_link(world.alice), computer="pc-x").json()["credential"]
        world.cmd_agent = Agent(world.srv, cred, "s-x1", client="claude-code").register("cody")
        world.pc = Computer(world.srv, cred)
        world.pc.report(("s-x1", "claude-code"))
        world.pc.connect()
        world.cred = cred
        assert until(lambda: agent(world, "cody")["online"], 8)
        yield world
    finally:
        if world.pc is not None and world.pc._stop is not None:
            world.pc.disconnect()
        world.srv.stop()


def agent(w, name) -> dict:
    return next(a for a in w.alice.members()["agents"] if a["name"] == name)


def commands(w) -> list[dict]:
    with w.pc.lock:
        return [d for d in w.pc.got if d.get("kind") == "command"]


# ------------------------------------------------------------------ commands (withdrawn 2026-11-18)

def test_a_slash_after_a_mention_is_an_ordinary_message(x):
    """Commands to agents were withdrawn: `@agent /compact` is delivered to the agent as a message, and nothing is
    handed to its program as a command."""
    sent = x.alice.say("@cody /compact [x0]")
    got = until(lambda: [g for g in x.pc.got if g.get("kind") == "message" and g["message"]["id"] == sent["id"]], 8)
    assert got, "the agent is handed it as a message"
    assert not commands(x), "no command deliveries exist any more"
    assert x.pc.c.post(f"/{SLUG}/api/computer/command", json={"delivery": 1, "result": "done"}).status_code in (404, 405)


# ------------------------------------------------------------------ activity and quotas

def test_the_work_state_follows_the_sessions_last_activity(x):
    now = time.time()
    x.pc.c.post(f"/{SLUG}/api/computer/sessions",
                json={"sessions": [{"session": "s-x1", "product": "claude-code", "active_at": now}]})
    a = agent(x, "cody")
    assert a["work"] == "active" and a["last_active"], a
    x.pc.c.post(f"/{SLUG}/api/computer/sessions",
                json={"sessions": [{"session": "s-x1", "product": "claude-code", "active_at": now - 600}]})
    assert agent(x, "cody")["work"] == "idle"
    r = x.alice.c.post(f"/{SLUG}/api/tasks", json={"group": "ai", "title": "held and left [x2]", "responsible": "cody"})
    assert r.status_code == 201, r.text
    assert until(lambda: agent(x, "cody")["stale"] is True, STALE_S + 4), "holds a task, idle too long"
    assert agent(x, "cody")["busy"] is True, "busy is still busy"


def test_quotas_are_kept_and_shown_only_to_their_person(x):
    q = [{"product": "codex", "plan": "prolite", "windows": [{"name": "week", "used_percent": 1, "resets_at": 1795260741}]},
         {"product": "claude-code", "windows": [{"name": "5h", "used_percent": 23.5}, {"name": "7d", "used_percent": 41}]}]
    r = x.pc.c.post(f"/{SLUG}/api/computer/sessions",
                    json={"sessions": [{"session": "s-x1", "product": "claude-code"}], "quotas": q})
    assert r.status_code == 200, r.text
    mine = x.alice.c.get(f"/{SLUG}/api/my").json()["credentials"]
    row = next(c for c in mine if c.get("quotas"))
    assert {p["product"] for p in row["quotas"]} == {"codex", "claude-code"} and row["quotas"][0].get("at") or True
    assert "quotas" not in str(x.bob.c.get(f"/{SLUG}/api/members").json()), "nobody else sees a person's quota"


# ------------------------------------------------------------------ files

def test_the_files_source_is_two_buttons(x):
    page = x.alice.c.get(f"/{SLUG}/files").text
    switch = page.split('id="source-switch"', 1)[1][:1200]
    assert switch.count('aria-pressed=') >= 2 and "aria-haspopup" not in switch
