"""Slice 1l: the member column is a tree of people with their agents under them. The scripts draw it; what these tests
can see is the page's shell (no 人 | agent control, the tree's place and the place for one sentence) and the sentence
under another person's agent, which no longer says to mention the agent (since 1e that calls nobody).

    python -m pytest tests/test_m1l.py -q
"""
from __future__ import annotations

import pytest

from test_m1b import SLUG, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datal"))
    yield world
    world.srv.stop()


def test_the_member_column_is_one_tree_without_the_people_agents_control(w):
    page = w.alice.c.get(f"/{SLUG}").text
    assert 'id="member-switch"' not in page, "the 人 | agent control is gone"
    column = page[page.index('id="member-panel"'):]
    assert 'id="member-tree"' in column and 'id="member-said"' in column
    head = column[column.index('class="right-head"'):column.index('id="member-body"')]
    assert "成員" in head, "the head is a title (the counts are filled in by the script)"


def test_the_line_under_another_persons_agent_says_how_to_reach_it_now(w):
    page = w.bob.c.get(f"/{SLUG}/agent", params={"name": "a1"}).text
    assert "在頻道裡提及 @" not in page, "mentioning another person's agent calls nobody since 1e"
    assert w.bob.c.post("/api/me/settings", json={"locale": "en"}).status_code == 200
    try:
        assert "mention @{name} in a channel" not in w.bob.c.get(f"/{SLUG}/agent", params={"name": "a1"}).text
    finally:
        assert w.bob.c.post("/api/me/settings", json={"locale": "zh-TW"}).status_code == 200
