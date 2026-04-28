"""Tests for Tooling/library/check_deps.py (P6 C42)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.library.check_deps import (
    CheckDepsResult,
    Violation,
    _trust_set_axioms,
    check_axiom_coverage,
)


_NOW = "2026-01-01T00:00:00+00:00"

_META_TEMPLATE = """\
---
problem_name: {name}
axioms:
{axiom_lines}
---
"""


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


def _write_problem(base: Path, name: str, axioms: list[str]) -> None:
    pdir = base / "Problems" / name
    pdir.mkdir(parents=True)
    axiom_lines = "\n".join(f"  - {a}" for a in axioms)
    (pdir / "META.md").write_text(
        _META_TEMPLATE.format(name=name, axiom_lines=axiom_lines),
        encoding="utf-8",
    )


def _seed_library_entry(
    conn,
    *,
    name: str,
    problem: str,
    slug: str,
    trust_set: list,
) -> int:
    """Insert a goal + library_index row pair. Returns goal id."""
    with conn:
        cur = conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, answer_data, trust_set, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, 'root', 'theorem', 'proved', 'live', ?, ?, ?, ?)",
            (problem, slug, f"Problems/{problem}/{slug}.lean",
             json.dumps({"type": "classical"}),
             json.dumps(trust_set), _NOW, _NOW),
        )
        gid = cur.lastrowid
        conn.execute(
            "INSERT INTO library_index "
            "(layer, name, path, source_root_id, committed_at) "
            "VALUES ('Theorems', ?, ?, ?, ?)",
            (name, f"Library/Theorems/{name}.lean", gid, _NOW),
        )
    return gid


# ---------------------------------------------------------------------------
# _trust_set_axioms helper
# ---------------------------------------------------------------------------


class TestTrustSetAxioms:
    def test_extracts_lean_axiom_names(self):
        ts = json.dumps([
            {"name": "propext", "kind": "lean_axiom"},
            {"name": "Quot.sound", "kind": "lean_axiom"},
        ])
        assert _trust_set_axioms(ts) == frozenset({"propext", "Quot.sound"})

    def test_filters_computational_kind(self):
        """spec line 38 字面: mathematical 層 axiom only — computational
        entries are concrete artifacts, not foundational deps."""
        ts = json.dumps([
            {"name": "propext", "kind": "lean_axiom"},
            {"name": "evaluator_xyz", "kind": "computational"},
        ])
        assert _trust_set_axioms(ts) == frozenset({"propext"})

    def test_none_returns_empty(self):
        assert _trust_set_axioms(None) == frozenset()

    def test_malformed_json_returns_empty(self):
        assert _trust_set_axioms("{not json") == frozenset()

    def test_non_list_returns_empty(self):
        assert _trust_set_axioms(json.dumps({"not": "list"})) == frozenset()


# ---------------------------------------------------------------------------
# check_axiom_coverage integration
# ---------------------------------------------------------------------------


class TestCheckAxiomCoverage:
    def test_all_problems_covered_no_violations(self, db, tmp_path):
        # Two problems, both declare all the axioms the entry needs
        _write_problem(tmp_path, "alpha", ["propext", "Quot.sound"])
        _write_problem(tmp_path, "beta", ["propext", "Quot.sound"])
        _seed_library_entry(
            db, name="alpha.lemma1", problem="alpha", slug="lemma1",
            trust_set=[
                {"name": "propext", "kind": "lean_axiom"},
                {"name": "Quot.sound", "kind": "lean_axiom"},
            ],
        )
        result = check_axiom_coverage(db, tmp_path)
        assert result.violations == []
        assert result.entries_checked == 1
        assert result.n_problems == 2

    def test_violation_on_narrower_consumer(self, db, tmp_path):
        # Problem 'alpha' has Classical.choice; 'beta' does NOT.
        _write_problem(tmp_path, "alpha",
                        ["propext", "Quot.sound", "Classical.choice"])
        _write_problem(tmp_path, "beta", ["propext", "Quot.sound"])
        _seed_library_entry(
            db, name="alpha.classical_lemma",
            problem="alpha", slug="classical_lemma",
            trust_set=[
                {"name": "propext", "kind": "lean_axiom"},
                {"name": "Classical.choice", "kind": "lean_axiom"},
            ],
        )
        result = check_axiom_coverage(db, tmp_path)
        # alpha covers (no violation); beta misses Classical.choice
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.consumer_problem == "beta"
        assert v.entry_name == "alpha.classical_lemma"
        assert v.missing == frozenset({"Classical.choice"})

    def test_skipped_problems_reported(self, db, tmp_path):
        # 'good' parses; 'bad' has no axioms field (skipped)
        _write_problem(tmp_path, "good", ["propext"])
        bad_dir = tmp_path / "Problems" / "bad"
        bad_dir.mkdir(parents=True)
        (bad_dir / "META.md").write_text("---\n---\n", encoding="utf-8")
        result = check_axiom_coverage(db, tmp_path)
        assert result.skipped_problems == ["bad"]
        assert result.n_problems == 1

    def test_no_library_entries_no_violations(self, db, tmp_path):
        _write_problem(tmp_path, "alpha", ["propext"])
        result = check_axiom_coverage(db, tmp_path)
        assert result.entries_checked == 0
        assert result.violations == []

    def test_computational_only_trust_set_no_violation(self, db, tmp_path):
        """Library entry whose trust_set contains only computational
        entries imposes no foundational axiom requirement → no
        violation regardless of consumer Problem axioms."""
        _write_problem(tmp_path, "alpha", ["propext"])
        _write_problem(tmp_path, "beta", [])  # would normally be MetaError
        # use minimal valid axioms for beta to keep parse_meta happy
        # (frozenset with at least one entry)
        (tmp_path / "Problems" / "beta" / "META.md").write_text(
            "---\nproblem_name: beta\naxioms:\n  - propext\n---\n",
            encoding="utf-8",
        )
        _seed_library_entry(
            db, name="alpha.computed", problem="alpha", slug="computed",
            trust_set=[
                {"name": "evaluator_hash_xyz", "kind": "computational"},
            ],
        )
        result = check_axiom_coverage(db, tmp_path)
        assert result.violations == []

    def test_empty_trust_set_no_violation(self, db, tmp_path):
        """Goal with NULL trust_set (e.g. P1 sync path silent fallback)
        contributes no axioms → no coverage requirement."""
        _write_problem(tmp_path, "alpha", ["propext"])
        # Insert without trust_set
        with db:
            cur = db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, origin, kind, status, "
                "commit_state, answer_data, "
                "created_at, updated_at) "
                "VALUES ('alpha', 'lem', 'p.lean', 'root', 'theorem', "
                "'proved', 'live', ?, ?, ?)",
                (json.dumps({"type": "classical"}), _NOW, _NOW),
            )
            gid = cur.lastrowid
            db.execute(
                "INSERT INTO library_index "
                "(layer, name, path, source_root_id, committed_at) "
                "VALUES ('Theorems', 'alpha.lem', 'p.lean', ?, ?)",
                (gid, _NOW),
            )
        result = check_axiom_coverage(db, tmp_path)
        assert result.violations == []
        assert result.entries_checked == 1
