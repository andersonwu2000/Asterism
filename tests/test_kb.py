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


def test_kb_scope_check_matches_runtime(conn):
    assert _check_values(conn, "kb_entries", "scope") == set(kb.KB_SCOPES)


def test_insert_and_read_roundtrip(conn):
    rid = kb.insert_entry(
        conn, entry_type="lesson", title="t1", body="b1", problem="P",
        scope="problem", provenance="reflection",
    )
    assert rid > 0
    rows = kb.entries_for_problem(conn, "P")
    assert len(rows) == 1
    r = rows[0]
    assert r["type"] == "lesson"
    assert r["title"] == "t1"
    assert r["body"] == "b1"
    assert r["scope"] == "problem"
    assert r["provenance"] == "reflection"


def test_insert_rejects_bad_enum(conn):
    with pytest.raises(ValueError):
        kb.insert_entry(conn, entry_type="bogus", title="x", problem="P")
    with pytest.raises(ValueError):
        kb.insert_entry(conn, entry_type="lesson", title="x", problem="P",
                        scope="galaxy")


def test_replace_reflection_lessons_resyncs(conn):
    # seed a legacy lesson + an antipattern that must survive a re-sync
    kb.insert_entry(conn, entry_type="lesson", title="legacy-keep",
                    problem="P", provenance="legacy_lessons")
    kb.insert_entry(conn, entry_type="antipattern", title="ap-keep",
                    problem="P", provenance="drafts_blocker")

    kb.replace_reflection_lessons(conn, "P", ["a", "b"])
    titles = {r["title"] for r in kb.entries_for_problem(conn, "P")}
    assert titles == {"legacy-keep", "ap-keep", "a", "b"}

    # correction (b→b') + removal (a) + append (c): full re-sync, not append-only
    kb.replace_reflection_lessons(conn, "P", ["b'", "c"])
    rows = kb.entries_for_problem(conn, "P")
    refl = {r["title"] for r in rows if r["provenance"] == "reflection"}
    assert refl == {"b'", "c"}            # a removed, b corrected, c added
    others = {r["title"] for r in rows if r["provenance"] != "reflection"}
    assert others == {"legacy-keep", "ap-keep"}  # untouched


def test_lesson_bullets_parsing():
    body = (
        "<!-- Lessons learned. -->\n"
        "<!-- LESSONS_BEGIN -->\n"
        "- first lesson\n"
        "  - indented still a bullet\n"
        "\n"
        "not a bullet\n"
        "-->\n"          # stray comment close, not a bullet
        "- second lesson  \n"
    )
    assert kb.lesson_bullets(body) == [
        "first lesson", "indented still a bullet", "second lesson"]


def test_migrate_all_lessons(conn, tmp_path):
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('Q', 'Q/Manifest.md', ?)", (db.now(),))
    conn.commit()
    pdir = db.problem_dir(tmp_path, "P")
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "LESSONS.md").write_text(
        "<!-- LESSONS_BEGIN -->\n- alpha\n- beta\n", encoding="utf-8")
    # Q has no LESSONS.md on disk → skipped.
    n = kb.migrate_all_lessons(conn, tmp_path)
    assert n == 1
    assert {r["title"] for r in kb.entries_for_problem(conn, "P")} == {
        "alpha", "beta"}
    assert kb.entries_for_problem(conn, "Q") == []


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
                          problem="P", node_id=9, scope="node")
    conn.execute("DELETE FROM goals WHERE id = 9")
    conn.commit()
    row = conn.execute(
        "SELECT node_id FROM kb_entries WHERE id = ?", (rid,)).fetchone()
    assert row["node_id"] is None
