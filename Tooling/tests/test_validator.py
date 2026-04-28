"""Unit tests for Tooling/stages/validator.py (C11).

Hypothesis carry:  mock subprocess + JSON  (no real Lean needed)
Slug uniqueness:   in-memory SQLite
max_subgoals:      pure Python
extract_theorem_type: pure Python
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.db.connect import init_schema
from Tooling.stages.validator import (
    MAX_SUBGOALS,
    ValidatorError,
    check_hyp_carry,
    check_max_subgoals,
    check_slug_unique,
    extract_theorem_type,
    validate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    init_schema(conn)
    return conn


def _insert_goal(conn: sqlite3.Connection, problem: str, slug: str) -> None:
    conn.execute(
        """INSERT INTO goals
           (problem, slug, lean_path, origin, kind, status, commit_state, created_at, updated_at)
           VALUES (?, ?, ?, 'root', 'theorem', 'open', 'pending', '2026-01-01', '2026-01-01')""",
        (problem, slug, f"Problems/{problem}/{slug}.lean"),
    )
    conn.commit()


def _mock_run(stdout: str) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = 0
    return m


# ---------------------------------------------------------------------------
# extract_theorem_type
# ---------------------------------------------------------------------------

class TestExtractTheoremType:
    def test_explicit_params(self):
        content = "theorem foo (n m : Nat) (h : n < m) : n + m = m + n := by sorry"
        assert extract_theorem_type(content) == "∀ (n m : Nat) (h : n < m), n + m = m + n"

    def test_no_explicit_params(self):
        content = "theorem foo : ∀ (n m : Nat), n + m = m + n := by sorry"
        assert extract_theorem_type(content) == "∀ (n m : Nat), n + m = m + n"

    def test_with_import_prefix(self):
        content = (
            "import Problems.sg.Defs\n"
            "theorem add_zero (n : Nat) : n + 0 = n := Nat.add_zero n\n"
        )
        assert extract_theorem_type(content) == "∀ (n : Nat), n + 0 = n"

    def test_inline_comment_stripped(self):
        content = "theorem foo (n : Nat) : n = n -- trivial\n  := rfl"
        result = extract_theorem_type(content)
        assert "n = n" in result

    def test_no_theorem_raises(self):
        with pytest.raises(ValueError, match="theorem"):
            extract_theorem_type("-- no theorem here\ndef foo := 1\n")

    def test_single_binder(self):
        content = "theorem single (n : Nat) : n + 0 = n := by simp"
        assert extract_theorem_type(content) == "∀ (n : Nat), n + 0 = n"


# ---------------------------------------------------------------------------
# check_max_subgoals
# ---------------------------------------------------------------------------

class TestMaxSubgoals:
    def _sgs(self, n: int) -> list:
        return [{"id": f"G{i}", "slug": f"s{i}", "lean_path": f"/tmp/g{i}.lean"}
                for i in range(n)]

    def test_exactly_max_is_ok(self):
        assert check_max_subgoals(self._sgs(MAX_SUBGOALS)) is None

    def test_one_over_max_rejects(self):
        err = check_max_subgoals(self._sgs(MAX_SUBGOALS + 1))
        assert err is not None
        assert err.check == "max_subgoals"
        assert str(MAX_SUBGOALS + 1) in err.detail

    def test_zero_subgoals_ok(self):
        assert check_max_subgoals([]) is None

    def test_one_subgoal_ok(self):
        assert check_max_subgoals(self._sgs(1)) is None


# ---------------------------------------------------------------------------
# check_slug_unique
# ---------------------------------------------------------------------------

class TestSlugUnique:
    def test_no_collision(self):
        conn = _make_db()
        _insert_goal(conn, "sg", "existing_slug")
        sgs = [{"slug": "new_slug"}]
        assert check_slug_unique(conn, "sg", sgs) is None

    def test_collision_detected(self):
        conn = _make_db()
        _insert_goal(conn, "sg", "taken")
        sgs = [{"slug": "taken"}]
        err = check_slug_unique(conn, "sg", sgs)
        assert err is not None
        assert err.check == "slug_unique"
        assert "taken" in err.detail

    def test_collision_different_problem_is_ok(self):
        conn = _make_db()
        _insert_goal(conn, "problem_a", "slug1")
        sgs = [{"slug": "slug1"}]
        assert check_slug_unique(conn, "problem_b", sgs) is None

    def test_first_collision_stops(self):
        conn = _make_db()
        _insert_goal(conn, "sg", "s1")
        sgs = [{"slug": "s1"}, {"slug": "s2"}]
        err = check_slug_unique(conn, "sg", sgs)
        assert err is not None
        assert "s1" in err.detail


# ---------------------------------------------------------------------------
# check_hyp_carry
# ---------------------------------------------------------------------------

PASS_JSON = json.dumps([
    {"subgoal": "G001", "missing_binders": [], "type_mismatches": []}
])

MISSING_JSON = json.dumps([
    {"subgoal": "G002", "missing_binders": ["h"], "type_mismatches": []}
])

MULTI_JSON = json.dumps([
    {"subgoal": "G001", "missing_binders": [],    "type_mismatches": []},
    {"subgoal": "G002", "missing_binders": ["h"], "type_mismatches": []},
])

PARENT_CONTENT = "theorem parent (n m : Nat) (h : n < m) : n ≤ m := Nat.le_of_lt h\n"
SUB_OK_CONTENT = "theorem sub_ok (n m : Nat) (h : n < m) : n + 0 = n := Nat.add_zero n\n"
SUB_BAD_CONTENT = "theorem sub_bad (n m : Nat) : n + 0 = n := Nat.add_zero n\n"


class TestHypCarry:
    """All tests mock subprocess.run + Path.read_text to avoid real Lean / filesystem."""

    def _call(self, subgoal_contents: list[str], stdout: str) -> list[ValidatorError]:
        subgoals = [
            {"id": f"G{i+1:03d}", "lean_path": f"/tmp/sub{i}.lean"}
            for i in range(len(subgoal_contents))
        ]

        file_map = {"/tmp/parent.lean": PARENT_CONTENT}
        for i, c in enumerate(subgoal_contents):
            file_map[f"/tmp/sub{i}.lean"] = c

        def _read(path, encoding="utf-8"):
            # Normalize to POSIX slashes for cross-platform key lookup.
            return file_map[Path(path).as_posix()]

        with (
            patch("Tooling.stages.validator.subprocess.run",
                  return_value=_mock_run(stdout)),
            patch("Tooling.stages.validator.Path.read_text", _read),
        ):
            return check_hyp_carry(
                parent_lean_path="/tmp/parent.lean",
                subgoals=subgoals,
                lake_cwd="/tmp/lake",
            )

    def test_pass_returns_no_errors(self):
        errs = self._call([SUB_OK_CONTENT], PASS_JSON)
        assert errs == []

    def test_missing_binder_returns_error(self):
        errs = self._call([SUB_BAD_CONTENT], MISSING_JSON)
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "G002" in errs[0].detail
        assert "h" in errs[0].detail

    def test_multi_subgoals_partial_fail(self):
        errs = self._call([SUB_OK_CONTENT, SUB_BAD_CONTENT], MULTI_JSON)
        assert len(errs) == 1
        assert "G002" in errs[0].detail

    def test_empty_subgoals_list(self):
        errs = self._call([], "[]")
        assert errs == []

    def test_lean_output_noise_before_json(self):
        """Python parser skips non-JSON lines before the JSON array."""
        noisy = (
            "D:/tools/validator.lean:10:0: warning: unused variable `x`\n"
            + PASS_JSON
        )
        errs = self._call([SUB_OK_CONTENT], noisy)
        assert errs == []

    def test_timeout_returns_error(self):
        import subprocess as sp

        subgoals = [{"id": "G001", "lean_path": "/tmp/sub0.lean"}]

        def _read(path, encoding="utf-8"):
            return PARENT_CONTENT if "parent" in Path(path).as_posix() else SUB_OK_CONTENT

        with (
            patch("Tooling.stages.validator.subprocess.run",
                  side_effect=sp.TimeoutExpired(cmd="lake", timeout=30)),
            patch("Tooling.stages.validator.Path.read_text", _read),
        ):
            errs = check_hyp_carry(
                parent_lean_path="/tmp/parent.lean",
                subgoals=subgoals,
                lake_cwd="/tmp/lake",
            )
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "timed out" in errs[0].detail


# ---------------------------------------------------------------------------
# validate() facade
# ---------------------------------------------------------------------------

class TestValidateFacade:
    def _subgoals(self, slugs: list[str]) -> list[dict]:
        return [
            {"id": f"G{i+1:03d}", "slug": s, "lean_path": f"/tmp/sub{i}.lean"}
            for i, s in enumerate(slugs)
        ]

    def test_max_subgoals_hard_stop(self):
        conn = _make_db()
        sgs = self._subgoals([f"s{i}" for i in range(MAX_SUBGOALS + 1)])
        errs = validate(conn, "sg", "/tmp/parent.lean", sgs, "/tmp/lake")
        assert len(errs) == 1
        assert errs[0].check == "max_subgoals"

    def test_slug_collision_reported(self):
        conn = _make_db()
        _insert_goal(conn, "sg", "taken")
        sgs = self._subgoals(["taken"])

        def _read(path, encoding="utf-8"):
            return PARENT_CONTENT if "parent" in Path(path).as_posix() else SUB_OK_CONTENT

        with (
            patch("Tooling.stages.validator.subprocess.run",
                  return_value=_mock_run(PASS_JSON)),
            patch("Tooling.stages.validator.Path.read_text", _read),
        ):
            errs = validate(conn, "sg", "/tmp/parent.lean", sgs, "/tmp/lake")

        assert any(e.check == "slug_unique" for e in errs)

    def test_all_clear(self):
        conn = _make_db()
        sgs = self._subgoals(["fresh_slug"])

        def _read(path, encoding="utf-8"):
            return PARENT_CONTENT if "parent" in Path(path).as_posix() else SUB_OK_CONTENT

        with (
            patch("Tooling.stages.validator.subprocess.run",
                  return_value=_mock_run(PASS_JSON)),
            patch("Tooling.stages.validator.Path.read_text", _read),
        ):
            errs = validate(conn, "sg", "/tmp/parent.lean", sgs, "/tmp/lake")

        assert errs == []
