"""Frontend f5: the default groups go by their names, files mode reworked (a source dropdown, a search field above
the tree, preview tabs).

    python -m pytest tests/test_m1f5.py -q
"""
from __future__ import annotations

import pytest

from test_m1b import ROOT, SLUG, build_world


@pytest.fixture(scope="module")
def t(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf5"))
    yield world
    world.srv.stop()


def test_the_default_groups_go_by_their_names(t):
    words = (ROOT / "asterism" / "i18n.py").read_text(encoding="utf-8")
    assert '"擁有者"' not in words and '"人類"' not in words, "owner, human, AI are written by their names"


def test_files_mode_has_a_source_dropdown_and_a_search_field_above_the_tree(t):
    page = t.alice.c.get(f"/{SLUG}/files").text
    for needed in ('id="source-switch"', 'id="files-menu"', 'id="files-search"', 'id="explorer-tree"', 'id="file-tabs"'):
        assert needed in page, needed
    left = page.split('id="explorer"', 1)[1]
    assert left.index('id="files-menu"') < left.index('id="files-search"') < left.index('id="explorer-tree"'), \
        "the menu, then the search field, then the tree"
    assert 'aria-pressed=' in page.split('id="source-switch"', 1)[1][:600], "the source is two buttons (1x)"


# ------------------------------------------------------------------ the agent page (m1f5_agent_page_design.md)

def test_the_agent_page_has_its_own_address_and_offers_inviting(t):
    for path in ("/agent", "/my"):
        r = t.alice.c.get(f"/{SLUG}{path}")
        assert r.status_code == 200 and 'id="invite-agent"' in r.text, path     # f6b: tasks and schedules moved to /work


def test_my_agents_say_which_computer_or_connector_they_came_through(t):
    my = t.alice.c.get(f"/{SLUG}/api/my").json()
    ids = {c["id"] for c in my["credentials"]}
    bound = [a for a in my["agents"] if a["name"] in ("a1", "a2")]
    assert bound and all(a.get("credential") in ids for a in bound), my["agents"]
