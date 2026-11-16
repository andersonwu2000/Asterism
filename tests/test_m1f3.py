"""Frontend f3: the project menu, project and channel settings as one layer, people and channels in chat, and search
over messages for people.

    python -m pytest tests/test_m1f3.py -q
"""
from __future__ import annotations

import httpx
import pytest

from test_m1b import SLUG, build_world


@pytest.fixture(scope="module")
def s(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf3"))
    yield world
    world.srv.stop()


def search(person, **params) -> httpx.Response:
    return person.c.get(f"/{SLUG}/api/search", params=params)


def found(person, **params) -> list[dict]:
    r = search(person, **params)
    assert r.status_code == 200, r.text
    return r.json()["results"]


# ------------------------------------------------------------------ search

def test_search_finds_messages_by_all_their_words_newest_first(s):
    one = s.alice.say("Orbit lemma draft [fs1]")
    two = s.bob.say("the ORBIT lemma, second try [fs1]")
    s.alice.say("orbit without the other word [fs1]")
    got = found(s.carol, q="orbit LEMMA fs1")
    assert [m["id"] for m in got] == [two["id"], one["id"]], "every word, any case, newest first"
    assert all(m["in"] == "#general" for m in got)
    sample = s.carol.read("#general")[-1]
    assert set(sample) - {"in"} <= set(got[0]), "a result has the shape of a message in api/messages"


def test_search_by_place_and_by_sender(s):
    s.alice.c.post(f"/{SLUG}/api/channels", json={"name": "side"})
    in_side = s.alice.say("kept apart [fs2]", to="#side")
    s.alice.say("in general [fs2]")
    s.a1.say("from an agent [fs2]", to="#general")
    assert [m["id"] for m in found(s.bob, q="fs2", **{"in": "#side"})] == [in_side["id"]]
    assert [m["text"] for m in found(s.bob, q="fs2", **{"from": "a1"})] == ["from an agent [fs2]"]
    assert found(s.bob, **{"from": "a1"}), "a filter alone is a search"
    assert all(m["from_kind"] == "system" for m in found(s.bob, **{"from": "system"}))


def test_private_conversations_are_found_only_by_who_is_in_them(s):
    secret = s.alice.say("between us two [fs3]", to="bob")
    assert [m["id"] for m in found(s.bob, q="fs3")] == [secret["id"]]
    assert found(s.bob, q="fs3")[0]["in"] == "alice", "a private place is named by the other member"
    assert [m["id"] for m in found(s.alice, q="fs3")] == [secret["id"]]
    assert found(s.carol, q="fs3") == [], "carol is not in it"
    assert found(s.bob, q="fs3", **{"in": "alice"})[0]["id"] == secret["id"]


def test_search_pages_with_before_and_limit(s):
    ids = [s.alice.say(f"page {i} [fs4]")["id"] for i in range(5)]
    first = search(s.bob, q="fs4", limit=2).json()
    assert [m["id"] for m in first["results"]] == ids[:2:-1][:2] and first["more"] is True
    rest = search(s.bob, q="fs4", limit=10, before=first["results"][-1]["id"]).json()
    assert [m["id"] for m in rest["results"]] == list(reversed(ids[:3])) and rest["more"] is False


def test_search_refuses_what_it_cannot_do(s):
    r = search(s.bob)
    assert r.status_code == 400 and r.json()["error"] == "empty_search"
    assert search(s.bob, q="   ").status_code == 400
    assert search(s.bob, q="x", **{"from": "nobody-here"}).status_code == 404
    assert search(s.bob, q="x", **{"in": "#nowhere"}).status_code == 404
    assert search(s.bob, q="x", limit=0).status_code == 400 and search(s.bob, q="x", limit=101).status_code == 400
    outsider = httpx.get(f"{s.srv.url}/{SLUG}/api/search", params={"q": "x"})
    assert outsider.status_code in (401, 403)


# ------------------------------------------------------------------ the pages

def test_the_chat_page_has_the_project_menu_and_the_new_channel_bar(s):
    page = s.alice.c.get(f"/{SLUG}").text
    for needed in ('id="project-menu-button"', 'id="project-menu"', 'id="members-toggle"', 'id="search-open"',
                   'id="search-results"'):
        assert needed in page, needed
    assert 'aria-haspopup="menu"' in page and 'role="menu"' in page
    for gone in ('id="settings-toggle"', 'id="invite-open"', 'id="pins-toggle"', 'id="task-toggle"'):
        assert gone not in page, f"{gone} is gone (f4)"


def test_the_rail_leads_to_chat_private_files_schedules_and_my_agents_only(s):
    page = s.alice.c.get(f"/{SLUG}").text
    rail = page.split('id="rail"', 1)[1].split("</nav>", 1)[0]
    assert f'href="/{SLUG}/members"' not in rail and f'href="/{SLUG}/admin"' not in rail and "/settings" not in rail
    for href in (f'/{SLUG}/dm', f'/{SLUG}/files', f'/{SLUG}/agent'):     # f5: one agent page for agents, tasks, schedules
        assert href in rail, href


def test_project_settings_are_one_layer_with_sections(s):
    for path in ("/settings", "/settings/overview", "/settings/members", "/settings/groups", "/settings/invites",
                 "/members", "/admin"):
        r = s.alice.c.get(f"/{SLUG}{path}")
        assert r.status_code == 200, path
        assert 'id="settings-nav"' in r.text and 'id="settings-close"' in r.text, path
    assert s.alice.c.get(f"/{SLUG}/settings/nothing-here").status_code == 404
    carol = s.carol.c.get(f"/{SLUG}/settings/groups")
    assert carol.status_code == 200 and 'id="settings-nav"' in carol.text, "every member may read members and groups"
    assert httpx.get(f"{s.srv.url}/{SLUG}/settings", follow_redirects=False).status_code in (302, 303, 401)


def test_channel_settings_are_the_same_layer(s):
    r = s.alice.c.get(f"/{SLUG}/channels/general/settings")
    assert r.status_code == 200 and 'id="settings-nav"' in r.text and 'id="settings-close"' in r.text
    assert s.alice.c.get(f"/{SLUG}/channels/no-such/settings").status_code == 404
