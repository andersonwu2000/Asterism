"""Unit tests for Tooling.lake harness.

Four cases from spike-003 decision tree:
  simp pass / type error / sorry / timeout
Subprocess is mocked; fixture .lean paths are passed as lean_file but never
actually opened (the mock intercepts Popen before any I/O occurs).
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.lake import LakeResult, _parse_json_lines, run_lean

FIXTURES = Path(__file__).parent / "fixtures" / "spikes"


def _mock_proc(stdout: str, returncode: int) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate.return_value = (stdout.encode("utf-8"), b"")
    return proc


def _j(**kwargs) -> str:
    return json.dumps(kwargs)


# ---------------------------------------------------------------------------
# parse helper
# ---------------------------------------------------------------------------

class TestParseJsonLines:
    def test_empty(self):
        assert _parse_json_lines("") == []

    def test_single(self):
        line = _j(kind="hasSorry", severity="warning")
        assert _parse_json_lines(line) == [{"kind": "hasSorry", "severity": "warning"}]

    def test_skips_non_json(self):
        text = "not json\n" + _j(kind="x") + "\n"
        result = _parse_json_lines(text)
        assert len(result) == 1
        assert result[0]["kind"] == "x"

    def test_multiple_lines(self):
        lines = "\n".join([_j(kind="a"), _j(kind="b")])
        assert len(_parse_json_lines(lines)) == 2


# ---------------------------------------------------------------------------
# run_lean — four canonical cases
# ---------------------------------------------------------------------------

class TestRunLean:
    def test_simp_pass(self):
        """rc=0, empty stdout → proved."""
        with patch("Tooling.lake.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _mock_proc("", 0)
            result = run_lean(
                str(FIXTURES / "spike003_type_error_nolib.lean"), "fake_cwd"
            )
        assert result.outcome == "proved"
        assert result.messages == []
        assert not result.timed_out

    def test_type_error(self):
        """rc=1 → exhausted regardless of message content."""
        msg = _j(
            severity="error",
            kind="Tactic.unsolvedGoals",
            data="unsolved goals\n⊢ False",
            fileName="test.lean",
            pos={"line": 3, "column": 53},
            endPos={"line": 3, "column": 53},
        )
        with patch("Tooling.lake.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _mock_proc(msg + "\n", 1)
            result = run_lean(
                str(FIXTURES / "spike003_type_error_nolib.lean"), "fake_cwd"
            )
        assert result.outcome == "exhausted"
        assert not result.timed_out
        assert result.messages[0]["kind"] == "Tactic.unsolvedGoals"

    def test_sorry_detected(self):
        """rc=0 but kind=hasSorry → exhausted (exit code alone is insufficient)."""
        msg = _j(
            severity="warning",
            kind="hasSorry",
            data="declaration uses `sorry`",
            fileName="test.lean",
            pos={"line": 2, "column": 0},
            endPos={"line": 2, "column": 0},
        )
        with patch("Tooling.lake.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _mock_proc(msg + "\n", 0)
            result = run_lean(
                str(FIXTURES / "spike003_sorry_nolib.lean"), "fake_cwd"
            )
        assert result.outcome == "exhausted"
        assert not result.timed_out
        assert result.messages[0]["kind"] == "hasSorry"

    def test_timeout_kills_process_tree(self):
        """TimeoutExpired → exhausted + timed_out=True + _kill_tree invoked."""
        proc = MagicMock()
        proc.pid = 9999
        proc.communicate.side_effect = subprocess.TimeoutExpired(cmd=[], timeout=1)

        with patch("Tooling.lake.subprocess.Popen", return_value=proc):
            with patch("Tooling.lake._kill_tree") as mock_kill:
                result = run_lean(
                    str(FIXTURES / "spike003_sorry_nolib.lean"),
                    "fake_cwd",
                    timeout=1.0,
                )

        mock_kill.assert_called_once_with(9999)
        proc.wait.assert_called_once()
        assert result.outcome == "exhausted"
        assert result.timed_out
        assert result.messages == []
