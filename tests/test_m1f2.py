"""Groups can be changed and removed (the page "members and groups" needs both).

    python -m pytest tests/test_m1f2.py -q
"""
from __future__ import annotations

import httpx
import pytest

from test_m1b import SLUG, Person, build_world


@pytest.fixture(scope="module")
def g(tmp_path_factory):
    """alice owns the project and has the agents a1 and a2; bob has b1; carol has none."""
    world = build_world(tmp_path_factory.mktemp("dataf2"))
    yield world
    world.srv.stop()


def err(r: httpx.Response) -> str:
    return r.json().get("error", "")


def make(person: Person, name: str, permissions: list[str]) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/groups", json={"name": name, "permissions": permissions})


def change(person: Person, name: str, permissions) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/groups/{name}", json={"permissions": permissions})


def remove(person: Person, name: str) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/groups/{name}/remove")


def put(person: Person, member: str, add=(), take=()) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/members/{member}/groups", json={"add": list(add), "remove": list(take)})


def group(person: Person, name: str) -> dict | None:
    return next((x for x in person.members()["groups"] if x["name"] == name), None)


def groups_of(person: Person, member: str) -> list[str]:
    m = person.members()
    row = next(x for x in m["people"] + m["agents"] if x["name"] == member)
    return row["groups"]


def test_a_custom_groups_permissions_can_be_changed(g):
    assert make(g.alice, "team", ["read"]).status_code == 201
    r = change(g.alice, "team", ["edit_tasks", "read", "post"])
    assert r.status_code == 200, r.text
    assert r.json() == {"name": "team", "kind": "custom", "permissions": ["read", "post", "edit_tasks"]}, \
        "the answer is the group, its permissions in the catalogue's order"
    assert group(g.bob, "team")["permissions"] == ["read", "post", "edit_tasks"]
    assert change(g.alice, "team", []).status_code == 200 and group(g.alice, "team")["permissions"] == []

    assert err(change(g.alice, "team", ["read", "fly"])) == "invalid_permissions"
    assert change(g.alice, "team", "read").status_code == 400
    assert change(g.alice, "no-such-group", ["read"]).status_code == 404
    r = change(g.bob, "team", ["read"])
    assert r.status_code == 403 and err(r) == "forbidden", "changing a group needs manage_groups"
    for fixed in ("human", "ai", "owner", "alice-agents"):
        r = change(g.alice, fixed, ["read"])
        assert r.status_code == 409 and err(r) == "conflict", f"{fixed}: only a custom group is changed here"
    assert "edit_tasks" in group(g.alice, "human")["permissions"]


def test_a_change_takes_effect_at_once(g):
    assert make(g.alice, "readers", ["read", "post"]).status_code == 201
    assert put(g.alice, "carol", add=["readers"], take=["human"]).status_code == 200
    pin = lambda: g.carol.c.post(f"/{SLUG}/api/channels/general/pins", json={"path": "notes/carol.md"})
    assert pin().status_code == 403
    assert change(g.alice, "readers", ["read", "post", "create_channel"]).status_code == 200
    assert pin().status_code == 201, "carol holds what her group holds now"
    assert change(g.alice, "readers", ["read", "post"]).status_code == 200
    assert g.carol.c.post(f"/{SLUG}/api/channels/general/pins", json={"path": "notes/again.md"}).status_code == 403
    assert put(g.alice, "carol", add=["human"], take=["readers"]).status_code == 200


def test_nobody_hands_out_or_takes_away_what_they_do_not_hold(g):
    assert make(g.alice, "stewards", ["manage_groups"]).status_code == 201
    assert put(g.alice, "bob", add=["stewards"]).status_code == 200
    assert make(g.alice, "helpers", ["read"]).status_code == 201
    assert make(g.alice, "settings", ["project_settings"]).status_code == 201
    assert change(g.bob, "helpers", ["read", "post"]).status_code == 200, "bob manages groups now, within what he holds"
    r = change(g.bob, "helpers", ["read", "manage_members"])
    assert r.status_code == 403 and group(g.alice, "helpers")["permissions"] == ["read", "post"], "not more than he holds"
    r = change(g.bob, "settings", ["read"])
    assert r.status_code == 403 and group(g.alice, "settings")["permissions"] == ["project_settings"], \
        "nor may he strip a group of what he does not hold himself"
    assert remove(g.bob, "settings").status_code == 403
    assert remove(g.bob, "helpers").status_code == 200
    assert put(g.alice, "bob", take=["stewards"]).status_code == 200
    assert change(g.bob, "team", ["read"]).status_code == 403


def test_a_custom_group_can_be_removed_when_it_holds_no_task(g):
    assert make(g.alice, "lemma", ["read"]).status_code == 201
    for member in ("alice", "bob", "a1"):
        assert put(g.alice, member, add=["lemma"]).status_code == 200
    held = g.alice.c.post(f"/{SLUG}/api/tasks", json={"group": "lemma", "text": "The open question [rm1]"})
    assert held.status_code == 201, held.text
    r = remove(g.alice, "lemma")
    assert r.status_code == 409 and err(r) == "conflict" and "1" in r.json()["message"], "its tasks are dealt with first"
    assert group(g.alice, "lemma") is not None and "lemma" in groups_of(g.alice, "a1")
    assert g.alice.c.post(f"/{SLUG}/api/tasks/{held.json()['task']['id']}/remove").status_code == 200

    r = remove(g.alice, "lemma")
    assert r.status_code == 200 and r.json() == {"removed": "lemma"}
    assert group(g.alice, "lemma") is None
    assert all("lemma" not in groups_of(g.alice, m) for m in ("alice", "bob", "a1")), "its members are simply no longer in it"
    assert remove(g.alice, "lemma").status_code == 404
    assert make(g.alice, "lemma", ["read", "post"]).status_code == 201, "the name is free again"
    assert groups_of(g.alice, "bob").count("lemma") == 0, "and nobody is in the new group of that name"

    for fixed in ("human", "ai", "owner", "bob-agents"):
        r = remove(g.alice, fixed)
        assert r.status_code == 409 and err(r) == "conflict", f"{fixed} is not removed"
    assert remove(g.carol, "lemma").status_code == 403
    sent = g.alice.say("@team are you there? [rm2]")
    assert remove(g.alice, "team").status_code == 200
    again = g.alice.say("@team and now? [rm3]")
    assert [m["name"] for m in sent["mentions"]] == ["team"] and sent["mentions"][0].get("group") is True
    assert [m.get("result") for m in again["mentions"]] == ["unknown"], "its name mentions nobody any more"


def test_the_members_page_shows_groups_and_who_may_change_them(g):
    page = g.alice.c.get(f"/{SLUG}/members")
    assert page.status_code == 200
    for needed in ('id="groups"', 'id="group-detail"', 'id="group-create"'):
        assert needed in page.text, needed
    theirs = g.carol.c.get(f"/{SLUG}/members")
    assert theirs.status_code == 200 and 'id="groups"' in theirs.text and 'id="group-create"' not in theirs.text, \
        "who may not manage groups sees them and is offered no form"
