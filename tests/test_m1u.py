"""Upgrades of an existing database at start: the old switch columns of `groups` are moved into the permissions and
then the table is rebuilt without them (SQLite before 3.35 has no DROP COLUMN, so the rebuild is by copy).

    python -m pytest tests/test_m1u.py -q
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from test_m1b import SLUG, build_world

OLD = ("others_mention", "others_channel", "others_assign", "others_regroup")


@pytest.fixture(scope="module")
def u(tmp_path_factory):
    data = tmp_path_factory.mktemp("datau")
    world = build_world(data)
    world.data = data
    yield world
    world.srv.stop()


def test_the_old_switch_columns_are_moved_and_then_dropped(u):
    a1_groups_before = next(a for a in u.alice.c.get(f"/{SLUG}/api/members").json()["agents"] if a["name"] == "a1")["groups"]
    u.srv.stop()
    path = u.data / "projects" / f"{SLUG}.db"
    db = sqlite3.connect(str(path))
    with db:
        for c in OLD:                                  # as a database made before f6 looked
            db.execute(f"ALTER TABLE groups ADD COLUMN {c} INTEGER NOT NULL DEFAULT 0")
        db.execute("UPDATE groups SET others_mention = 1, others_assign = 1 WHERE name = 'alice-agents'")
        db.execute("DELETE FROM upgrades WHERE name = 'switches_moved'")
    db.close()
    u.srv.start()
    groups = {g["name"]: g for g in u.alice.c.get(f"/{SLUG}/api/members").json()["groups"]}
    assert {"others_mention", "others_assign"} <= set(groups["alice-agents"]["permissions"]), groups["alice-agents"]
    assert not {"others_channel", "others_regroup"} & set(groups["alice-agents"]["permissions"])
    u.srv.stop()
    db = sqlite3.connect(str(path))
    cols = [r[1] for r in db.execute("PRAGMA table_info(groups)")]
    assert not set(OLD) & set(cols), cols
    assert db.execute("PRAGMA foreign_key_check").fetchall() == [], "memberships and tasks still point at their groups"
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    perms = json.loads(db.execute("SELECT permissions FROM groups WHERE name = 'alice-agents'").fetchone()[0])
    assert "others_mention" in perms
    db.close()
    u.srv.start()
    a1 = next(a for a in u.alice.c.get(f"/{SLUG}/api/members").json()["agents"] if a["name"] == "a1")
    assert a1["groups"] == a1_groups_before, "nobody lost a group"
    u.srv.stop()
    u.srv.start()                                      # and a second start changes nothing
    again = {g["name"]: g["permissions"] for g in u.alice.c.get(f"/{SLUG}/api/members").json()["groups"]}
    assert again["alice-agents"] == groups["alice-agents"]["permissions"]
