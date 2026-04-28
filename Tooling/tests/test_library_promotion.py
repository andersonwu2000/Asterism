"""Tests for Tooling/library/promotion.py (P6 C41)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.library.promotion import (
    PromotionResult,
    _qualifies_for_library_theorems,
    _qualifies_for_per_problem,
    _re_export_line,
    promote_to_library,
)


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    conn = connect(p)
    init_schema(conn)
    conn.close()
    return p


@pytest.fixture
def db(db_path):
    conn = connect(db_path)
    yield conn
    conn.close()


def _seed_proved_root(
    conn,
    *,
    slug: str = "thm",
    problem: str = "test_problem",
    answer_data: dict | None = None,
    trust_set: list | None = None,
) -> int:
    """Insert a status='proved', origin='root', type='classical' goal."""
    if answer_data is None:
        answer_data = {"type": "classical", "lean_path": f"path/{slug}.lean"}
    if trust_set is None:
        trust_set = [
            {"name": "propext", "kind": "lean_axiom"},
            {"name": "Quot.sound", "kind": "lean_axiom"},
        ]
    with conn:
        cur = conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, answer_data, trust_set, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, 'root', 'theorem', 'proved', 'live', ?, ?, ?, ?)",
            (problem, slug, f"Problems/{problem}/{slug}.lean",
             json.dumps(answer_data), json.dumps(trust_set), _NOW, _NOW),
        )
    return cur.lastrowid


def _seed_proved_other(conn, *, origin: str, slug: str = "g",
                        problem: str = "test_problem") -> int:
    """Insert a proved goal with given non-root origin."""
    with conn:
        cur = conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, answer_data, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'theorem', 'proved', 'live', ?, ?, ?)",
            (problem, slug, f"Problems/{problem}/{slug}.lean", origin,
             json.dumps({"type": "classical", "lean_path": f"path/{slug}.lean"}),
             _NOW, _NOW),
        )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# _re_export_line
# ---------------------------------------------------------------------------


class TestReExportLine:
    def test_format_per_spike_024(self):
        goal = {"id": 42, "problem": "demo", "slug": "add_comm"}
        assert _re_export_line(goal) == (
            "theorem demo.add_comm := Problems.demo.Goals.42_add_comm.add_comm\n"
        )


# ---------------------------------------------------------------------------
# _qualifies_for_library_theorems
# ---------------------------------------------------------------------------


class TestQualifyLibraryTheorems:
    def test_root_classical_with_axioms_qualifies(self):
        goal = {
            "origin": "root",
            "status": "proved",
            "answer_data": json.dumps({"type": "classical"}),
            "trust_set": json.dumps([
                {"name": "propext", "kind": "lean_axiom"},
            ]),
        }
        ok, reason = _qualifies_for_library_theorems(
            goal, ["propext", "Quot.sound", "Classical.choice"],
        )
        assert ok is True
        assert reason is None

    def test_non_root_origin_skipped(self):
        goal = {"origin": "backward", "status": "proved",
                "answer_data": json.dumps({"type": "classical"})}
        ok, reason = _qualifies_for_library_theorems(goal, [])
        assert ok is False
        assert "not 'root'" in reason

    def test_missing_trust_set_skipped(self):
        goal = {"origin": "root", "status": "proved",
                "answer_data": json.dumps({"type": "classical"})}
        ok, reason = _qualifies_for_library_theorems(goal, ["propext"])
        assert ok is False
        assert "trust_set missing" in reason

    def test_axioms_unknown_skipped(self):
        goal = {"origin": "root", "status": "proved",
                "answer_data": json.dumps({"type": "classical"}),
                "trust_set": json.dumps([])}
        ok, reason = _qualifies_for_library_theorems(goal, None)
        assert ok is False
        assert "axioms unknown" in reason

    def test_axiom_outside_whitelist_skipped(self):
        goal = {"origin": "root", "status": "proved",
                "answer_data": json.dumps({"type": "classical"}),
                "trust_set": json.dumps([
                    {"name": "sorryAx", "kind": "lean_axiom"},
                ])}
        ok, reason = _qualifies_for_library_theorems(
            goal, ["propext", "Quot.sound", "Classical.choice"],
        )
        assert ok is False
        assert "rejected by axiom whitelist" in reason
        assert "sorryAx" in reason

    def test_witness_type_skipped(self):
        """type='witness' (silver) doesn't go to Library/Theorems."""
        goal = {"origin": "root", "status": "proved",
                "answer_data": json.dumps({"type": "witness"}),
                "trust_set": json.dumps([])}
        ok, reason = _qualifies_for_library_theorems(goal, ["propext"])
        assert ok is False
        assert "not 'classical'" in reason


# ---------------------------------------------------------------------------
# _qualifies_for_per_problem
# ---------------------------------------------------------------------------


class TestQualifyPerProblem:
    def test_proved_root_qualifies(self):
        ok, _ = _qualifies_for_per_problem(
            {"origin": "root", "status": "proved"},
        )
        assert ok is True

    def test_proved_backward_qualifies(self):
        ok, _ = _qualifies_for_per_problem(
            {"origin": "backward", "status": "proved"},
        )
        assert ok is True

    def test_proved_refuter_negation_qualifies(self):
        ok, _ = _qualifies_for_per_problem(
            {"origin": "refuter_negation", "status": "proved"},
        )
        assert ok is True

    def test_construction_witness_deferred(self):
        """task.md ## 延後 cycles: construction_witness origin not in
        per-Problem proved.lean append set."""
        ok, reason = _qualifies_for_per_problem(
            {"origin": "construction_witness", "status": "proved"},
        )
        assert ok is False
        assert "construction_witness" in reason

    def test_open_status_skipped(self):
        ok, reason = _qualifies_for_per_problem(
            {"origin": "root", "status": "open"},
        )
        assert ok is False
        assert "not 'proved'" in reason


# ---------------------------------------------------------------------------
# promote_to_library — integration
# ---------------------------------------------------------------------------


class TestPromoteToLibrary:
    def test_root_classical_appends_both_files(self, db, tmp_path):
        gid = _seed_proved_root(db, slug="add_comm")
        # Create META.md so axioms whitelist is consulted
        meta = tmp_path / "Problems" / "test_problem" / "META.md"
        meta.parent.mkdir(parents=True)
        meta.write_text(
            "---\n"
            "problem_name: test_problem\n"
            "axioms:\n  - propext\n  - Quot.sound\n"
            "---\n",
            encoding="utf-8",
        )
        import os
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = promote_to_library(db, gid, tmp_path)
        finally:
            os.chdir(cwd)
        assert result.per_problem_appended is True
        assert result.library_theorems_appended is True
        assert result.library_index_inserted is True
        # Both files have the line
        pp = (tmp_path / "Problems" / "test_problem" / "proved.lean")
        lt = (tmp_path / "Library" / "Theorems" / "proved.lean")
        assert pp.exists()
        assert lt.exists()
        assert "test_problem.add_comm" in pp.read_text()
        assert "test_problem.add_comm" in lt.read_text()
        # library_index row
        rows = db.execute(
            "SELECT layer, name, source_root_id FROM library_index"
        ).fetchall()
        assert rows == [("Theorems", "test_problem.add_comm", gid)]

    def test_backward_origin_only_per_problem(self, db, tmp_path):
        """Non-root origin (backward) appends only to per-Problem
        proved.lean, NOT Library/Theorems/proved.lean."""
        gid = _seed_proved_other(db, origin="backward", slug="sub_lemma")
        result = promote_to_library(db, gid, tmp_path)
        assert result.per_problem_appended is True
        assert result.library_theorems_appended is False
        assert result.library_index_inserted is False
        pp = tmp_path / "Problems" / "test_problem" / "proved.lean"
        lt = tmp_path / "Library" / "Theorems" / "proved.lean"
        assert pp.exists()
        assert not lt.exists()

    def test_construction_witness_skipped(self, db, tmp_path):
        """task.md ## 延後 cycles: construction_witness origin defer."""
        gid = _seed_proved_other(
            db, origin="construction_witness", slug="cw_g",
        )
        result = promote_to_library(db, gid, tmp_path)
        assert result.per_problem_appended is False
        assert result.library_theorems_appended is False
        assert result.skipped_reason is not None
        assert "construction_witness" in result.skipped_reason

    def test_unproved_goal_skipped(self, db, tmp_path):
        with db:
            cur = db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, origin, kind, status, "
                "commit_state, created_at, updated_at) "
                "VALUES ('p', 'g_open', 'p.lean', 'root', 'theorem', "
                "'open', 'live', ?, ?)",
                (_NOW, _NOW),
            )
        gid = cur.lastrowid
        result = promote_to_library(db, gid, tmp_path)
        assert result.skipped_reason is not None
        assert "not 'proved'" in result.skipped_reason

    def test_unknown_goal_id(self, db, tmp_path):
        result = promote_to_library(db, 99999, tmp_path)
        assert "not found" in result.skipped_reason

    def test_lake_verify_failure_reverts(self, db, tmp_path):
        """If lake_verify returns False, all writes are reverted."""
        gid = _seed_proved_root(db, slug="bad_lemma")
        # Provide a META.md so library_theorems path triggers
        meta = tmp_path / "Problems" / "test_problem" / "META.md"
        meta.parent.mkdir(parents=True)
        meta.write_text(
            "---\n"
            "problem_name: test_problem\n"
            "axioms:\n  - propext\n  - Quot.sound\n"
            "---\n",
            encoding="utf-8",
        )
        import os
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = promote_to_library(
                db, gid, tmp_path,
                lake_verify=lambda _path: False,
            )
        finally:
            os.chdir(cwd)
        assert result.reverted is True
        assert result.per_problem_appended is False
        assert result.library_theorems_appended is False
        assert result.library_index_inserted is False
        pp = tmp_path / "Problems" / "test_problem" / "proved.lean"
        lt = tmp_path / "Library" / "Theorems" / "proved.lean"
        # Files exist (we appended) but content was truncated back
        if pp.exists():
            assert "bad_lemma" not in pp.read_text()
        if lt.exists():
            assert "bad_lemma" not in lt.read_text()
        # library_index row also removed
        rows = db.execute(
            "SELECT count(*) FROM library_index "
            "WHERE name = 'test_problem.bad_lemma'"
        ).fetchone()
        assert rows[0] == 0

    def test_emit_event_on_revert(self, db, tmp_path):
        gid = _seed_proved_root(db, slug="rev_lemma")
        meta = tmp_path / "Problems" / "test_problem" / "META.md"
        meta.parent.mkdir(parents=True)
        meta.write_text(
            "---\n"
            "problem_name: test_problem\n"
            "axioms:\n  - propext\n  - Quot.sound\n"
            "---\n",
            encoding="utf-8",
        )
        captured: list[tuple[str, dict]] = []

        def fake_emit(kind, payload):
            captured.append((kind, payload))

        import os
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            promote_to_library(
                db, gid, tmp_path,
                lake_verify=lambda _p: False,
                emit_event=fake_emit,
            )
        finally:
            os.chdir(cwd)
        rules = [p.get("rule") for _, p in captured]
        assert "library_promotion_reverted" in rules

    def test_library_promotion_invalidates_library_cache(self, db, tmp_path):
        """C43 R1: Library write triggers cache invalidation per impl
        §2.3 字面."""
        # Pre-seed search_cache with a library scope row
        with db:
            db.execute(
                "INSERT INTO search_cache (query_hash, scope, mode, "
                "results, expires_at) "
                "VALUES ('q_lib', 'mathlib_library', 'find_lemmas', "
                "'[]', '2099-01-01')"
            )
            db.execute(
                "INSERT INTO search_cache (query_hash, scope, mode, "
                "results, expires_at) "
                "VALUES ('q_local', 'local_goals', 'find_subgoals', "
                "'[]', '2099-01-01')"
            )
        gid = _seed_proved_root(db, slug="cache_inv_thm")
        meta = tmp_path / "Problems" / "test_problem" / "META.md"
        meta.parent.mkdir(parents=True)
        meta.write_text(
            "---\n"
            "problem_name: test_problem\n"
            "axioms:\n  - propext\n  - Quot.sound\n"
            "---\n",
            encoding="utf-8",
        )
        import os
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            promote_to_library(db, gid, tmp_path)
        finally:
            os.chdir(cwd)
        # library scope row deleted by invalidate_for_library_write
        rows = db.execute(
            "SELECT query_hash FROM search_cache "
            "WHERE scope LIKE '%library%'"
        ).fetchall()
        assert rows == []
        # local_goals scope row untouched (different invalidation hook)
        rows = db.execute(
            "SELECT query_hash FROM search_cache "
            "WHERE scope = 'local_goals'"
        ).fetchall()
        assert len(rows) == 1

    def test_library_index_first_write_wins(self, db, tmp_path):
        """If library_index already has (Theorems, <name>), don't
        overwrite — emit a cascade event for visibility."""
        meta = tmp_path / "Problems" / "test_problem" / "META.md"
        meta.parent.mkdir(parents=True)
        meta.write_text(
            "---\n"
            "problem_name: test_problem\n"
            "axioms:\n  - propext\n  - Quot.sound\n"
            "---\n",
            encoding="utf-8",
        )
        # Insert two goals; pre-seed library_index pointing at the first
        # so the second triggers first-write-wins on the same name.
        incumbent_gid = _seed_proved_root(db, slug="dup_lemma_incumbent")
        with db:
            db.execute(
                "INSERT INTO library_index "
                "(layer, name, path, source_root_id, committed_at) "
                "VALUES ('Theorems', 'test_problem.dup_lemma', 'old/path.lean', "
                "?, ?)",
                (incumbent_gid, _NOW),
            )
        gid = _seed_proved_root(db, slug="dup_lemma")
        captured: list = []
        import os
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = promote_to_library(
                db, gid, tmp_path,
                emit_event=lambda k, p: captured.append((k, p)),
            )
        finally:
            os.chdir(cwd)
        # File appended (idempotent re-export-line = harmless extra)
        # but library_index NOT re-INSERTed
        assert result.library_theorems_appended is True
        assert result.library_index_inserted is False
        rules = [p.get("rule") for _, p in captured]
        assert "library_index_first_write_wins" in rules
        # Original row still points at the incumbent goal id
        existing = db.execute(
            "SELECT source_root_id FROM library_index "
            "WHERE name = 'test_problem.dup_lemma'"
        ).fetchone()
        assert existing[0] == incumbent_gid
