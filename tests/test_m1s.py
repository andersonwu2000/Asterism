"""Slice 1s: statuses instead of tasks. Each agent has one status (a title and a body) that it writes itself; its
person may ask for it to be updated every N hours; people have a status too, a title only. Busy is withdrawn: a
status changes no delivery.

    python -m pytest tests/test_m1s.py -q
"""
from __future__ import annotations

import secrets

import httpx
import pytest

from test_m1b import ENV, SLUG, build_world

UNIT_S = 2


@pytest.fixture(scope="module")
def s(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datas"), dict(ENV, ASTERISM_STATUS_HOUR_S=str(UNIT_S)))
    yield world
    world.srv.stop()


def set_status(agent, **body) -> httpx.Response:
    return agent.c.post(f"/{SLUG}/api/agent/status", json=body)


def statuses(agent) -> dict[str, dict]:
    r = agent.c.get(f"/{SLUG}/api/agent/statuses")
    assert r.status_code == 200, r.text
    return {x["agent"]: x for x in r.json()["statuses"]}


def board(person) -> dict:
    r = person.c.get(f"/{SLUG}/api/statuses")
    assert r.status_code == 200, r.text
    return r.json()


def member(person, name) -> dict:
    m = person.members()
    return next(x for x in m["agents"] + m["people"] if x["name"] == name)


def every(person, agent, hours) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/agents/{agent}/update-every", json={"hours": hours})


# ------------------------------------------------------------------ an agent's status

def test_an_agent_writes_its_own_status(s):
    assert statuses(s.a1)["a1"]["title"] == "" and statuses(s.a1)["a1"]["at"] is None, "no status yet"
    r = set_status(s.a1, title="  Checking   Lemma 3.2  ", body="Step 1 done.\n\nStep 2 next.")
    assert r.status_code == 200, r.text
    mine = statuses(s.a1)["a1"]
    assert mine["title"] == "Checking Lemma 3.2" and mine["body"] == "Step 1 done.\n\nStep 2 next." and mine["at"]
    assert mine["person"] == "alice" and mine["update_every_h"] is None and mine["overdue"] is False
    assert set_status(s.a1, body="Step 2 done.").status_code == 200, "a field left out keeps its value"
    assert statuses(s.a1)["a1"]["title"] == "Checking Lemma 3.2" and statuses(s.a1)["a1"]["body"] == "Step 2 done."
    assert statuses(s.b1)["a1"]["title"] == "Checking Lemma 3.2", "an agent sharing a group reads it"
    assert set_status(s.a1, title="").status_code == 200
    assert (statuses(s.a1)["a1"]["title"], statuses(s.a1)["a1"]["body"]) == ("", ""), "an empty title clears both"
    r = set_status(s.a1, body="a body with no title")
    assert r.status_code == 400 and r.json()["error"] == "bad_request", r.text
    for big in ({"title": "x" * 201}, {"title": "ok", "body": "x" * 10_001}):
        r = set_status(s.a1, **big)
        assert r.status_code == 400 and r.json()["error"] == "too_long", r.text


def test_a_status_is_written_once_per_key_and_in_the_timeline(s):
    key = {"Idempotency-Key": secrets.token_hex(16)}
    body = {"title": "Reading the 1987 paper [s2]"}
    one = s.a2.c.post(f"/{SLUG}/api/agent/status", json=body, headers=key)
    two = s.a2.c.post(f"/{SLUG}/api/agent/status", json=body, headers=key)
    assert one.status_code == 200 and two.status_code == 200, (one.text, two.text)
    assert two.headers.get("idempotent-replayed") == "true"
    r = s.alice.c.get(f"/{SLUG}/api/agents/a2/timeline", params={"limit": 50})
    assert r.status_code == 200, r.text
    noted = [x for x in r.json()["items"] if x["kind"] == "state" and x["state"] == "status"]
    assert [x["title"] for x in noted] == ["Reading the 1987 paper [s2]"], noted
    assert not [m for m in s.alice.read() if "[s2]" in m["text"]], "no channel notice"


def test_people_see_every_status_on_the_dashboard_and_in_the_member_list(s):
    assert set_status(s.b1, title="Writing section 4 [s3]", body="Half done").status_code == 200
    got = board(s.carol)
    row = next(x for x in got["agents"] if x["agent"] == "b1")
    assert row["title"] == "Writing section 4 [s3]" and row["body"] == "Half done" and row["person"] == "bob"
    assert "groups" in row and row["groups"], row
    m = member(s.carol, "b1")
    assert m["status"]["title"] == "Writing section 4 [s3]" and m["status"]["overdue"] is False
    assert "busy" not in m, "busy is withdrawn"


# ------------------------------------------------------------------ updates every N hours

def test_only_the_agents_person_asks_for_updates_and_a_late_agent_is_reminded(s):
    assert every(s.bob, "a1", 1).status_code == 403, "not bob's agent"
    assert every(s.alice, "a1", 0).status_code == 400 and every(s.alice, "a1", 169).status_code == 400
    assert every(s.alice, "a1", 1).status_code == 200
    assert statuses(s.a1)["a1"]["update_every_h"] == 1 and statuses(s.a1)["a1"]["overdue"] is False
    got = s.a1.take("Your person asked for a status update every 1 h", timeout=UNIT_S + 8)
    assert got["message"]["level"] == "important" and got["message"]["from_kind"] == "system"
    assert "set_status" in got["message"]["text"]
    assert statuses(s.a1)["a1"]["overdue"] is True and member(s.alice, "a1")["status"]["overdue"] is True
    assert not [m for m in s.bob.read() if "asked for a status update" in m["text"]], "nobody else is told"
    assert set_status(s.a1, title="Back on it [s4]").status_code == 200
    assert statuses(s.a1)["a1"]["overdue"] is False
    assert every(s.alice, "a1", None).status_code == 200
    assert statuses(s.a1)["a1"]["update_every_h"] is None


# ------------------------------------------------------------------ a person's status

def test_a_person_has_a_title_only(s):
    r = s.carol.c.post(f"/{SLUG}/api/me/status", json={"title": "  Reading   about tori ", "body": "ignored"})
    assert r.status_code == 200, r.text
    assert member(s.alice, "carol")["status"]["title"] == "Reading about tori"
    me = next(x for x in board(s.alice)["people"] if x["name"] == "carol")
    assert me["title"] == "Reading about tori" and "body" not in me
    assert s.carol.c.post(f"/{SLUG}/api/me/status", json={"title": "x" * 201}).status_code == 400
    assert s.carol.c.post(f"/{SLUG}/api/me/status", json={"title": ""}).status_code == 200
    assert member(s.alice, "carol")["status"]["title"] == ""


# ------------------------------------------------------------------ what is withdrawn

def test_tasks_and_busy_are_gone(s):
    assert s.alice.c.get(f"/{SLUG}/api/tasks").status_code == 404
    assert s.alice.c.post(f"/{SLUG}/api/tasks", json={"group": "ai", "title": "x"}).status_code in (404, 405)
    assert s.a1.c.get(f"/{SLUG}/api/agent/tasks").status_code == 404
    who = s.a1.c.get(f"/{SLUG}/api/agent/whoami").json()
    assert all("busy" not in a for a in who["agents"]), who
    perms = s.alice.c.get(f"/{SLUG}/api/my").json()
    text = str(perms)
    for gone in ("assign_tasks", "edit_tasks", "coordinate_tasks", "others_assign"):
        assert gone not in text, gone


def test_a_status_changes_no_delivery(s):
    """Channel talk reaches an agent with a status as it reaches one without (busy is withdrawn)."""
    s.a2.say("I follow this channel [s5]", to="#general")
    assert set_status(s.a2, title="Deep in a proof [s5]").status_code == 200
    s.alice.say("a thought for whoever listens [s5b]")
    assert s.a2.take("[s5b]")["message"]["level"] == "normal"


# ------------------------------------------------------------------ the pages

def test_the_task_page_is_the_dashboard(s):
    r = s.alice.c.get(f"/{SLUG}/work")
    assert r.status_code == 200 and "儀表板" in r.text, r.text[:300]
    assert "任務表" not in r.text and "tasktable.js" not in r.text
