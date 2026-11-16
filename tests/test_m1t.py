"""Slice 1t: tasks with a title and a body, one task per agent, the lock over title and holder only, done tasks kept
for a while, a body that must be updated every N hours, notices of open and finished tasks.

    python -m pytest tests/test_m1t.py -q
"""
from __future__ import annotations

import time

import pytest

from test_m1b import ENV, SLUG, build_world, until

UNIT_S, KEEP_S = 2, 4


@pytest.fixture(scope="module")
def t(tmp_path_factory):
    env = dict(ENV, ASTERISM_TASK_HOUR_S=str(UNIT_S), ASTERISM_TASK_DONE_KEEP_S=str(KEEP_S))
    world = build_world(tmp_path_factory.mktemp("datat"), env)
    world.alice.switches(others_assign=True)
    yield world
    world.srv.stop()


def board(person) -> dict[int, dict]:
    r = person.c.get(f"/{SLUG}/api/tasks")
    assert r.status_code == 200, r.text
    return {x["id"]: x for g in r.json()["groups"] for x in g["tasks"]}


def post(person, **body):
    r = person.c.post(f"/{SLUG}/api/tasks", json=body)
    assert r.status_code == 201, r.text
    return r.json()["task"]


def a_task(agent, **body):
    return agent.c.post(f"/{SLUG}/api/agent/task", json=body)


def system_texts(person) -> list[str]:
    return [m["text"] for m in person.read() if m["from_kind"] == "system"]


def test_a_task_has_a_title_and_a_body(t):
    x = post(t.alice, group="ai", title="  Check   the constant  ", body="Line one\n\nLine two")
    assert x["title"] == "Check the constant" and x["body"] == "Line one\n\nLine two" and "text" not in x
    assert t.alice.c.post(f"/{SLUG}/api/tasks", json={"group": "ai", "title": ""}).status_code == 400
    assert t.alice.c.post(f"/{SLUG}/api/tasks", json={"group": "ai", "title": "x" * 201}).status_code == 400
    old = post(t.alice, group="ai", text="An old program's text [t1]")
    assert old["title"] == "An old program's text [t1]" and old["body"] == ""
    assert any("Open task" in s and "Check the constant" in s for s in system_texts(t.bob)), "an open task is announced"


def test_one_task_per_agent_and_the_old_one_goes_back(t):
    one = post(t.alice, group="ai", title="first job [t2]")
    two = post(t.alice, group="ai", title="second job [t2]")
    assert a_task(t.a1, id=one["id"], responsible="a1").status_code == 200
    assert a_task(t.a1, id=two["id"], responsible="a1").status_code == 200
    b = board(t.alice)
    assert b[two["id"]]["responsible"] == "a1" and b[one["id"]]["responsible"] is None, "the first went back"
    assert sum(1 for x in b.values() if x["responsible"] == "a1" and not x["done"]) == 1


def test_a_locked_task_is_not_pushed_off_and_its_holder_keeps_the_body(t):
    locked = post(t.alice, group="ai", title="assigned by alice [t3]", responsible="a2")
    assert board(t.alice)[locked["id"]]["assigned_by"] == "alice"
    other = post(t.alice, group="ai", title="another [t3]")
    r = a_task(t.a2, id=other["id"], responsible="a2")
    assert r.status_code == 409 and r.json()["error"] == "has_locked_task", r.text
    r = t.bob.c.post(f"/{SLUG}/api/tasks/{other['id']}", json={"responsible": "a2"})
    assert r.status_code == 409 and r.json()["error"] == "has_locked_task", r.text
    assert a_task(t.a2, id=locked["id"], body="halfway there").status_code == 200, "the body is the holder's"
    assert board(t.alice)[locked["id"]]["body"] == "halfway there" and board(t.alice)[locked["id"]]["body_at"]
    r = a_task(t.a2, id=locked["id"], title="renamed by the agent")
    assert r.status_code == 403, r.text
    assert "body" in r.json()["message"], "the refusal says what the holder may do"


def test_done_frees_the_agent_and_stays_listed_for_a_while(t):
    x = post(t.alice, group="ai", title="finish me [t4]")
    assert a_task(t.b1, id=x["id"], responsible="b1").status_code == 200
    assert a_task(t.b1, id=x["id"], done=True).status_code == 200
    got = board(t.alice)[x["id"]]
    assert got["done"] is True and got["done_at"]
    assert next(a for a in t.alice.members()["agents"] if a["name"] == "b1")["busy"] is False
    assert any("finished task" in s and "finish me [t4]" in s for s in system_texts(t.alice))
    assert a_task(t.b1, id=x["id"], title="changed after done").status_code in (400, 409)
    assert until(lambda: x["id"] not in board(t.alice), KEEP_S + 6), "deleted after the keeping time"


def test_a_body_that_is_not_kept_current_is_overdue_and_its_holder_is_reminded(t):
    x = post(t.alice, group="ai", title="report often [t5]", update_every_h=1)
    assert x["update_every_h"] == 1
    assert t.alice.c.post(f"/{SLUG}/api/tasks", json={"group": "ai", "title": "x", "update_every_h": 0}).status_code == 400
    assert a_task(t.b1, id=x["id"], responsible="b1").status_code == 200
    assert board(t.alice)[x["id"]]["overdue"] is False
    got = t.b1.take(f"Task {x['id']} (report often [t5]) asks for an update", timeout=UNIT_S + 8)
    assert got["message"]["level"] == "important"
    assert board(t.alice)[x["id"]]["overdue"] is True
    assert a_task(t.b1, id=x["id"], body="on track").status_code == 200
    assert board(t.alice)[x["id"]]["overdue"] is False


def test_the_agents_tools_say_it(t):
    who = t.a1.c.get(f"/{SLUG}/api/agent/tasks").json()["tasks"]
    assert who and all({"title", "body", "done", "overdue", "update_every_h"} <= set(x) for x in who)
