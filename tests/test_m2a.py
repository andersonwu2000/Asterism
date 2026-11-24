"""Slice 2a: the rail's message buttons carry how much is unread and how much of it is important for the reader; a
channel says to whom it is closed, so that `@` does not offer them there.

    python -m pytest tests/test_m2a.py -q
"""
from __future__ import annotations

import re

import pytest

from test_m1b import SLUG, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("data2a"))
    yield world
    world.srv.stop()


def count(html: str, ident: str) -> tuple[bool, int, int]:
    """(shown, unread, important) of one of the rail's counts as the page is first painted."""
    m = re.search(r'<span id="%s"([^>]*)>' % re.escape(ident), html)
    assert m, f"no {ident} in the page"
    attrs = m.group(1)
    unread, important = (re.search(r'data-%s="(\d+)"' % k, attrs) for k in ("unread", "important"))
    assert unread and important, f"{ident} carries data-unread and data-important: {attrs}"
    return "hidden" not in attrs, int(unread.group(1)), int(important.group(1))


def rail(person) -> str:
    """A page that is neither chat, private messages nor the agent page: all three counts are drawn on it."""
    r = person.c.get(f"/{SLUG}/work")
    assert r.status_code == 200, r.status_code
    return r.text


def read_all(person, place="#general"):
    last = max(m["id"] for m in person.read(place))
    assert person.c.post(f"/{SLUG}/api/read", json={"in": place, "upto": last}).status_code == 200


def test_the_rail_says_what_is_unread_and_how_much_of_it_is_important(w):
    # The world begins with the notices of the agents coming online, unread and normal for their person: they count.
    assert count(rail(w.alice), "rail-chat-count")[2] == 0
    read_all(w.alice)
    assert count(rail(w.alice), "rail-chat-count") == (False, 0, 0)
    w.bob.say("a remark, for nobody in particular [u1]")
    w.bob.say("and another [u2]")
    assert count(rail(w.alice), "rail-chat-count") == (True, 2, 0), "unread, nothing important: the mark without a number"
    w.bob.say("@alice this one is for you [u3]")
    assert count(rail(w.alice), "rail-chat-count") == (True, 3, 1), "one of them is important"

    assert count(rail(w.alice), "rail-dm-count") == (False, 0, 0) and count(rail(w.alice), "rail-my-count") == (False, 0, 0)
    w.bob.say("privately [u4]", to="alice")
    w.a1.say("from your agent [u5]", to="alice")
    assert count(rail(w.alice), "rail-dm-count") == (True, 1, 1)
    assert count(rail(w.alice), "rail-my-count") == (True, 1, 1)

    read_all(w.alice)
    assert count(rail(w.alice), "rail-chat-count") == (False, 0, 0), "read: nothing left"


def test_a_muted_channels_talk_does_not_count_but_a_mention_there_does(w):
    assert w.carol.c.post(f"/{SLUG}/api/channels/general/mute", json={"muted": True}).status_code == 200
    try:
        before = count(rail(w.carol), "rail-chat-count")
        w.bob.say("talk in a channel carol muted [u6]")
        assert count(rail(w.carol), "rail-chat-count") == before, "muted talk is not counted"
        w.bob.say("@carol but this is for you [u7]")
        shown, unread, important = count(rail(w.carol), "rail-chat-count")
        assert shown and important == before[2] + 1 and unread == before[1] + 1
    finally:
        assert w.carol.c.post(f"/{SLUG}/api/channels/general/mute", json={"muted": False}).status_code == 200


def test_a_channel_says_to_whom_it_is_closed(w):
    assert w.alice.c.post(f"/{SLUG}/api/channels", json={"name": "secret"}).status_code == 201
    assert w.alice.c.post(f"/{SLUG}/api/groups", json={"name": "insiders", "permissions": ["read", "post"]}).status_code == 201
    assert w.alice.c.post(f"/{SLUG}/api/members/bob/groups", json={"add": ["insiders"], "remove": []}).status_code == 200
    r = w.alice.c.post(f"/{SLUG}/api/channels/secret/permissions",
                       json={"overrides": {"human": {"read": "deny"}, "ai": {"read": "deny"}, "insiders": {"read": "allow"}}})
    assert r.status_code == 200, r.text
    channels = {c["name"]: c for c in w.alice.places()["channels"]}
    assert channels["general"]["closed_to"] == [], "everybody reads it"
    closed = channels["secret"]["closed_to"]
    assert closed == sorted(closed)
    assert {"carol", "a1", "a2", "b1"} <= set(closed), "the people and agents who may not read it"
    assert {"ai", "alice-agents", "bob-agents"} <= set(closed), "the groups none of whose members may read it"
    assert not {"alice", "bob", "human", "owner", "insiders"} & set(closed), "who reads it, and a group with a reader in it"
