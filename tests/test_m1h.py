"""Slice 1h: a message that waits for an agent says so to the people who read it (`waiting`), until the agent comes
back and is handed it; deleting it revokes it, an edit is what the agent gets.

    python -m pytest tests/test_m1h.py -q
"""
from __future__ import annotations

import pytest

from test_m1b import OFFLINE_S, SLUG, build_world, until
from test_m1b2 import ENV2, fresh, leave


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datah"), ENV2)
    yield world
    world.srv.stop()


def away(v, name):
    """An agent of alice's whose helper stopped polling: offline, and it comes back with `.online()`."""
    a = fresh(v, name)
    a._stop.set()
    assert until(lambda: not v.alice.is_online(name), OFFLINE_S + 8)
    return a


def seen(person, place, tag) -> dict:
    return next(m for m in person.read(place) if tag in m["text"])


def test_a_message_for_an_agent_that_is_away_waits_and_says_so(v):
    h1 = away(v, "h1")
    r = v.alice.post("for when you are back [h1]", to="h1")
    assert r.status_code == 201 and r.json().get("waiting") == ["h1"], r.text
    assert seen(v.alice, "h1", "[h1]").get("waiting") == ["h1"]
    asked = v.alice.say("@h1 a question in the channel [h2]")
    assert asked.get("waiting") == ["h1"]
    assert seen(v.bob, "#general", "[h2]").get("waiting") == ["h1"], "whoever reads the message sees it"
    quiet = v.alice.say("a remark for nobody in particular [h3]")
    assert "waiting" not in quiet and "waiting" not in seen(v.alice, "#general", "[h3]"), "never addressed to an agent"
    on_page = v.alice.c.get(f"/{SLUG}/api/agents/h1/timeline", params={"limit": 50}).json()["items"]
    mine = next(x["message"] for x in on_page if x["kind"] == "message" and "[h1]" in x["message"]["text"])
    assert mine.get("waiting") == ["h1"], "on the agent page too"

    h1.online()
    h1.take("[h1]", 12)
    h1.take("[h2]", 12)
    assert until(lambda: "waiting" not in seen(v.alice, "h1", "[h1]"), 8), "handed over: it waits no longer"
    assert until(lambda: "waiting" not in seen(v.alice, "#general", "[h2]"), 8)
    h1.say("here [h2a]", reply_to=asked["id"])
    # Online now: what is sent to it is on its way, not waiting; and agents are never given the field.
    again = v.alice.say("@h1 and now that you are here? [h4]")
    h1.take("[h4]")
    assert until(lambda: "waiting" not in seen(v.alice, "#general", "[h4]"), 5)
    h1.say("yes [h4a]", reply_to=again["id"])
    assert not [m for m in h1.messages(place="#general", limit=50).json()["messages"] if "waiting" in m]
    leave(h1)


def test_a_waiting_message_can_be_revoked_or_changed(v):
    h3 = away(v, "h5")
    gone = v.alice.say("forget this one [h5]", to="h5")
    kept = v.alice.say("the first wording [h6]", to="h5")
    assert seen(v.alice, "h5", "[h5]").get("waiting") == ["h5"] and seen(v.alice, "h5", "[h6]").get("waiting") == ["h5"]
    assert v.alice.c.post(f"/{SLUG}/api/messages/{gone['id']}/delete").status_code == 200
    r = v.alice.c.post(f"/{SLUG}/api/messages/{kept['id']}/edit", json={"text": "the second wording [h6]"})
    assert r.status_code == 200, r.text
    assert seen(v.alice, "h5", "the second wording [h6]").get("waiting") == ["h5"], "edited, and still waiting"
    deleted = next(m for m in v.alice.read("h5") if m["id"] == gone["id"])
    assert deleted.get("deleted") is True and "waiting" not in deleted, "a deleted message waits for nobody"
    h3.online()
    got = h3.take("[h6]", 12)
    assert got["message"]["text"] == "the second wording [h6]", "the agent gets it as it reads now"
    h3.absent("[h5]", 2.0)
    leave(h3)


def test_the_page_has_the_words(v):
    page = v.alice.c.get(f"/{SLUG}").text
    assert "尚未送達" in page
    assert v.alice.c.post("/api/me/settings", json={"locale": "en"}).status_code == 200
    try:
        assert "Not delivered to" in v.alice.c.get(f"/{SLUG}").text
    finally:
        assert v.alice.c.post("/api/me/settings", json={"locale": "zh-TW"}).status_code == 200
