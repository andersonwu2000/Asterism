"""Slice 2b: an agent's groups are changed as a person's are. Whoever may manage groups puts any agent, their own or
somebody else's, into a custom group without being in it; without that permission a person still changes their own
agents' groups, within the groups they are in. The last switch (others_regroup) is gone, and the switches with it.

    python -m pytest tests/test_m2b.py -q
"""
from __future__ import annotations

import pytest

from test_m1b import SLUG, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("data2b"))
    yield world
    world.srv.stop()


def regroup(person, member, add=(), remove=()):
    return person.c.post(f"/{SLUG}/api/members/{member}/groups", json={"add": list(add), "remove": list(remove)})


def groups_of(person, name) -> list[str]:
    m = person.c.get(f"/{SLUG}/api/members").json()
    return next(x for x in m["people"] + m["agents"] if x["name"] == name)["groups"]


def test_an_agents_groups_are_changed_as_a_persons_are(w):
    assert w.alice.c.post(f"/{SLUG}/api/groups", json={"name": "team", "permissions": []}).status_code == 201
    assert "team" not in groups_of(w.alice, "alice"), "alice made it and is not in it"
    r = regroup(w.alice, "a1", add=["team"])
    assert r.status_code == 200 and "team" in r.json()["groups"], r.text                # her own agent
    r = regroup(w.alice, "b1", add=["team"])
    assert r.status_code == 200 and "team" in r.json()["groups"], r.text                # somebody else's, no switch asked
    assert regroup(w.alice, "bob", add=["team"]).status_code == 200                     # and a person, the same way
    assert {"a1", "b1", "bob"} <= {n for n in ("a1", "b1", "bob") if "team" in groups_of(w.alice, n)}
    assert regroup(w.alice, "b1", remove=["team"]).status_code == 200
    assert "team" not in groups_of(w.alice, "b1")

    # Without that permission (bob holds no manage_groups; he is in `team` now, b1 is not) a person still changes
    # their own agents' groups, within the groups they are in themselves, and nothing else.
    assert w.alice.c.post(f"/{SLUG}/api/groups", json={"name": "elsewhere", "permissions": []}).status_code == 201
    assert regroup(w.bob, "b1", add=["team"]).status_code == 200, "his own agent, a group he is in"
    r = regroup(w.bob, "b1", add=["elsewhere"])
    assert r.status_code == 403, "a group he is not in: " + r.text
    assert regroup(w.bob, "a1", remove=["team"]).status_code == 403, "somebody else's agent needs manage_groups"
    assert regroup(w.bob, "carol", add=["team"]).status_code == 403
    assert regroup(w.bob, "b1", remove=["team"]).status_code == 200


def test_the_switches_are_gone(w):
    my = w.alice.c.get(f"/{SLUG}/api/my").json()
    assert "switches" not in my, my.keys()
    assert w.alice.c.post(f"/{SLUG}/api/my/switches", json={"others_regroup": True}).status_code in (404, 405)
    groups = {g["name"]: g for g in w.alice.c.get(f"/{SLUG}/api/members").json()["groups"]}
    assert groups["alice-agents"]["permissions"] == [], "an ownership group carries no permission of its own any more"
    r = w.alice.c.post(f"/{SLUG}/api/groups/alice-agents", json={"permissions": ["others_regroup"]})
    assert r.status_code == 400, r.text
    for page in (f"/{SLUG}", f"/{SLUG}/me/agents", f"/{SLUG}/settings/groups"):
        html = w.alice.c.get(page).text
        assert "別人可以調整" not in html and "others_regroup" not in html, page
