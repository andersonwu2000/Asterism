"""Unit tests for Tooling/agent/providers/gemini.py (P5 C35).

All subprocess calls mocked — no real gemini CLI invocations. Pattern
mirrors test_provider.py for ClaudeProvider.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.agent.provider import AgentResponse, ProviderError
from Tooling.agent.providers.gemini import (
    GEMINI_MODEL_MAP,
    GeminiProvider,
)


def _mock_completed(stdout="agent output", returncode=0):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# model_map
# ---------------------------------------------------------------------------

class TestModelMap:
    def test_three_tier_aliasing(self):
        # Per spike-020 D-20-1: gemini lacks strict opus, opus aliases to pro
        assert GEMINI_MODEL_MAP["haiku"] == "gemini-2.5-flash"
        assert GEMINI_MODEL_MAP["sonnet"] == "gemini-2.5-pro"
        assert GEMINI_MODEL_MAP["opus"] == "gemini-2.5-pro"

    def test_resolve_tier(self):
        p = GeminiProvider()
        assert p.resolve_model_id("haiku") == "gemini-2.5-flash"

    def test_resolve_literal_passthrough(self):
        p = GeminiProvider()
        # Unknown tier returned unchanged (lets META.md specify literal id)
        assert p.resolve_model_id("custom-experimental-id") == \
            "custom-experimental-id"


# ---------------------------------------------------------------------------
# _build_cmd — gemini flag mapping per spike-019 D-19-1
# ---------------------------------------------------------------------------

class TestBuildCmd:
    def _provider(self):
        return GeminiProvider(gemini_bin="gemini")

    def test_basic_cmd(self):
        p = self._provider()
        cmd = p._build_cmd("gemini-2.5-pro", "hello", ["/staging"])
        assert cmd[0] == "gemini"
        assert "-p" in cmd
        assert "hello" in cmd
        assert "-m" in cmd
        assert "gemini-2.5-pro" in cmd

    def test_approval_mode_auto_edit(self):
        p = self._provider()
        cmd = p._build_cmd("gemini-2.5-pro", "p", ["/s"])
        assert "--approval-mode" in cmd
        idx = cmd.index("--approval-mode")
        assert cmd[idx + 1] == "auto_edit"

    def test_no_include_directories_flag_when_only_cwd(self):
        """When scope_dirs has only one entry (the cwd), no
        --include-directories flag is emitted (csv would be empty)."""
        p = self._provider()
        cmd = p._build_cmd("gemini-2.5-pro", "p", ["/staging_only"])
        assert "--include-directories" not in cmd

    def test_extra_dirs_csv_join(self):
        """Multiple extra dirs (scope_dirs[1:]) are comma-joined into a
        single --include-directories flag value (per spike-019 D-19-1
        canonical CSV form)."""
        p = self._provider()
        cmd = p._build_cmd(
            "gemini-2.5-pro", "p",
            ["/staging", "/problem", "/library"],
        )
        assert cmd.count("--include-directories") == 1
        idx = cmd.index("--include-directories")
        assert cmd[idx + 1] == "/problem,/library"

    def test_no_session_id_flag(self):
        """gemini CLI does not accept fresh --session-id. Provider tracks
        session_id in AgentResponse.extra; not passed to argv."""
        p = self._provider()
        cmd = p._build_cmd("gemini-2.5-pro", "p", ["/s"])
        # Neither --session-id nor -r/--resume should be emitted on a
        # fresh invocation
        assert "--session-id" not in cmd
        assert "--resume" not in cmd
        assert "-r" not in cmd

    def test_no_permission_mode_flag(self):
        """gemini uses --approval-mode (not claude's --permission-mode);
        the claude flag must NOT leak into gemini argv."""
        p = self._provider()
        cmd = p._build_cmd("gemini-2.5-pro", "p", ["/s"])
        assert "--permission-mode" not in cmd
        assert "acceptEdits" not in cmd

    def test_no_add_dir_flag(self):
        """Claude's repeated --add-dir must not leak into gemini argv."""
        p = self._provider()
        cmd = p._build_cmd(
            "gemini-2.5-pro", "p", ["/s1", "/s2", "/s3"]
        )
        assert "--add-dir" not in cmd


# ---------------------------------------------------------------------------
# invoke — subprocess mocked
# ---------------------------------------------------------------------------

class TestGeminiInvoke:
    def test_successful_invoke(self, tmp_path):
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed("done")) as mock_run:
            resp = p.invoke(
                "sonnet", "my prompt", [str(tmp_path)], "sess1"
            )
        assert resp.output == "done"
        assert resp.exit_code == 0
        assert resp.session_id == "sess1"
        assert resp.extra["model_id"] == "gemini-2.5-pro"

    def test_cmd_args_passed_to_subprocess(self, tmp_path):
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("haiku", "prompt", [str(tmp_path)], "sess42")
        cmd_passed = mock_run.call_args[0][0]
        assert "-p" in cmd_passed
        assert "prompt" in cmd_passed
        assert "-m" in cmd_passed
        assert "gemini-2.5-flash" in cmd_passed
        assert "--approval-mode" in cmd_passed

    def test_extra_scope_dirs_csv(self, tmp_path):
        staging = tmp_path / "stg"
        problem = tmp_path / "prob"
        staging.mkdir()
        problem.mkdir()
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "p", [str(staging), str(problem)], "s1")
        cmd_passed = mock_run.call_args[0][0]
        assert "--include-directories" in cmd_passed
        idx = cmd_passed.index("--include-directories")
        assert cmd_passed[idx + 1] == str(problem)

    def test_empty_scope_dirs_raises(self, tmp_path):
        p = GeminiProvider(repo_root=tmp_path)
        with pytest.raises(ProviderError, match="scope_dirs must not be empty"):
            p.invoke("sonnet", "p", [], "s1")

    def test_timeout_raises_provider_error(self, tmp_path):
        p = GeminiProvider(invoke_timeout=1.0, repo_root=tmp_path)
        with patch("subprocess.run",
                   side_effect=subprocess.TimeoutExpired("gemini", 1.0)):
            with pytest.raises(ProviderError, match="timed out"):
                p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_binary_not_found_raises_provider_error(self, tmp_path):
        p = GeminiProvider(gemini_bin="nonexistent_bin", repo_root=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(ProviderError, match="not found"):
                p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_cwd_defaults_to_first_scope_dir(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "p", [str(staging), str(tmp_path)], "s1")
        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == str(staging)

    def test_cwd_override(self, tmp_path):
        custom = tmp_path / "custom"
        custom.mkdir()
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke(
                "sonnet", "p", [str(tmp_path)], "s1", cwd=str(custom),
            )
        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == str(custom)

    def test_stdin_devnull_and_stderr_merged(self, tmp_path):
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")
        kwargs = mock_run.call_args[1]
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.STDOUT


# ---------------------------------------------------------------------------
# gc_session — no-op for P5 C35 + empty-id guard
# ---------------------------------------------------------------------------

class TestGcSession:
    def test_no_op_returns_none(self):
        p = GeminiProvider()
        assert p.gc_session("any-id") is None

    def test_empty_session_id_raises(self):
        p = GeminiProvider()
        with pytest.raises(ValueError, match="non-empty"):
            p.gc_session("")


# ---------------------------------------------------------------------------
# check_scope — git status backstop (parity with ClaudeProvider)
# ---------------------------------------------------------------------------

class TestCheckScope:
    def test_clean_tree_passes(self, tmp_path):
        p = GeminiProvider(repo_root=tmp_path)
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert p.check_scope(tmp_path) is True

    def test_only_staging_changes_pass(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = GeminiProvider(repo_root=tmp_path)
        mock_result = MagicMock()
        mock_result.stdout = " M staging/file.lean\n"
        with patch("subprocess.run", return_value=mock_result):
            assert p.check_scope(staging) is True

    def test_outside_change_fails(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = GeminiProvider(repo_root=tmp_path)
        mock_result = MagicMock()
        mock_result.stdout = " M outside/secret.txt\n"
        with patch("subprocess.run", return_value=mock_result):
            assert p.check_scope(staging) is False

    def test_git_unavailable_fails_safe(self, tmp_path):
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert p.check_scope(tmp_path) is False

    def test_git_timeout_fails_safe(self, tmp_path):
        p = GeminiProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   side_effect=subprocess.TimeoutExpired("git", 30)):
            assert p.check_scope(tmp_path) is False
