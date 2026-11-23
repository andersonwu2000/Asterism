"""Slice 1g: a person's private conversation with an agent lives on the agent page. The old private address of an
agent leads there; private conversations say whether the other member is a person or an agent; the private column and
the rail count people and agents apart; the timeline says the agent's own level of a message; the agent page's shell
has the two views and the chat's own message script.

    python -m pytest tests/test_m1g.py -q
"""
from __future__ import annotations

import json
import re

import pytest

from test_m1b import SLUG, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datag"))
    yield world
    world.srv.stop()


def pill(html: str, ident: str) -> tuple[bool, int]:
    """(shown, number) of a rail count as the page is first painted."""
    m = re.search(r'<span id="%s"([^>]*)>\s*<span class="pill"[^>]*>(\d+)</span>' % re.escape(ident), html)
    assert m, f"no {ident} in the page"
    return "hidden" not in m.group(1), int(m.group(2))


def test_an_agents_private_address_leads_to_its_page(w):
    for person in (w.alice, w.bob):                       # its own person, and anybody else
        r = person.c.get(f"/{SLUG}/dm/a1")
        assert r.status_code == 303 and r.headers["location"] == f"/{SLUG}/agent?name=a1", (person.name, r.status_code)
    r = w.alice.c.get(f"/{SLUG}/dm/a1", params={"m": "17"})
    assert r.status_code == 303 and r.headers["location"] == f"/{SLUG}/agent?name=a1&m=17"
    assert w.alice.c.get(f"/{SLUG}/dm/bob").status_code == 200, "a person's private page is as before"


def test_private_conversations_say_what_the_other_member_is(w):
    w.alice.say("a word for my agent [g1]", to="a1")
    w.alice.say("a word for bob [g2]", to="bob")
    private = {p["with"]: p for p in w.alice.places()["private"]}
    assert private["a1"]["kind"] == "agent" and private["bob"]["kind"] == "person", private


def test_the_private_column_and_the_rail_count_people_and_agents_apart(w):
    w.a1.say("your agent has something for you [g3]", to="alice")          # important for alice: an agent's conversation
    w.bob.say("and bob too [g4]", to="alice")                              # important for alice: a person's
    w.bob.say("once more [g5]", to="alice")
    chat = w.alice.c.get(f"/{SLUG}").text
    assert pill(chat, "rail-dm-count") == (True, 2), "people only"
    assert pill(chat, "rail-my-count") == (True, 1), "the agent button counts the conversations with agents"

    page = w.alice.c.get(f"/{SLUG}/dm").text
    column = page[page.index('id="dm-list"'):]
    column = column[:column.index("</ul>")]
    assert ">bob<" in column and ">a1<" not in column and ">a2<" not in column, "conversations with people only"
    choices = json.loads(re.search(r'id="dm-new"[^>]*data-choices="([^"]*)"', page).group(1).replace("&quot;", '"'))
    assert {c["name"] for c in choices} == {"bob", "carol"} and not any(c.get("agent") for c in choices), choices
    on_agent_page = w.alice.c.get(f"/{SLUG}/agent").text
    assert pill(on_agent_page, "rail-my-count")[0] is False, "on the agent page the list says it, not the rail"


def test_the_timeline_says_the_agents_own_level(w):
    asked = w.alice.say("@a2 a question for you [g6]")
    w.a2.take("[g6]")
    back = w.a2.say("an answer [g6a]", reply_to=asked["id"])
    w.alice.say("a note, nothing to answer [g7]", to="a2")
    w.a2.take("[g7]")
    items = w.alice.c.get(f"/{SLUG}/api/agents/a2/timeline", params={"limit": 100}).json()["items"]
    by_tag = {tag: next(x["message"] for x in items if x["kind"] == "message" and tag in x["message"]["text"])
              for tag in ("[g6]", "[g6a]", "[g7]")}
    assert by_tag["[g6]"]["agent_level"] == "important", "it was mentioned"
    assert by_tag["[g7]"]["agent_level"] == "normal", "a private message without a mention (1p)"
    assert "agent_level" not in by_tag["[g6a]"] and by_tag["[g6a]"]["id"] == back["id"], "what it sent has none"


def test_the_agent_pages_shell_has_both_views_and_the_chats_own_room(w):
    page = w.alice.c.get(f"/{SLUG}/agent", params={"name": "a1"}).text
    for ident in ("agent-views", "agent-conversation", "agent-timeline"):
        assert f'id="{ident}"' in page, ident
    assert re.search(r'<script src="/static/messages\.js', page), "對話 is the private page's room, not a copy"
    assert "對話" in page and "動態" in page
