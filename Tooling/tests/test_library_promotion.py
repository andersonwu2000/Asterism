"""Tests for Tooling/library/promotion.py (P6 C41 + R3 audit fixes)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.library.promotion import (
    LIBRARY_WHITELIST,
    PromotionResult,
    _has_numeric_prefix,
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


@pytest.fixture(autouse=True)
def _set_noop_verifier(monkeypatch):
    """Tests don't have a real lake env; opt into the noop verifier
    via the documented LIBRARY_VERIFY_NOOP=1 path. Production code
    uses an explicit lake_verify or this same env hook (set by the
    scheduler hook in C41-C44; C45 ships the real verifier)."""
    monkeypatch.setenv("LIBRARY_VERIFY_NOOP", "1")


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
        # Default: axioms within LIBRARY_WHITELIST so qualifies passes.
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
# _qualifies_for_library_theorems (uses LIBRARY_WHITELIST, NOT Problem.axioms)
# ---------------------------------------------------------------------------


class TestQualifyLibraryTheorems:
    def test_root_classical_with_whitelist_axioms_qualifies(self):
        """C41 R3 HIGH-1: Library.whitelist is framework-global; trust_set
        within {propext, Quot.sound, Classical.choice} qualifies."""
        goal = {
            "origin": "root",
            "status": "proved",
            "answer_data": json.dumps({"type": "classical"}),
            "trust_set": json.dumps([
                {"name": "propext", "kind": "lean_axiom"},
                {"name": "Quot.sound", "kind": "lean_axiom"},
            ]),
        }
        ok, reason = _qualifies_for_library_theorems(goal)
        assert ok is True
        assert reason is None

    def test_non_root_origin_skipped(self):
        goal = {"origin": "backward", "status": "proved",
                "answer_data": json.dumps({"type": "classical"})}
        ok, reason = _qualifies_for_library_theorems(goal)
        assert ok is False
        assert "not 'root'" in reason

    def test_missing_trust_set_skipped(self):
        goal = {"origin": "root", "status": "proved",
                "answer_data": json.dumps({"type": "classical"})}
        ok, reason = _qualifies_for_library_theorems(goal)
        assert ok is False
        assert "trust_set missing" in reason

    def test_axiom_outside_whitelist_skipped(self):
        """C41 R3 HIGH-1 + acceptance #9 (RH-dependent exclusion):
        an axiom not in LIBRARY_WHITELIST → trust_set rejected."""
        goal = {"origin": "root", "status": "proved",
                "answer_data": json.dumps({"type": "classical"}),
                "trust_set": json.dumps([
                    {"name": "riemann_hypothesis", "kind": "lean_axiom"},
                ])}
        ok, reason = _qualifies_for_library_theorems(goal)
        assert ok is False
        assert "Library.whitelist" in reason
        assert "riemann_hypothesis" in reason

    def test_witness_type_skipped(self):
        """type='witness' (silver) doesn't go to Library/Theorems."""
        goal = {"origin": "root", "status": "proved",
                "answer_data": json.dumps({"type": "witness"}),
                "trust_set": json.dumps([])}
        ok, reason = _qualifies_for_library_theorems(goal)
        assert ok is False
        assert "not 'classical'" in reason

    def test_library_whitelist_constant_value(self):
        """C41 R3 HIGH-1 pin: LIBRARY_WHITELIST is the canonical 3-axiom
        set per architecture_impl.md:287 + phase6_library.md:230."""
        assert LIBRARY_WHITELIST == frozenset({
            "propext", "Quot.sound", "Classical.choice",
        })


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
# _has_numeric_prefix (C41 R3 MED-4)
# ---------------------------------------------------------------------------


class TestNumericPrefixDetection:
    def test_numeric_id_detected(self):
        assert _has_numeric_prefix({"id": 42}) is True
        assert _has_numeric_prefix({"id": "7"}) is True

    def test_alpha_id_not_detected(self):
        # Future-proof: if some future id format starts with letter.
        assert _has_numeric_prefix({"id": "g42"}) is False

    def test_missing_id_not_detected(self):
        assert _has_numeric_prefix({}) is False


# ---------------------------------------------------------------------------
# promote_to_library — integration
# ---------------------------------------------------------------------------


class TestPromoteToLibrary:
    def test_root_classical_appends_both_files(self, db, tmp_path):
        gid = _seed_proved_root(db, slug="add_comm")
        result = promote_to_library(db, gid, tmp_path)
        assert result.per_problem_appended is True
        assert result.library_theorems_appended is True
        assert result.library_index_inserted is True
        pp = (tmp_path / "Problems" / "test_problem" / "proved.lean")
        lt = (tmp_path / "Library" / "Theorems" / "proved.lean")
        assert "test_problem.add_comm" in pp.read_text()
        assert "test_problem.add_comm" in lt.read_text()
        rows = db.execute(
            "SELECT layer, name, source_root_id FROM library_index"
        ).fetchall()
        assert rows == [("Theorems", "test_problem.add_comm", gid)]

    def test_backward_origin_only_per_problem(self, db, tmp_path):
        gid = _seed_proved_other(db, origin="backward", slug="sub_lemma")
        result = promote_to_library(db, gid, tmp_path)
        assert result.per_problem_appended is True
        assert result.library_theorems_appended is False
        assert result.library_index_inserted is False

    def test_construction_witness_skipped(self, db, tmp_path):
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

    def test_rh_dependent_excluded_from_library_theorems(self, db, tmp_path):
        """C41 R3 HIGH-1 + acceptance #9: a proved goal whose trust_set
        contains an axiom outside LIBRARY_WHITELIST (e.g.
        riemann_hypothesis) does NOT make it into
        Library/Theorems/proved.lean — but DOES land in the per-Problem
        proved.lean (origin='root' still qualifies for per-Problem)."""
        gid = _seed_proved_root(
            db, slug="rh_consequence", problem="A_rh",
            trust_set=[
                {"name": "propext", "kind": "lean_axiom"},
                {"name": "riemann_hypothesis", "kind": "lean_axiom"},
            ],
        )
        result = promote_to_library(db, gid, tmp_path)
        # per-Problem path qualifies (origin=root, status=proved)
        assert result.per_problem_appended is True
        # Library/Theorems path rejected by Library.whitelist
        assert result.library_theorems_appended is False
        assert result.library_index_inserted is False
        pp = tmp_path / "Problems" / "A_rh" / "proved.lean"
        lt = tmp_path / "Library" / "Theorems" / "proved.lean"
        assert pp.exists()
        assert "A_rh.rh_consequence" in pp.read_text()
        assert not lt.exists()  # never written

    def test_promote_with_base_dir_not_cwd(self, db, tmp_path):
        """C41 R3 MED-2: the production scheduler hook passes base_dir
        explicitly; promotion logic must NOT rely on os.getcwd matching
        base_dir. cwd is left at default; base_dir resolves Library /
        Problems paths."""
        original_cwd = os.getcwd()
        # Run from a directory that's NOT the workspace root.
        try:
            other = tmp_path.parent
            os.chdir(str(other))
            gid = _seed_proved_root(db, slug="cwd_proof")
            result = promote_to_library(db, gid, tmp_path)
        finally:
            os.chdir(original_cwd)
        assert result.per_problem_appended is True
        assert result.library_theorems_appended is True
        # Verify files landed under base_dir, not cwd
        pp = tmp_path / "Problems" / "test_problem" / "proved.lean"
        assert pp.exists()

    def test_lake_verify_failure_reverts(self, db, tmp_path):
        """Explicit lake_verify=False reverts both files + library_index
        DELETE, emits library_promotion_partial_revert event."""
        gid = _seed_proved_root(db, slug="bad_lemma")
        captured: list = []
        result = promote_to_library(
            db, gid, tmp_path,
            lake_verify=lambda _path: False,
            emit_event=lambda k, p: captured.append((k, p)),
        )
        assert result.reverted is True
        assert result.per_problem_appended is False
        assert result.library_theorems_appended is False
        assert result.library_index_inserted is False
        rules = [p.get("rule") for _, p in captured]
        assert "library_promotion_partial_revert" in rules
        rows = db.execute(
            "SELECT count(*) FROM library_index "
            "WHERE name = 'test_problem.bad_lemma'"
        ).fetchone()
        assert rows[0] == 0

    def test_library_index_first_write_wins_no_file_append(self, db, tmp_path):
        """C41 R3 HIGH-3: when library_index has a (Theorems, name)
        collision, NO file append happens (impl §3.1 step 3 字面). The
        existence check moves BEFORE _append_line. Per-Problem proved.lean
        is unaffected (different scope)."""
        # Pre-seed library_index with the name + an incumbent goal
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
        result = promote_to_library(
            db, gid, tmp_path,
            emit_event=lambda k, p: captured.append((k, p)),
        )
        # File did NOT get appended (spec literal)
        assert result.library_theorems_appended is False
        assert result.library_index_inserted is False
        # Per-Problem still appended (different scope)
        assert result.per_problem_appended is True
        # Event emitted for audit trail
        rules = [p.get("rule") for _, p in captured]
        assert "library_index_first_write_wins" in rules
        # Library/Theorems/proved.lean does NOT contain the new entry
        lt = tmp_path / "Library" / "Theorems" / "proved.lean"
        if lt.exists():
            assert "dup_lemma" not in lt.read_text() or \
                "dup_lemma_incumbent" in lt.read_text()
        # Original library_index row preserved
        existing = db.execute(
            "SELECT source_root_id FROM library_index "
            "WHERE name = 'test_problem.dup_lemma'"
        ).fetchone()
        assert existing[0] == incumbent_gid

    def test_numeric_prefix_warning_emitted(self, db, tmp_path):
        """C41 R3 MED-4: bare-numeric goal id triggers
        library_promotion_warning event (spike-024 D-24-1 #6)."""
        gid = _seed_proved_root(db, slug="num_lemma")
        # All AUTOINCREMENT ids are numeric; verify warning fires.
        captured: list = []
        promote_to_library(
            db, gid, tmp_path,
            emit_event=lambda k, p: captured.append((k, p)),
        )
        rules = [p.get("rule") for _, p in captured]
        assert "library_promotion_warning" in rules
        # Reason text mentions numeric-prefix details
        warn = next(p for _, p in captured
                    if p.get("rule") == "library_promotion_warning")
        assert str(gid) in warn["reason"]
        assert "spike-024 D-24-1 #6" in warn["reason"]

    def test_library_promotion_invalidates_library_cache(self, db, tmp_path):
        """C43 cache invalidation hook still works under R3 changes."""
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
        promote_to_library(db, gid, tmp_path)
        rows = db.execute(
            "SELECT query_hash FROM search_cache "
            "WHERE scope LIKE '%library%'"
        ).fetchall()
        assert rows == []
        rows = db.execute(
            "SELECT query_hash FROM search_cache "
            "WHERE scope = 'local_goals'"
        ).fetchall()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# C41 R3 HIGH-2: lake_verify default safety
# ---------------------------------------------------------------------------


class TestLakeVerifyDefault:
    def test_no_env_no_callable_raises(
        self, db, tmp_path, monkeypatch,
    ):
        """C41 R3 HIGH-2: default lake_verify=None + no
        LIBRARY_VERIFY_NOOP env → NotImplementedError so production
        callers can't silently bypass the verifier."""
        monkeypatch.delenv("LIBRARY_VERIFY_NOOP", raising=False)
        gid = _seed_proved_root(db, slug="strict_verify")
        with pytest.raises(NotImplementedError, match="LIBRARY_VERIFY_NOOP"):
            promote_to_library(db, gid, tmp_path)

    def test_explicit_callable_overrides_env(self, db, tmp_path, monkeypatch):
        """Explicit lake_verify always wins over LIBRARY_VERIFY_NOOP env."""
        monkeypatch.setenv("LIBRARY_VERIFY_NOOP", "1")
        gid = _seed_proved_root(db, slug="explicit_verify")
        called = []
        promote_to_library(
            db, gid, tmp_path,
            lake_verify=lambda p: called.append(p) or True,
        )
        assert len(called) == 1

    def test_noop_env_emits_audit_event(self, db, tmp_path):
        """C41 R3 HIGH-2: when LIBRARY_VERIFY_NOOP=1 path activates,
        emit library_verify_skipped for audit-trail visibility."""
        gid = _seed_proved_root(db, slug="noop_audit")
        captured: list = []
        promote_to_library(
            db, gid, tmp_path,
            emit_event=lambda k, p: captured.append((k, p)),
        )
        rules = [p.get("rule") for _, p in captured]
        assert "library_verify_skipped" in rules
