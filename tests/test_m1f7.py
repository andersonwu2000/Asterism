"""f7: what the two reviews asked for that a test can hold: tasks remember who posted them and when they were taken;
the owner group takes no channel override; unused invitations are listed and revoked; a private conversation that
is not allowed is answered inside the frame.

    python -m pytest tests/test_m1f7.py -q
"""
from __future__ import annotations

import urllib.parse

import httpx
import pytest

from test_m1b import SLUG, Person, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf7"))
    yield world
    world.srv.stop()


def task(person, tid) -> dict:
    groups = person.c.get(f"/{SLUG}/api/tasks").json()["groups"]
    return next(x for g in groups for x in g["tasks"] if x["id"] == tid)


def test_a_task_remembers_who_posted_it_and_when_it_was_taken(w):
    r = w.carol.c.post(f"/{SLUG}/api/tasks", json={"group": "ai", "text": "a bounty [b1]"})
    assert r.status_code == 201, r.text
    tid = r.json()["task"]["id"]
    t = task(w.alice, tid)
    assert t["posted_by"] == "carol" and t["posted_at"] and t["taken_at"] is None, t
    r = w.a1.c.post(f"/{SLUG}/api/agent/task", json={"id": tid, "responsible": "a1"})
    assert r.status_code == 200, r.text
    t = task(w.alice, tid)
    assert t["taken_at"] and t["posted_by"] == "carol"
    mine = w.a1.c.get(f"/{SLUG}/api/agent/tasks").json()["tasks"]
    assert next(x for x in mine if x["id"] == tid)["posted_by"] == "carol", "agents see it too"
    made_by_agent = w.a2.c.post(f"/{SLUG}/api/agent/task", json={"group": "ai", "text": "an agent's bounty [b1]"})
    assert made_by_agent.status_code == 200, made_by_agent.text
    assert task(w.alice, made_by_agent.json()["task"]["id"])["posted_by"] == "a2"


def test_the_owner_group_takes_no_channel_override(w):
    r = w.alice.c.post(f"/{SLUG}/api/channels/general/permissions", json={"overrides": {"owner": {"read": "deny"}}})
    assert r.status_code == 400, r.text
    got = w.alice.c.get(f"/{SLUG}/api/channels/general/permissions").json()["overrides"]
    assert got.get("owner", {}).get("read", "inherit") == "inherit"


def test_unused_invitations_are_listed_and_revoked(w):
    made = w.alice.c.post(f"/{SLUG}/api/invites", json={"github_login": "dora"})
    assert made.status_code == 201, made.text
    listed = w.alice.c.get(f"/{SLUG}/api/invites")
    assert listed.status_code == 200, listed.text
    row = next(i for i in listed.json()["invites"] if i["github_login"] == "dora")
    assert {"id", "created", "expires"} <= set(row) and "url" not in row, "the link is shown once"
    assert w.carol.c.get(f"/{SLUG}/api/invites").status_code == 403
    assert w.carol.c.post(f"/{SLUG}/api/invites/{row['id']}/revoke").status_code == 403
    assert w.alice.c.post(f"/{SLUG}/api/invites/{row['id']}/revoke").status_code == 200
    assert all(i["id"] != row["id"] for i in w.alice.c.get(f"/{SLUG}/api/invites").json()["invites"])
    dora = Person(w.srv, "dora")
    path = urllib.parse.urlparse(made.json()["url"]).path
    assert dora.c.post(path).status_code in (400, 404, 410), "a revoked invitation no longer works"


def test_a_private_conversation_not_allowed_is_answered_inside_the_frame(w):
    r = w.bob.c.get(f"/{SLUG}/dm/a1")
    assert r.status_code == 403 and 'id="rail"' in r.text, r.status_code
    assert "alice" in r.text, "it says whose agent it is"
    assert httpx.get(f"{w.srv.url}/{SLUG}/dm/a1", follow_redirects=False).status_code in (302, 303, 401)
