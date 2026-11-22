"""f6b: the agent page lists every agent and shows one agent's timeline (its messages and state changes, as far as the
reader may read them), where its own person can talk to it; the dashboard and scheduled messages are one page.

    python -m pytest tests/test_m1f6b.py -q
"""
from __future__ import annotations

import time

import httpx
import pytest

from test_m1b import ENV, SLUG, build_world, until

OFFLINE_S = 3


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf6b"), dict(ENV, ASTERISM_OFFLINE_AFTER_S=str(OFFLINE_S)))
    yield world
    world.srv.stop()


def timeline(person, agent, **params) -> httpx.Response:
    return person.c.get(f"/{SLUG}/api/agents/{agent}/timeline", params=params)


def items(person, agent, **params) -> list[dict]:
    r = timeline(person, agent, **params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def texts(xs) -> list[str]:
    return [x["message"]["text"] for x in xs if x["kind"] == "message"]


def test_the_timeline_holds_what_the_agent_sent_and_was_handed(w):
    w.a1.say("a1 speaking [t1]", to="#general")
    w.alice.say("@a1 for you [t1]")
    w.a1.take("for you [t1]")
    got = items(w.alice, "a1")
    sent = next(x for x in got if x["kind"] == "message" and x["message"]["text"] == "a1 speaking [t1]")
    received = next(x for x in got if x["kind"] == "message" and x["message"]["text"] == "@a1 for you [t1]")
    assert sent["dir"] == "sent" and received["dir"] == "received"
    ids = [x["message"]["id"] for x in got if x["kind"] == "message"]
    assert ids == sorted(ids), "oldest first, newest at the bottom"


def test_the_timeline_shows_only_what_the_reader_may_read(w):
    w.alice.say("private to my agent [t2]", to="a1")
    w.a1.take("private to my agent [t2]")
    assert "private to my agent [t2]" in texts(items(w.alice, "a1"))
    assert "private to my agent [t2]" not in texts(items(w.bob, "a1")), "bob is not in that conversation"
    assert "a1 speaking [t1]" in texts(items(w.bob, "a1")), "channels bob reads are shown"
    assert timeline(w.bob, "nobody-here").status_code == 404
    assert httpx.get(f"{w.srv.url}/{SLUG}/api/agents/a1/timeline").status_code in (401, 403)


def test_the_timeline_holds_state_changes(w):
    w.a2.c.post(f"/{SLUG}/api/agent/leave", json={})
    states = until(lambda: [x for x in items(w.alice, "a2") if x["kind"] == "state" and x["state"] == "offline"], 8)
    assert states, items(w.alice, "a2")
    assert all("at" in x for x in states)


def test_the_timeline_pages_with_before(w):
    for i in range(6):
        w.a1.say(f"page {i} [t4]", to="#general")
    first = timeline(w.alice, "a1", limit=3).json()
    assert len(first["items"]) == 3 and first["more"] is True
    oldest = min(x["message"]["id"] for x in first["items"] if x["kind"] == "message")
    older = timeline(w.alice, "a1", limit=3, before=oldest).json()["items"]
    assert older and all(x["message"]["id"] < oldest for x in older if x["kind"] == "message")


def test_the_agent_page_and_the_work_page(w):
    page = w.alice.c.get(f"/{SLUG}/agent")
    assert page.status_code == 200 and 'id="agent-list"' in page.text and 'id="agent-timeline"' in page.text
    for path in ("/agent", "/my"):
        assert 'id="invite-agent"' in w.alice.c.get(f"/{SLUG}{path}").text, path
    for path, tab in (("/work", None), ("/work/schedules", "schedules"), ("/agent/tasks", None),
                      ("/agent/schedules", "schedules"), ("/schedules", "schedules")):
        r = w.alice.c.get(f"/{SLUG}{path}")
        assert r.status_code == 200, path
        assert 'id="work-tabs"' in r.text, path
        assert (f'data-tab="{tab}"' if tab else "儀表板") in r.text, path      # 1s: the task tab is the dashboard
    rail = w.alice.c.get(f"/{SLUG}").text.split('id="rail"', 1)[1].split("</nav>", 1)[0]
    assert f'href="/{SLUG}/agent"' in rail and f'href="/{SLUG}/work"' in rail
