"""Unit tests for Tooling/trust.py.

Coverage:
  - print_axioms: PRINT_AXIOMS_MOCK env hook (none / single / multiple / whitespace)
  - print_axioms: subprocess invocation args
  - _parse_print_axioms_output: bracketed list / no-axioms / empty output
  - build_trust_set: shape correctness / empty input / single entry
  - check_accept_rule: all-allowed / name-rejected / kind-rejected / empty trust_set /
                       empty allowed_axioms
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from Tooling.trust import (
    _parse_print_axioms_output,
    build_trust_set,
    check_accept_rule,
    print_axioms,
)


# ---------------------------------------------------------------------------
# print_axioms — PRINT_AXIOMS_MOCK hook
# ---------------------------------------------------------------------------

class TestPrintAxiomsMock:
    def test_mock_none_returns_empty(self, monkeypatch):
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "none")
        assert print_axioms("Nat.add_comm", "/any") == []

    def test_mock_single_axiom(self, monkeypatch):
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "propext")
        assert print_axioms("something", "/any") == ["propext"]

    def test_mock_three_axioms(self, monkeypatch):
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "propext,Quot.sound,Classical.choice")
        result = print_axioms("Classical.em", "/any")
        assert result == ["propext", "Quot.sound", "Classical.choice"]

    def test_mock_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", " propext , Quot.sound ")
        assert print_axioms("x", "/any") == ["propext", "Quot.sound"]

    def test_mock_empty_string_returns_empty(self, monkeypatch):
        monkeypatch.setenv("PRINT_AXIOMS_MOCK", "  ")
        assert print_axioms("x", "/any") == []


# ---------------------------------------------------------------------------
# print_axioms — subprocess invocation (no mock env set)
# ---------------------------------------------------------------------------

class TestPrintAxiomsSubprocess:
    def test_subprocess_argv(self, monkeypatch):
        """Verify the exact command issued matches impl §5.2 spec."""
        monkeypatch.delenv("PRINT_AXIOMS_MOCK", raising=False)

        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "'Nat.add_comm' does not depend on any axioms"
        fake_result.stderr = ""

        with patch("subprocess.run", return_value=fake_result) as mock_run:
            print_axioms("Nat.add_comm", "/some/cwd")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd == ["lake", "env", "lean", "-e", "#print axioms Nat.add_comm"]
        assert call_args.kwargs.get("cwd") == "/some/cwd"

    def test_timeout_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("PRINT_AXIOMS_MOCK", raising=False)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=60)):
            with pytest.raises(RuntimeError, match="timed out"):
                print_axioms("slow_thm", "/cwd")

    def test_nonzero_returncode_raises(self, monkeypatch):
        """Reject silent-PASS: lake error / unknown identifier must not parse to []."""
        monkeypatch.delenv("PRINT_AXIOMS_MOCK", raising=False)
        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stdout = ""
        fake_result.stderr = "error: unknown identifier 'NonExistent.thm'"
        with patch("subprocess.run", return_value=fake_result):
            with pytest.raises(RuntimeError, match="exit 1"):
                print_axioms("NonExistent.thm", "/cwd")

    def test_nonzero_returncode_includes_stderr(self, monkeypatch):
        """Stderr context propagated into RuntimeError message."""
        monkeypatch.delenv("PRINT_AXIOMS_MOCK", raising=False)
        fake_result = MagicMock()
        fake_result.returncode = 2
        fake_result.stdout = ""
        fake_result.stderr = "lake: build failed"
        with patch("subprocess.run", return_value=fake_result):
            with pytest.raises(RuntimeError, match="lake: build failed"):
                print_axioms("foo", "/cwd")

    def test_zero_returncode_no_brackets_returns_empty(self, monkeypatch):
        """rc=0 + 'does not depend on any axioms' is a legitimate trivial proof."""
        monkeypatch.delenv("PRINT_AXIOMS_MOCK", raising=False)
        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "'Nat.add_zero' does not depend on any axioms"
        fake_result.stderr = ""
        with patch("subprocess.run", return_value=fake_result):
            assert print_axioms("Nat.add_zero", "/cwd") == []


# ---------------------------------------------------------------------------
# _parse_print_axioms_output
# ---------------------------------------------------------------------------

class TestParseOutput:
    def test_single_axiom_in_brackets(self):
        out = "'Nat.mul_assoc' depends on axioms: [propext]"
        assert _parse_print_axioms_output(out) == ["propext"]

    def test_multiple_axioms_in_brackets(self):
        out = "'Classical.em' depends on axioms: [propext, Quot.sound, Classical.choice]"
        result = _parse_print_axioms_output(out)
        assert result == ["propext", "Quot.sound", "Classical.choice"]

    def test_no_axioms_line(self):
        out = "'Nat.add_comm' does not depend on any axioms"
        assert _parse_print_axioms_output(out) == []

    def test_empty_output(self):
        assert _parse_print_axioms_output("") == []

    def test_bracket_whitespace_trimmed(self):
        out = "thm: [ propext ,  Quot.sound ]"
        assert _parse_print_axioms_output(out) == ["propext", "Quot.sound"]


# ---------------------------------------------------------------------------
# build_trust_set
# ---------------------------------------------------------------------------

class TestBuildTrustSet:
    def test_three_axioms_shape(self):
        ts = build_trust_set(["propext", "Quot.sound", "Classical.choice"])
        assert len(ts) == 3
        for entry in ts:
            assert entry["kind"] == "lean_axiom"
            assert entry["provenance"] == "lean #print axioms"
            assert "name" in entry
        assert {e["name"] for e in ts} == {"propext", "Quot.sound", "Classical.choice"}

    def test_empty_input(self):
        assert build_trust_set([]) == []

    def test_single_entry_exact_shape(self):
        ts = build_trust_set(["propext"])
        assert ts == [{"name": "propext", "kind": "lean_axiom", "provenance": "lean #print axioms"}]

    def test_no_confidence_field(self):
        # confidence omitted per impl §5.2 (implicitly 1.0)
        ts = build_trust_set(["propext"])
        assert "confidence" not in ts[0]


# ---------------------------------------------------------------------------
# check_accept_rule
# ---------------------------------------------------------------------------

class TestCheckAcceptRule:
    _allowed = frozenset(["propext", "Quot.sound", "Classical.choice"])

    def test_all_in_allowed(self):
        ts = build_trust_set(["propext", "Quot.sound"])
        ok, rejected = check_accept_rule(ts, self._allowed)
        assert ok
        assert rejected == []

    def test_name_not_in_allowed(self):
        ts = build_trust_set(["propext", "Classical.choice"])
        ok, rejected = check_accept_rule(ts, frozenset(["propext"]))
        assert not ok
        assert "Classical.choice" in rejected

    def test_wrong_kind_rejected(self):
        ts = [{"name": "propext", "kind": "computational", "provenance": "x"}]
        ok, rejected = check_accept_rule(ts, self._allowed)
        assert not ok
        assert "propext" in rejected

    def test_empty_trust_set_accepted(self):
        ok, rejected = check_accept_rule([], self._allowed)
        assert ok
        assert rejected == []

    def test_empty_allowed_rejects_all(self):
        ts = build_trust_set(["propext"])
        ok, rejected = check_accept_rule(ts, frozenset())
        assert not ok
        assert "propext" in rejected

    def test_multiple_violations_all_reported(self):
        ts = build_trust_set(["propext", "Quot.sound", "Classical.choice"])
        ok, rejected = check_accept_rule(ts, frozenset(["propext"]))
        assert not ok
        assert set(rejected) == {"Quot.sound", "Classical.choice"}

    def test_mixed_kinds(self):
        ts = [
            {"name": "propext", "kind": "lean_axiom", "provenance": "lean #print axioms"},
            {"name": "eval_hash", "kind": "computational", "provenance": "evaluator"},
        ]
        ok, rejected = check_accept_rule(ts, self._allowed)
        assert not ok
        assert "eval_hash" in rejected
        assert "propext" not in rejected
