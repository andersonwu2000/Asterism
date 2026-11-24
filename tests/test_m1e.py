"""Slice 1e: an agent is reached from its own side only. Channel talk is not handed to an agent because it spoke there;
a mention by another person's side does not call it; the two switches that opened an agent to others are gone. What
stays: a mention by its own side, and the answer to its own question, whoever answers.

    python -m pytest tests/test_m1e.py -q
"""
from __future__ import annotations

import pytest

from test_m1b import SLUG, build_world, mention


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datae"))
    yield world
    world.srv.stop()


def test_an_agent_is_handed_only_what_its_own_side_addresses_to_it_and_answers_to_its_questions(w):
    w.a1.say("I am following this channel [e0]", to="#general")
    w.alice.say("a remark for nobody in particular [e1]")
    w.a2.say("another one, from an agent of the same person [e2]", to="#general")
    w.a1.absent("[e1]", 2.0)
    w.a1.absent("[e2]", 0.5)
    unread = [m for m in w.a1.messages(place="#general", limit=50).json()["messages"] if "[e1]" in m["text"] or "[e2]" in m["text"]]
    assert len(unread) == 2 and all(m["level"] == "muted" for m in unread), "there to read, not handed over"

    called = w.alice.say("@a1 this one is for you [e3]")
    assert mention(called, "a1")["result"] == "woken"
    assert w.a1.take("[e3]")["message"]["level"] == "important", "a mention by its own side calls it"
    w.a1.say("here [e3a]", reply_to=called["id"])
    asked = w.a2.say("@a1 and from an agent of the same person [e3b]", to="#general")
    assert w.a1.take("[e3b]")["message"]["level"] == "important"
    w.a1.say("yes [e3c]", reply_to=asked["id"])

    # What stays beside that: the answer to its own question, whoever answers.
    asked = w.a1.say("@bob which constant do you mean? [e4]", to="#general")
    assert mention(asked, "bob")["result"] == "notified"
    w.bob.say("the one in section 4 [e4a]", reply_to=asked["id"])
    got = w.a1.take("[e4a]")["message"]
    assert (got["level"], got["relation"]) == ("normal", "another collaborator"), "handed over, and it owes no answer"
    w.bob.say("and a remark that answers nothing [e4b]")
    w.a1.absent("[e4b]", 1.5)

    # Another person's side does not call it (no switch opens it any more: the next test).
    r = w.bob.say("@a1 could you check this for me? [e5]")
    assert mention(r, "a1")["result"] == "closed"
    w.a1.absent("[e5]", 1.5)
    r = w.b1.say("@a1 and from bob's agent [e6]", to="#general")
    assert mention(r, "a1")["result"] == "closed"
    w.a1.absent("[e6]", 1.5)
    seen = [m for m in w.a1.messages(place="#general", limit=50).json()["messages"] if "[e5]" in m["text"] or "[e6]" in m["text"]]
    assert len(seen) == 2 and all(m["level"] == "muted" for m in seen)
    assert not [m for m in w.a1.messages().json()["messages"] if "[e5]" in m["text"] or "[e6]" in m["text"]], \
        "not among what it must answer"


def test_the_switches_that_opened_an_agent_to_others_are_gone(w):
    for name in ("others_mention", "others_channel"):
        r = w.alice.c.post(f"/{SLUG}/api/my/switches", json={name: True})
        assert r.status_code == 400 and r.json()["error"] == "invalid_switches", (name, r.text)
    my = w.alice.c.get(f"/{SLUG}/api/my").json()
    assert my["switches"] == {"others_regroup": False}, my["switches"]
    assert w.alice.c.post(f"/{SLUG}/api/my/switches", json={"others_regroup": True}).status_code == 200
    assert w.alice.c.post(f"/{SLUG}/api/my/switches", json={"others_regroup": False}).status_code == 200
    groups = w.alice.c.get(f"/{SLUG}/api/members").json()["groups"]
    own = next(g for g in groups if g["name"] == "alice-agents")
    r = w.alice.c.post(f"/{SLUG}/api/groups/{own['name']}", json={"permissions": own["permissions"] + ["others_mention"]})
    assert r.status_code == 400, "no permission of that name any more: " + r.text
    for page in (f"/{SLUG}", f"/{SLUG}/me/agents", f"/{SLUG}/settings/groups"):
        html = w.alice.c.get(page).text
        assert "別人可以 @" not in html and "別人的頻道訊息" not in html, page
