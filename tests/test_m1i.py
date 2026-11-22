"""Slice 1i: the invite panel tells how dot (ChatGPT) joins, through a connector rather than a link, and the
terminal commands of a link's result are folded as an advanced part.

    python -m pytest tests/test_m1i.py -q
"""
from __future__ import annotations

import pytest

from test_m1b import SLUG, build_world

DOT_SAY = "Register on Asterism with the name dot."


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datai"))
    yield world
    world.srv.stop()


def test_the_invite_panel_tells_how_dot_joins(w):
    page = w.alice.c.get(f"/{SLUG}")
    assert page.status_code == 200, page.text[:300]
    html = page.text
    start = html.index('id="invite-panel"')
    panel = html[start:]
    assert 'id="invite-dot"' in panel, "a part for ChatGPT (dot)"
    assert f"/{SLUG}/mcp" in panel, "the connector address"
    assert "OAuth" in panel and DOT_SAY in panel
    assert "ChatGPT" in panel and "Claude Code" in panel, "the two choices"


def test_the_terminal_commands_are_folded(w):
    js = w.alice.c.get("/static/base.js")
    assert js.status_code == 200
    assert "invite-advanced" in js.text and '"details"' in js.text, "a closed <details> holds the commands"
    assert "進階：自己在終端機設定這台電腦" in w.alice.c.get(f"/{SLUG}").text
    assert w.alice.c.post("/api/me/settings", json={"locale": "en"}).status_code == 200
    try:
        assert "Advanced: set up this computer yourself in a terminal" in w.alice.c.get(f"/{SLUG}").text
    finally:
        assert w.alice.c.post("/api/me/settings", json={"locale": "zh-TW"}).status_code == 200
