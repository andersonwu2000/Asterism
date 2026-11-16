"""Frontend f5: tasks are given to agents (or to nobody), the default groups go by their names, files mode reworked
(a source dropdown, a search field above the tree, preview tabs).

    python -m pytest tests/test_m1f5.py -q
"""
from __future__ import annotations

import sqlite3

import pytest

from test_m1b import ROOT, SLUG, build_world


@pytest.fixture(scope="module")
def t(tmp_path_factory):
    data = tmp_path_factory.mktemp("dataf5")
    world = build_world(data)
    world.data = data
    yield world
    world.srv.stop()


def p_make(person, **body):
    return person.c.post(f"/{SLUG}/api/tasks", json=body)


def table(person) -> dict[int, dict]:
    r = person.c.get(f"/{SLUG}/api/tasks")
    assert r.status_code == 200, r.text
    return {x["id"]: x for g in r.json()["groups"] for x in g["tasks"]}


def test_a_person_is_never_given_a_task(t):
    r = p_make(t.alice, group="human", text="for a person [t1]", responsible="bob")
    assert r.status_code == 400 and r.json()["error"] == "not_an_agent", r.text
    assert "bob" in r.json()["message"]
    open_one = p_make(t.alice, group="human", text="for nobody [t1]")
    assert open_one.status_code == 201, open_one.text
    tid = open_one.json()["task"]["id"]
    r = t.alice.c.post(f"/{SLUG}/api/tasks/{tid}", json={"responsible": "carol"})
    assert r.status_code == 400 and r.json()["error"] == "not_an_agent", r.text
    assert table(t.alice)[tid]["responsible"] is None
    r = t.a1.c.post(f"/{SLUG}/api/agent/task", json={"id": tid, "responsible": "alice"})
    assert r.status_code == 400 and r.json()["error"] == "not_an_agent", r.text
    assert "alice" in r.json()["message"] and "agent" in r.json()["message"]
    given = p_make(t.alice, group="ai", text="for an agent [t1]", responsible="a1")
    assert given.status_code == 201 and given.json()["task"]["responsible"] == "a1"


def test_a_task_a_person_held_before_becomes_nobodys(t):
    made = p_make(t.alice, group="human", text="held by a person before [t2]")
    tid = made.json()["task"]["id"]
    t.srv.stop()
    db = sqlite3.connect(str(t.data / "projects" / f"{SLUG}.db"))
    pid = db.execute("SELECT person_id FROM people WHERE name = 'bob'").fetchone()[0]
    with db:
        db.execute("UPDATE tasks SET responsible_kind = 'person', responsible_id = ? WHERE id = ?", (pid, tid))
    db.close()
    t.srv.start()
    got = table(t.alice)[tid]
    assert got["responsible"] is None and got["responsible_kind"] is None and got["assigned_by"] is None, got


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
    assert 'aria-haspopup="menu"' in page.split('id="source-switch"', 1)[1][:400], "the source is a dropdown menu"


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
