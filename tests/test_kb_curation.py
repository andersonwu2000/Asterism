"""Routine-wake KB curation (2026-07-13, user call; moved from the
retired audit wake 2026-07-25): delete/merge of GLOBAL lessons via
the `kb_curation.json` sidecar.

Design pins: the sidecar is NOT a decision kind — curation is
belief-store maintenance and must never satisfy the stall-advance
delta gate; the apply is routine-runner-only and strictly
all-or-nothing on any invalid op."""
import json
import sqlite3

import pytest

from Tooling.state import db, kb
from Tooling.pipeline.strategist import _apply_kb_curation


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at) VALUES (?,?)",
        ("P", db.now()),
    )
    c.commit()
    return c


def _lesson(conn, title, *, problem="P", node_id=None, typ="lesson"):
    return kb.insert_entry(conn, entry_type=typ, title=title, body=f"body {title}",
                           problem=problem, node_id=node_id,
                           provenance=f"t:{title}")


def _titles(conn, problem="P"):
    return [r["title"] for r in kb.global_lessons(conn, problem)]


# ---------- kb primitives ----------

def test_delete_scoping_wall(conn):
    gid = _lesson(conn, "keepable")
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES (?,?)",
        ("Q", db.now()))
    other = _lesson(conn, "other-problem", problem="Q")
    # goals row for a node-bound entry
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement, kind,"
        " origin, status, depth, created_at, updated_at) VALUES "
        "('P','g','p','s','theorem','root','open',0,?,?)",
        (db.now(), db.now()))
    node_gid = conn.execute("SELECT id FROM goals").fetchone()["id"]
    node = _lesson(conn, "node-bound", node_id=node_gid, typ="antipattern")
    # wrong problem / node-bound / antipattern all unreachable
    assert kb.delete_global_lesson(conn, entry_id=other, problem="P") is None
    assert kb.delete_global_lesson(conn, entry_id=node, problem="P") is None
    snap = kb.delete_global_lesson(conn, entry_id=gid, problem="P")
    assert snap["title"] == "keepable"
    assert _titles(conn) == []
    # other rows untouched
    assert kb.entries_for_problem(conn, "Q")[0]["id"] == other


def test_merge_atomic_and_scoped(conn):
    a = _lesson(conn, "a")
    b = _lesson(conn, "b")
    c_ = _lesson(conn, "c")
    # bad absorb id → nothing changes
    assert kb.merge_global_lessons(
        conn, keep_id=a, absorb_ids=[b, 99999], problem="P",
        title="X", body="Y") is None
    assert set(_titles(conn)) == {"a", "b", "c"}
    snaps = kb.merge_global_lessons(
        conn, keep_id=a, absorb_ids=[b, c_], problem="P",
        title="merged", body="all three")
    assert {r["title"] for r in snaps} == {"a", "b", "c"}
    rows = kb.global_lessons(conn, "P")
    assert len(rows) == 1
    assert rows[0]["id"] == a and rows[0]["title"] == "merged"
    assert rows[0]["body"] == "all three"


# ---------- sidecar apply ----------

def _write(tmp_path, ops):
    (tmp_path / "kb_curation.json").write_text(
        json.dumps(ops), encoding="utf-8")


def test_sidecar_applies_delete_and_merge(conn, tmp_path, capsys):
    a = _lesson(conn, "broken half-sentence")
    b = _lesson(conn, "dead arc recipe 1")
    c_ = _lesson(conn, "dead arc recipe 2")
    keep = _lesson(conn, "live recipe")
    _write(tmp_path, [
        {"op": "delete", "id": a, "reason": "truncated narrative, no action"},
        {"op": "merge", "keep_id": b, "absorb_ids": [c_],
         "title": "dead quotient arc recipes (superseded)",
         "body": "tombstone", "reason": "arc superseded per TREE"},
    ])
    _apply_kb_curation(conn, problem="P", attempts_dir=tmp_path)
    got = _titles(conn)
    assert "broken half-sentence" not in got
    assert "dead arc recipe 2" not in got
    assert "dead quotient arc recipes (superseded)" in got
    assert "live recipe" in got
    out = capsys.readouterr().out
    assert "[kb-curation]" in out and "snapshot=" in out


def test_sidecar_all_or_nothing(conn, tmp_path, capsys):
    a = _lesson(conn, "a")
    b = _lesson(conn, "b")
    _write(tmp_path, [
        {"op": "delete", "id": a, "reason": "fine"},
        {"op": "delete", "id": 424242, "reason": "bad id"},
    ])
    _apply_kb_curation(conn, problem="P", attempts_dir=tmp_path)
    assert set(_titles(conn)) == {"a", "b"}          # nothing applied
    assert "rejected, nothing applied" in capsys.readouterr().out


def test_sidecar_rejects_missing_reason_dup_ids_and_cap(conn, tmp_path, capsys):
    ids = [_lesson(conn, f"l{i}") for i in range(12)]
    # missing reason
    _write(tmp_path, [{"op": "delete", "id": ids[0]}])
    _apply_kb_curation(conn, problem="P", attempts_dir=tmp_path)
    assert len(_titles(conn)) == 12
    # duplicate id across ops
    _write(tmp_path, [
        {"op": "delete", "id": ids[0], "reason": "r"},
        {"op": "merge", "keep_id": ids[1], "absorb_ids": [ids[0]],
         "title": "t", "reason": "r"},
    ])
    _apply_kb_curation(conn, problem="P", attempts_dir=tmp_path)
    assert len(_titles(conn)) == 12
    # over the op cap
    _write(tmp_path, [{"op": "delete", "id": i, "reason": "r"}
                      for i in ids[:11]])
    _apply_kb_curation(conn, problem="P", attempts_dir=tmp_path)
    assert len(_titles(conn)) == 12
    assert capsys.readouterr().out.count("rejected, nothing applied") == 3


def test_sidecar_absent_is_silent_noop(conn, tmp_path, capsys):
    _lesson(conn, "a")
    _apply_kb_curation(conn, problem="P", attempts_dir=tmp_path)
    assert _titles(conn) == ["a"]
    assert "[kb-curation]" not in capsys.readouterr().out


# ---------- routine context surface ----------

def test_routine_context_gets_curation_surface(conn, tmp_path):
    """The lesson index + LESSONS.md companion appear on routine wakes
    ONLY — the curation power is structurally routine-only, so no other
    trigger should even advertise the surface."""
    from Tooling.agent.phase2_context import _section_kb_lessons_curation
    a = _lesson(conn, "some recipe")
    lines = _section_kb_lessons_curation(conn, "P", tmp_path)
    text = "\n".join(lines)
    assert "curation surface" in text and f"[id-{a}]" in text
    companion = (tmp_path / "LESSONS.md").read_text(encoding="utf-8")
    assert "body some recipe" in companion
    # empty KB → no section at all
    kb.delete_global_lesson(conn, entry_id=a, problem="P")
    assert _section_kb_lessons_curation(conn, "P", tmp_path) == []
    # wiring pin: compile gates the section on the routine trigger, and
    # the runner applies the sidecar from both commit branches
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    ctx_src = (root / "Tooling" / "agent" / "phase2_context.py").read_text(
        encoding="utf-8")
    assert 'if trigger_kind == "routine":' in ctx_src
    strat_src = (root / "Tooling" / "pipeline" / "strategist.py").read_text(
        encoding="utf-8")
    assert strat_src.count("_apply_kb_curation(conn, problem=problem,") == 2
