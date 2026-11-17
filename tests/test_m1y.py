"""Slice 1y: projects get a random address, groups may be named in any script (and mentioned), messages take reactions,
edits and deletions, pictures of the repository show in messages.

    python -m pytest tests/test_m1y.py -q
"""
from __future__ import annotations

import re

import pytest

from test_m1b import SLUG, Person, build_world, until


@pytest.fixture(scope="module")
def y(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datay"))
    yield world
    world.srv.stop()


def msg(person, mid, place="#general") -> dict:
    return next(m for m in person.read(place) if m["id"] == mid)


def test_a_new_project_gets_a_random_address_and_names_may_repeat(y):
    erin = Person(y.srv, "erin")
    one = erin.c.post("/api/projects", json={"name": "Orbit Lab"})
    two = erin.c.post("/api/projects", json={"name": "Orbit Lab", "slug": "chosen-by-me"})
    assert one.status_code == 201 and two.status_code == 201, (one.text, two.text)
    a, b = one.json()["slug"], two.json()["slug"]
    assert a != b and re.fullmatch(r"[a-z0-9]{10}", a) and re.fullmatch(r"[a-z0-9]{10}", b), (a, b)
    assert erin.c.get(f"/{a}").status_code == 200 and erin.c.get(f"/{b}").status_code == 200


def test_groups_are_named_in_any_script_and_mentioned(y):
    r = y.alice.c.post(f"/{SLUG}/api/groups", json={"name": "證明組", "permissions": ["read", "post"]})
    assert r.status_code == 201, r.text
    assert y.alice.c.post(f"/{SLUG}/api/members/bob/groups", json={"add": ["證明組"], "remove": []}).status_code == 200
    for bad in ("有 空格", "a@b", "#組", "x" * 41, ""):
        assert y.alice.c.post(f"/{SLUG}/api/groups", json={"name": bad, "permissions": ["read"]}).status_code == 400, bad
    sent = y.alice.say("@證明組請看這段")
    assert [m["name"] for m in sent["mentions"]] == ["證明組"], sent["mentions"]
    assert y.alice.c.post(f"/{SLUG}/api/groups/證明組", json={"name": "審查組"}).status_code == 200


def test_reactions_are_added_and_taken_away(y):
    m = y.alice.say("react to me [y1]")
    for who in (y.bob, y.carol):
        assert who.c.post(f"/{SLUG}/api/messages/{m['id']}/react", json={"emoji": "👍", "on": True}).status_code == 200
    assert y.bob.c.post(f"/{SLUG}/api/messages/{m['id']}/react", json={"emoji": "🎉", "on": True}).status_code == 200
    got = msg(y.alice, m["id"])["reactions"]
    assert got[0]["emoji"] == "👍" and got[0]["count"] == 2 and set(got[0]["by"]) == {"bob", "carol"}
    assert y.bob.c.post(f"/{SLUG}/api/messages/{m['id']}/react", json={"emoji": "👍", "on": False}).status_code == 200
    assert msg(y.alice, m["id"])["reactions"][0]["count"] == 1
    assert y.bob.c.post(f"/{SLUG}/api/messages/{m['id']}/react", json={"emoji": "ok", "on": True}).status_code == 400
    seen = y.a1.messages(place="#general").json()["messages"]
    assert any(x["id"] == m["id"] and x.get("reactions") for x in seen), "agents see reactions"


def test_a_person_edits_their_own_message(y):
    m = y.bob.say("first wording [y2]")
    assert y.alice.c.post(f"/{SLUG}/api/messages/{m['id']}/edit", json={"text": "not hers"}).status_code == 403
    r = y.bob.c.post(f"/{SLUG}/api/messages/{m['id']}/edit", json={"text": "second wording [y2]"})
    assert r.status_code == 200, r.text
    got = msg(y.carol, m["id"])
    assert got["text"] == "second wording [y2]" and got["edited_at"]


def test_deleting_messages_own_own_agents_and_by_moderators(y):
    own = y.carol.say("mine to delete [y3]")
    assert y.bob.c.post(f"/{SLUG}/api/messages/{own['id']}/delete").status_code == 403
    assert y.carol.c.post(f"/{SLUG}/api/messages/{own['id']}/delete").status_code == 200
    got = msg(y.alice, own["id"])
    assert got["deleted"] is True and "mine to delete" not in str(got)
    agents = y.a1.say("an agent's message [y3]", to="#general")
    assert y.bob.c.post(f"/{SLUG}/api/messages/{agents['id']}/delete").status_code == 403
    assert y.alice.c.post(f"/{SLUG}/api/messages/{agents['id']}/delete").status_code == 200, "its person may"
    bobs = y.bob.say("moderated [y3]")
    assert y.alice.c.post(f"/{SLUG}/api/messages/{bobs['id']}/delete").status_code == 200, "manage_channels may"
    system = next(m for m in y.alice.read() if m["from_kind"] == "system")
    assert y.alice.c.post(f"/{SLUG}/api/messages/{system['id']}/delete").status_code in (400, 403, 409)
    assert y.alice.c.get(f"/{SLUG}/api/search", params={"q": "y3"}).json()["results"] == [] or \
        all(r.get("deleted") for r in y.alice.c.get(f"/{SLUG}/api/search", params={"q": "y3"}).json()["results"])


def test_the_send_control_is_an_icon(y):
    page = y.alice.c.get(f"/{SLUG}").text
    form = page.split('id="composer"', 1)[1].split("</form>", 1)[0]
    button = re.search(r"<button[^>]*type=\"submit\"[^>]*>(.*?)</button>", form, re.S)
    assert button and "aria-label=" in button.group(0), "an accessible name"
    assert "<svg" in button.group(1) or "glyph" in button.group(1), "an icon, not a word"
    assert "送出" not in re.sub(r"<[^>]+>", "", button.group(1)), "no visible word"
