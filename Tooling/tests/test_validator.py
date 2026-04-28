"""Unit tests for Tooling/stages/validator.py (C11 R3).

After R2 audit:
  - extract_theorem_type / regex parsing of Lean source has been removed
    (architectural rule violation).  No tests for it here.
  - hyp_carry tests mock subprocess.run only — file reading is now done
    inside tools/validator.lean, not Python.
  - Failure paths (returncode!=0, parent_error JSON, no JSON, timeout)
    are explicitly covered.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from Tooling.db.connect import init_schema
from Tooling.stages.validator import (
    MAX_SUBGOALS,
    ValidatorError,
    check_hyp_carry,
    check_max_subgoals,
    check_slug_unique,
    validate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
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


def _mock_run(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


# Canonical JSON payloads produced by tools/validator.lean ------------------

PASS_JSON = json.dumps({
    "parent_error": None,
    "subgoals": [
        {"subgoal": "/tmp/sub0.lean", "missing_binders": [], "error": None},
    ],
})

MISSING_BINDER_JSON = json.dumps({
    "parent_error": None,
    "subgoals": [
        {"subgoal": "/tmp/sub0.lean", "missing_binders": ["h"], "error": None},
    ],
})

PARENT_ERR_JSON = json.dumps({
    "parent_error": "no user theorem found in /tmp/parent.lean",
    "subgoals": [],
})

SUB_ELAB_ERR_JSON = json.dumps({
    "parent_error": None,
    "subgoals": [
        {"subgoal": "/tmp/sub0.lean", "missing_binders": [],
         "error": "runFrontend reported errors in /tmp/sub0.lean"},
    ],
})

MULTI_PARTIAL_JSON = json.dumps({
    "parent_error": None,
    "subgoals": [
        {"subgoal": "/tmp/sub0.lean", "missing_binders": [],     "error": None},
        {"subgoal": "/tmp/sub1.lean", "missing_binders": ["h"],  "error": None},
    ],
})


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
# check_hyp_carry — pure subprocess mocking, no filesystem
# ---------------------------------------------------------------------------

class TestHypCarry:
    def _call(self, *, stdout: str = "", stderr: str = "", returncode: int = 0,
              n_subgoals: int = 1) -> list[ValidatorError]:
        sgs = [{"id": f"G{i+1:03d}", "lean_path": f"/tmp/sub{i}.lean"}
               for i in range(n_subgoals)]
        with patch(
            "Tooling.stages.validator.subprocess.run",
            return_value=_mock_run(stdout, stderr, returncode),
        ):
            return check_hyp_carry(
                parent_lean_path="/tmp/parent.lean",
                subgoals=sgs,
                lake_cwd="/tmp/lake",
            )

    # ----- success paths -----

    def test_pass_returns_no_errors(self):
        errs = self._call(stdout=PASS_JSON, returncode=0)
        assert errs == []

    def test_lean_diagnostic_noise_before_json(self):
        noisy = (
            "/tools/validator.lean:10:0: warning: unused variable `x`\n"
            + PASS_JSON
        )
        errs = self._call(stdout=noisy, returncode=0)
        assert errs == []

    def test_empty_subgoals(self):
        empty = json.dumps({"parent_error": None, "subgoals": []})
        errs = self._call(stdout=empty, returncode=0, n_subgoals=0)
        assert errs == []

    # ----- failure paths -----

    def test_missing_binder_returns_error(self):
        errs = self._call(stdout=MISSING_BINDER_JSON, returncode=0)
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "G001" in errs[0].detail
        assert "h" in errs[0].detail

    def test_multi_subgoals_partial_fail(self):
        errs = self._call(stdout=MULTI_PARTIAL_JSON, returncode=0, n_subgoals=2)
        assert len(errs) == 1
        # only G002 has missing binders
        assert "G002" in errs[0].detail

    def test_parent_error_short_circuits(self):
        """JSON has parent_error → no per-subgoal results, single error."""
        errs = self._call(stdout=PARENT_ERR_JSON, returncode=2)
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "parent" in errs[0].detail.lower()

    def test_subgoal_elab_error_reported(self):
        errs = self._call(stdout=SUB_ELAB_ERR_JSON, returncode=0)
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "elab" in errs[0].detail.lower()

    def test_returncode_nonzero_no_parent_error(self):
        """Non-zero rc without parent_error → opaque rc/stderr error."""
        # JSON exists (so 'no JSON' branch isn't taken) but no parent_error
        # and no subgoal errors — yet rc!=0 indicates something broke.
        opaque = json.dumps({"parent_error": None, "subgoals": []})
        errs = self._call(stdout=opaque, stderr="something broke", returncode=3)
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "rc=3" in errs[0].detail

    def test_no_json_in_stdout(self):
        """No `{...}` line anywhere → explicit ValidatorError, not silent []."""
        errs = self._call(stdout="some warning\nno json here\n",
                          stderr="usage error\n", returncode=1)
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "no JSON" in errs[0].detail
        assert "rc=1" in errs[0].detail

    def test_invalid_json_falls_through_to_no_json(self):
        """Line starts with `{` but isn't valid JSON → treated as no JSON."""
        broken = "{not valid json}\n"
        errs = self._call(stdout=broken, returncode=0)
        assert len(errs) == 1
        assert "no JSON" in errs[0].detail

    def test_timeout_returns_error(self):
        sgs = [{"id": "G001", "lean_path": "/tmp/sub0.lean"}]
        with patch(
            "Tooling.stages.validator.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="lake", timeout=60),
        ):
            errs = check_hyp_carry(
                parent_lean_path="/tmp/parent.lean",
                subgoals=sgs,
                lake_cwd="/tmp/lake",
            )
        assert len(errs) == 1
        assert errs[0].check == "hyp_carry"
        assert "timed out" in errs[0].detail


# ---------------------------------------------------------------------------
# subprocess invocation shape
# ---------------------------------------------------------------------------

class TestSubprocessInvocation:
    """Verify the exact argv passed to subprocess matches impl §4.2 spec."""

    def test_cli_args_match_spec(self):
        sgs = [
            {"id": "G001", "lean_path": "/tmp/sub0.lean"},
            {"id": "G002", "lean_path": "/tmp/sub1.lean"},
        ]
        with patch(
            "Tooling.stages.validator.subprocess.run",
            return_value=_mock_run(PASS_JSON, returncode=0),
        ) as mock:
            check_hyp_carry(
                parent_lean_path="/tmp/parent.lean",
                subgoals=sgs,
                lake_cwd="/tmp/lake",
            )

        argv = mock.call_args[0][0]
        # lake env lean --run <validator.lean> -- hypothesis_carry --parent <p> --subgoals <s1> <s2>
        assert argv[0:3]   == ["lake", "env", "lean"]
        assert argv[3]     == "--run"
        assert argv[5]     == "--"
        assert argv[6]     == "hypothesis_carry"
        assert argv[7]     == "--parent"
        assert argv[8]     == "/tmp/parent.lean"
        assert argv[9]     == "--subgoals"
        assert argv[10:12] == ["/tmp/sub0.lean", "/tmp/sub1.lean"]
        assert mock.call_args[1]["cwd"] == "/tmp/lake"


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
        # No subprocess call should happen — hard gate.
        with patch(
            "Tooling.stages.validator.subprocess.run",
            return_value=_mock_run(PASS_JSON, returncode=0),
        ) as mock:
            errs = validate(conn, "sg", "/tmp/parent.lean", sgs, "/tmp/lake")
        assert len(errs) == 1
        assert errs[0].check == "max_subgoals"
        assert mock.call_count == 0

    def test_slug_collision_reported(self):
        conn = _make_db()
        _insert_goal(conn, "sg", "taken")
        sgs = self._subgoals(["taken"])
        with patch(
            "Tooling.stages.validator.subprocess.run",
            return_value=_mock_run(PASS_JSON, returncode=0),
        ):
            errs = validate(conn, "sg", "/tmp/parent.lean", sgs, "/tmp/lake")
        assert any(e.check == "slug_unique" for e in errs)

    def test_all_clear(self):
        conn = _make_db()
        sgs = self._subgoals(["fresh_slug"])
        with patch(
            "Tooling.stages.validator.subprocess.run",
            return_value=_mock_run(PASS_JSON, returncode=0),
        ):
            errs = validate(conn, "sg", "/tmp/parent.lean", sgs, "/tmp/lake")
        assert errs == []
