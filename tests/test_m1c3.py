"""Acceptance tests for slice 1c, step c3: an agent that comes back is told how much it missed, and reads
everything unread in one call.

    python -m pytest tests/test_m1c3.py -q
"""
from __future__ import annotations

import time

import pytest

from test_m1b import SLUG, build_world, connector_token, frame, remote_tool, until
from test_m1b2 import leave

HINT = "(While you were offline other messages arrived: {n} unread. messages with all=true reads them in one call.)"


@pytest.fixture(scope="module")
def r(tmp_path_factory):
    """alice owns the project and has the agents a1 and a2; bob has b1; carol has none. All agents are online."""
    world = build_world(tmp_path_factory.mktemp("datac3"))
    yield world
    world.srv.stop()


def unread_total(agent) -> int:
    who = agent.c.get(f"/{SLUG}/api/agent/whoami")
    assert who.status_code == 200, who.text
    return sum(u["count"] for u in who.json().get("unread", []))


def test_an_agent_that_comes_back_is_told_how_much_it_missed(r):
    leave(r.a2)
    assert until(lambda: not r.alice.is_online("a2"), 5)
    assert r.alice.c.post(f"/{SLUG}/api/channels", json={"name": "side"}).status_code == 201
    quiet = [r.alice.say(f"talk that nobody has to answer, {i} [bk{i}]") for i in range(3)]
    quiet.append(r.alice.say("and some in another channel [bk3]", to="#side"))
    first = r.alice.say("@a2 the first of two that need you [bk8]")
    last = r.alice.say("@a2 and the second [bk9]")

    r.a2.register("a2")
    assert until(lambda: r.alice.is_online("a2"), 6)
    d8, d9 = r.a2.take("[bk8]"), r.a2.take("[bk9]")
    time.sleep(0.5)                                         # both are acknowledged by now
    n = unread_total(r.a2)
    assert n >= len(quiet), "what was not addressed to it is still unread"
    assert d8["frame"] == frame(d8["message"]), "the hint comes once, with the last message handed over"
    assert d9["frame"] == frame(d9["message"]) + "\n" + HINT.format(n=n)
    assert (d8["message"]["id"], d9["message"]["id"]) == (first["id"], last["id"])
    r.a2.say("here [bk8a]", reply_to=first["id"])
    r.a2.say("and here [bk9a]", reply_to=last["id"])

    got = r.a2.messages(all="true")
    assert got.status_code == 200, got.text
    listed = got.json()["messages"]
    assert len(listed) == n and [m["id"] for m in listed] == sorted(m["id"] for m in listed), "everything, oldest first"
    mine = {m["id"]: m for m in listed}
    assert all(q["id"] in mine and mine[q["id"]]["level"] == "muted" for q in quiet)
    assert mine[quiet[0]["id"]]["in"] == "#general" and mine[quiet[3]["id"]]["in"] == "#side"
    assert unread_total(r.a2) == 0 and r.a2.messages(all="true").json()["messages"] == []
    for clash in ({"place": "#general"}, {"id": first["id"]}, {"before": last["id"]}):
        bad = r.a2.messages(all="true", **clash)
        assert bad.status_code == 400 and bad.json()["error"] == "bad_request", clash

    sent = r.alice.say("@a1 you were here all along [bk10]")
    d = r.a1.take("[bk10]")
    assert unread_total(r.a1) > 0 and d["frame"] == frame(d["message"]), "no hint for an agent that was not away"
    r.a1.say("yes [bk10a]", reply_to=sent["id"])

    before = unread_total(r.a1)
    assert before >= 4
    part = r.a1.messages(all="true", limit=2).json()["messages"]
    assert len(part) == 2 and unread_total(r.a1) == before - 2, "the limit holds, and the rest stays unread"
    rest = r.a1.messages(all="true").json()["messages"]
    assert len(rest) == before - 2 and min(m["id"] for m in rest) > max(m["id"] for m in part)

    r.a2.messages(all="true")                               # whatever reached the channel meanwhile is read
    leave(r.a2)                                             # nothing else unread: no hint
    assert until(lambda: not r.alice.is_online("a2"), 5)
    only = r.alice.say("@a2 one thing, and nothing else happened [bk11]")
    r.a2.register("a2")
    d = r.a2.take("[bk11]")
    assert d["frame"] == frame(d["message"]), "nothing else is unread, so nothing is said about it"
    r.a2.say("got it [bk11a]", reply_to=only["id"])


def test_the_connector_reads_everything_unread_too(r):
    token = connector_token(r.srv, r.bob)
    assert not remote_tool(r.srv, "register", token, "conv-r", name="dot-r")[1]
    r.bob.say("something for later [cn1]")
    got, bad = remote_tool(r.srv, "messages", token, "conv-r", all=True)
    assert not bad and any("[cn1]" in m["text"] for m in got["messages"]), got
    msg, bad = remote_tool(r.srv, "messages", token, "conv-r", all=True, id=1)
    assert bad and isinstance(msg, str)
