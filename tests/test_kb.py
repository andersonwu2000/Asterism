"""kb_entries schema + helpers (Phase 12 informal knowledge base)."""
import re
import sqlite3

import pytest

from Tooling.state import db, kb


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")  # mirror db.connect (FK enforced)
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?,?,?)",
        ("P", "P/Manifest.md", db.now()),
    )
    c.commit()
    return c


def _check_values(conn: sqlite3.Connection, table: str, col: str) -> set[str]:
    """Value set of a `CHECK(<col> IN (...))` constraint from the live CREATE
    SQL — introspected, not parsed from a copy of the schema string."""
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()["sql"]
    m = re.search(rf"CHECK\(\s*{col}\s+IN\s*\(([^)]*)\)", sql)
    assert m, f"no CHECK({col} IN ...) found on table {table}"
    return set(re.findall(r"'([^']*)'", m.group(1)))


def test_kb_type_check_matches_runtime(conn):
    assert _check_values(conn, "kb_entries", "type") == set(kb.KB_TYPES)


def test_kb_has_no_scope_column(conn):
    """`scope` was dropped in Phase 12 — breadth reads off `node_id` alone."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(kb_entries)")}
    assert "scope" not in cols
    assert "node_id" in cols


def test_insert_and_read_roundtrip(conn):
    rid = kb.insert_entry(
        conn, entry_type="lesson", title="t1", body="b1", problem="P",
        provenance="reflection",
    )
    assert rid > 0
    rows = kb.entries_for_problem(conn, "P")
    assert len(rows) == 1
    r = rows[0]
    assert r["type"] == "lesson"
    assert r["title"] == "t1"
    assert r["body"] == "b1"
    assert r["provenance"] == "reflection"


def test_insert_rejects_bad_enum(conn):
    with pytest.raises(ValueError):
        kb.insert_entry(conn, entry_type="bogus", title="x", problem="P")


def test_query_splits_by_type(conn):
    kb.insert_entry(conn, entry_type="lesson", title="L", problem="P")
    kb.insert_entry(conn, entry_type="antipattern", title="A", problem="P")
    g = kb.query(conn, problem="P")
    assert [r["title"] for r in g["lessons"]] == ["L"]
    assert [r["title"] for r in g["antipatterns"]] == ["A"]
    assert kb.query(conn, problem="Q") == {"lessons": [], "antipatterns": []}


def test_query_filters_node_antipatterns_to_own_goal(conn):
    for gid in (1, 2):
        conn.execute(
            "INSERT INTO goals (id, problem, slug, lean_path, statement, origin,"
            " status, created_at, updated_at)"
            " VALUES (?, 'P', ?, ?, 'True', 'root', 'open', ?, ?)",
            (gid, f"s{gid}", f"P/proofs/L_s{gid}.lean", db.now(), db.now()))
    conn.commit()
    kb.insert_entry(conn, entry_type="antipattern", title="ap1", problem="P",
                    node_id=1)
    kb.insert_entry(conn, entry_type="antipattern", title="ap2", problem="P",
                    node_id=2)
    kb.insert_entry(conn, entry_type="lesson", title="L", problem="P")
    # goal 1: its OWN node antipattern + the problem-wide lesson (not ap2)
    g1 = kb.query(conn, problem="P", goal_id=1)
    assert [r["title"] for r in g1["antipatterns"]] == ["ap1"]
    assert [r["title"] for r in g1["lessons"]] == ["L"]
    # no goal_id → unfiltered (both antipatterns)
    assert len(kb.query(conn, problem="P")["antipatterns"]) == 2


def _seed_goal(conn, gid):
    conn.execute(
        "INSERT INTO goals (id, problem, slug, lean_path, statement, origin,"
        " status, created_at, updated_at)"
        " VALUES (?, 'P', ?, ?, 'True', 'root', 'open', ?, ?)",
        (gid, f"s{gid}", f"P/proofs/L_s{gid}.lean", db.now(), db.now()))
    conn.commit()


def test_add_lesson_anchors_and_idempotent(conn):
    _seed_goal(conn, 1)
    # global (NULL) + node-bound, each idempotent on provenance
    assert kb.add_lesson(conn, problem="P", title="glob",
                         provenance="reflection:s1") == 1
    assert kb.add_lesson(conn, problem="P", title="glob-dup",
                         provenance="reflection:s1") == 0  # same prov → no-op
    assert kb.add_lesson(conn, problem="P", title="nodey", node_id=1,
                         provenance="reflection:s2") == 1
    rows = {r["title"]: r for r in kb.entries_for_problem(conn, "P")}
    assert set(rows) == {"glob", "nodey"}
    assert rows["glob"]["node_id"] is None
    assert rows["nodey"]["node_id"] == 1


def test_query_filters_node_lessons_to_own_goal(conn):
    _seed_goal(conn, 1)
    _seed_goal(conn, 2)
    kb.add_lesson(conn, problem="P", title="glob", provenance="r:g")
    kb.add_lesson(conn, problem="P", title="n1", node_id=1, provenance="r:1")
    kb.add_lesson(conn, problem="P", title="n2", node_id=2, provenance="r:2")
    # goal 1 sees global + its own node lesson, NOT goal 2's
    g1 = kb.query(conn, problem="P", goal_id=1)
    assert {r["title"] for r in g1["lessons"]} == {"glob", "n1"}
    # no goal_id → all lessons
    assert len(kb.query(conn, problem="P")["lessons"]) == 3


def test_edit_global_lesson_scoped(conn):
    _seed_goal(conn, 1)
    gid = None
    kb.add_lesson(conn, problem="P", title="orig", body="b0",
                  provenance="r:edit")
    gid = kb.global_lessons(conn, "P")[0]["id"]
    nid_row = kb.add_lesson(conn, problem="P", title="node", node_id=1,
                            provenance="r:node")
    assert nid_row == 1
    node_lesson_id = [r["id"] for r in kb.entries_for_problem(conn, "P")
                      if r["title"] == "node"][0]
    # edit the global in place
    assert kb.edit_global_lesson(conn, entry_id=gid, problem="P",
                                 title="fixed", body="b1") == 1
    g = kb.global_lessons(conn, "P")
    assert (g[0]["title"], g[0]["body"]) == ("fixed", "b1")
    # cannot touch a node-bound lesson (node_id NOT NULL) via global edit
    assert kb.edit_global_lesson(conn, entry_id=node_lesson_id, problem="P",
                                 title="hax") == 0
    # cannot touch another problem's id
    assert kb.edit_global_lesson(conn, entry_id=gid, problem="Q",
                                 title="hax") == 0


def test_context_section_renders_kb(conn):
    """The read path (_section_lessons_inline) surfaces KB lessons +
    antipatterns; empty problem → no section."""
    from Tooling.agent import context
    kb.insert_entry(conn, entry_type="lesson", title="L1", problem="P",
                    provenance="reflection")
    kb.insert_entry(conn, entry_type="antipattern", title="AP",
                    body="why it failed\nsecond line", problem="P",
                    provenance="drafts_blocker")
    text = "\n".join(context._section_lessons_inline(conn, "P"))
    assert "## Lessons learned on this problem" in text
    assert "- L1" in text
    assert "## Antipatterns on this problem" in text
    assert "- AP" in text
    assert "  why it failed" in text   # body indented under the bullet
    assert "  second line" in text
    assert context._section_lessons_inline(conn, "Q") == []  # no entries


def test_node_fk_set_null_on_goal_delete(conn):
    """A vanished node (deleted goal) leaves its entry problem-scoped, not
    dropped — ON DELETE SET NULL on kb_entries.node_id."""
    conn.execute(
        "INSERT INTO goals (id, problem, slug, lean_path, statement, origin,"
        " status, created_at, updated_at)"
        " VALUES (9, 'P', 's', 'P/proofs/L_s.lean', 'True', 'root', 'open',"
        " ?, ?)",
        (db.now(), db.now()),
    )
    conn.commit()
    rid = kb.insert_entry(conn, entry_type="antipattern", title="a",
                          problem="P", node_id=9)
    conn.execute("DELETE FROM goals WHERE id = 9")
    conn.commit()
    row = conn.execute(
        "SELECT node_id FROM kb_entries WHERE id = ?", (rid,)).fetchone()
    assert row["node_id"] is None
