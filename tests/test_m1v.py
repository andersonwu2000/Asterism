"""Slice 1v: the person an agent belongs to sees, on the agent page, what that agent and their other agents write to
each other privately. Nobody else does, and nothing else about private conversations changes.

    python -m pytest tests/test_m1v.py -q
"""
from __future__ import annotations

import pytest

from test_m1b import SLUG, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datav"))
    yield world
    world.srv.stop()


def items(person, agent, **params) -> list[dict]:
    r = person.c.get(f"/{SLUG}/api/agents/{agent}/timeline", params={"limit": 100, **params})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def found(xs, tag) -> list[dict]:
    return [x for x in xs if x["kind"] == "message" and tag in x["message"]["text"]]


def test_the_agents_person_sees_what_their_agents_write_to_each_other(w):
    sent = w.a1.say("a result for you, between agents [v1]", to="a2")
    w.a2.take("[v1]")
    back = w.a2.say("received, thank you [v1b]", to="a1", reply_to=sent["id"])

    on_a1 = items(w.alice, "a1")
    one = found(on_a1, "[v1]")
    assert len(one) == 1 and one[0]["dir"] == "sent", on_a1
    m = one[0]["message"]
    assert m["private"] is True and m["in"] == "a2" and m["with"] == "a2" and m["from"] == "a1"
    assert m["level"] == "normal"
    answer = found(on_a1, "[v1b]")
    assert len(answer) == 1 and answer[0]["dir"] == "received" and answer[0]["message"]["with"] == "a2"
    assert answer[0]["message"]["id"] == back["id"] and answer[0]["message"]["reply_to"] == sent["id"]

    on_a2 = items(w.alice, "a2")
    other = found(on_a2, "[v1]")
    assert len(other) == 1 and other[0]["dir"] == "received" and other[0]["message"]["with"] == "a1"
    assert found(items(w.alice, "a1", only="concerns"), "[v1]"), "it concerns the agent: kept by the filter"


def test_nobody_else_sees_it_and_nothing_else_opens(w):
    w.a1.say("only alice's agents and alice [v2]", to="a2")
    w.a2.take("[v2]")
    assert found(items(w.alice, "a1"), "[v2]")
    for other in (w.bob, w.carol):
        assert not found(items(other, "a1"), "[v2]") and not found(items(other, "a2"), "[v2]"), other.name
    # For alice it is on the agent page only: not in her own conversation with a2, not counted, not searchable.
    assert not [m for m in w.alice.read(place="a2") if "[v2]" in m["text"]]
    private = w.alice.places().get("private", [])
    assert sum(p["unread"] for p in private) == 0, private
    mine = w.alice.say("my own word to a1 [v3]", to="a1")
    w.a1.take("[v3]")
    own = found(items(w.alice, "a1"), "[v3]")
    assert len(own) == 1 and own[0]["message"]["id"] == mine["id"] and "with" not in own[0]["message"], \
        "her own conversation with the agent is shown as before"
