"""Unit tests for Tooling/agent/providers/codex.py (P5 C36).

All subprocess calls mocked. Pattern mirrors test_provider.py /
test_provider_gemini.py.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from Tooling.agent.provider import AgentResponse, ProviderError
from Tooling.agent.providers.codex import (
    CODEX_MODEL_MAP,
    CodexProvider,
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
    def test_single_tier_aliasing(self):
        """Per spike-020 D-20-1: codex single-tier in P5; all tiers
        currently map to gpt-5 (P5.x patch will subdivide)."""
        assert CODEX_MODEL_MAP["haiku"] == "gpt-5"
        assert CODEX_MODEL_MAP["sonnet"] == "gpt-5"
        assert CODEX_MODEL_MAP["opus"] == "gpt-5"

    def test_resolve_tier(self):
        p = CodexProvider()
        assert p.resolve_model_id("sonnet") == "gpt-5"

    def test_resolve_literal_passthrough(self):
        p = CodexProvider()
        assert p.resolve_model_id("custom-model-id") == "custom-model-id"


# ---------------------------------------------------------------------------
# _build_cmd — codex flag mapping per spike-019 D-19-1 (post-C34 R3)
# ---------------------------------------------------------------------------

class TestBuildCmd:
    def _provider(self):
        return CodexProvider(codex_bin="codex")

    def test_basic_cmd_starts_with_exec_subcommand(self):
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "hello", ["/staging"])
        assert cmd[0] == "codex"
        assert cmd[1] == "exec"
        assert "-m" in cmd
        assert "gpt-5" in cmd

    def test_prompt_is_positional_at_end(self):
        """codex exec takes the prompt as a positional argument, not via
        a -p/--prompt flag."""
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "my-prompt", ["/staging"])
        assert "-p" not in cmd
        assert "--prompt" not in cmd
        assert cmd[-1] == "my-prompt"

    def test_cd_flag_sets_working_root(self):
        """C34 R3 fix: codex uses -C, --cd <DIR> to set working root."""
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "p", ["/staging"])
        assert "-C" in cmd
        idx = cmd.index("-C")
        assert cmd[idx + 1] == "/staging"

    def test_sandbox_workspace_write_with_full_auto(self):
        """spike-019 D-19-1: codex auto-approve via --sandbox workspace-write
        + --full-auto for non-interactive auto-execute."""
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "p", ["/s"])
        assert "--sandbox" in cmd
        idx = cmd.index("--sandbox")
        assert cmd[idx + 1] == "workspace-write"
        assert "--full-auto" in cmd

    def test_add_dir_flags_for_extra_scope(self):
        """C34 R3 fix: codex --add-dir mirrors claude's repeated flag,
        not config-based writable_roots."""
        p = self._provider()
        cmd = p._build_cmd(
            "gpt-5", "p",
            ["/staging", "/problem", "/library"],
        )
        # Two extra dirs → two --add-dir flags
        assert cmd.count("--add-dir") == 2
        positions = [i for i, x in enumerate(cmd) if x == "--add-dir"]
        assert cmd[positions[0] + 1] == "/problem"
        assert cmd[positions[1] + 1] == "/library"

    def test_no_add_dir_when_only_cwd(self):
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "p", ["/staging_only"])
        assert "--add-dir" not in cmd

    def test_no_session_id_flag(self):
        """codex exec does not accept --session-id for fresh runs (mirrors
        gemini); session_id stored in AgentResponse.extra only."""
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "p", ["/s"])
        assert "--session-id" not in cmd
        assert "--resume" not in cmd

    def test_no_permission_or_approval_mode_flag(self):
        """codex uses sandbox + --full-auto, not claude's permission-mode
        nor gemini's approval-mode."""
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "p", ["/s"])
        assert "--permission-mode" not in cmd
        assert "--approval-mode" not in cmd
        assert "acceptEdits" not in cmd
        assert "auto_edit" not in cmd

    def test_no_writable_roots_config_string(self):
        """C34 R3 fix: codex provider uses --add-dir directly; the
        -c sandbox_workspace_write.writable_roots=[...] config-string
        path is fallback only, NOT default."""
        p = self._provider()
        cmd = p._build_cmd(
            "gpt-5", "p", ["/s1", "/s2", "/s3"]
        )
        assert "writable_roots" not in " ".join(cmd)

    def test_no_dangerously_bypass_flag(self):
        """The dangerous escape hatch must not appear by default."""
        p = self._provider()
        cmd = p._build_cmd("gpt-5", "p", ["/s"])
        assert "--dangerously-bypass-approvals-and-sandbox" not in cmd


# ---------------------------------------------------------------------------
# invoke — subprocess mocked
# ---------------------------------------------------------------------------

class TestCodexInvoke:
    def test_successful_invoke(self, tmp_path):
        p = CodexProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed("done")) as mock_run:
            resp = p.invoke(
                "sonnet", "my prompt", [str(tmp_path)], "sess1"
            )
        assert resp.output == "done"
        assert resp.exit_code == 0
        assert resp.session_id == "sess1"
        assert resp.extra["model_id"] == "gpt-5"

    def test_cmd_args_passed_to_subprocess(self, tmp_path):
        p = CodexProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("haiku", "prompt", [str(tmp_path)], "sess42")
        cmd_passed = mock_run.call_args[0][0]
        assert cmd_passed[0] == "codex"
        assert cmd_passed[1] == "exec"
        assert "-m" in cmd_passed
        assert "gpt-5" in cmd_passed
        assert "--sandbox" in cmd_passed
        assert "workspace-write" in cmd_passed
        assert "--full-auto" in cmd_passed

    def test_extra_scope_dirs_become_add_dir_flags(self, tmp_path):
        staging = tmp_path / "stg"
        problem = tmp_path / "prob"
        staging.mkdir()
        problem.mkdir()
        p = CodexProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "p", [str(staging), str(problem)], "s1")
        cmd_passed = mock_run.call_args[0][0]
        assert "--add-dir" in cmd_passed
        idx = cmd_passed.index("--add-dir")
        assert cmd_passed[idx + 1] == str(problem)

    def test_empty_scope_dirs_raises(self, tmp_path):
        p = CodexProvider(repo_root=tmp_path)
        with pytest.raises(ProviderError, match="scope_dirs must not be empty"):
            p.invoke("sonnet", "p", [], "s1")

    def test_timeout_raises_provider_error(self, tmp_path):
        p = CodexProvider(invoke_timeout=1.0, repo_root=tmp_path)
        with patch("subprocess.run",
                   side_effect=subprocess.TimeoutExpired("codex", 1.0)):
            with pytest.raises(ProviderError, match="timed out"):
                p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_binary_not_found_raises_provider_error(self, tmp_path):
        p = CodexProvider(codex_bin="nonexistent_bin", repo_root=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(ProviderError, match="not found"):
                p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_cwd_defaults_to_first_scope_dir(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = CodexProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "p", [str(staging), str(tmp_path)], "s1")
        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == str(staging)

    def test_cwd_override(self, tmp_path):
        custom = tmp_path / "custom"
        custom.mkdir()
        p = CodexProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke(
                "sonnet", "p", [str(tmp_path)], "s1", cwd=str(custom),
            )
        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == str(custom)

    def test_stdin_devnull_and_stderr_merged(self, tmp_path):
        p = CodexProvider(repo_root=tmp_path)
        with patch("subprocess.run",
                   return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")
        kwargs = mock_run.call_args[1]
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.STDOUT


# ---------------------------------------------------------------------------
# gc_session — no-op + empty-id guard
# ---------------------------------------------------------------------------

class TestGcSession:
    def test_no_op_returns_none(self):
        p = CodexProvider()
        assert p.gc_session("any-id") is None

    def test_empty_session_id_raises(self):
        p = CodexProvider()
        with pytest.raises(ValueError, match="non-empty"):
            p.gc_session("")


# ---------------------------------------------------------------------------
# check_scope — git status backstop (parity)
# ---------------------------------------------------------------------------

class TestCheckScope:
    def test_clean_tree_passes(self, tmp_path):
        p = CodexProvider(repo_root=tmp_path)
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert p.check_scope(tmp_path) is True

    def test_outside_change_fails(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = CodexProvider(repo_root=tmp_path)
        mock_result = MagicMock()
        mock_result.stdout = " M outside/secret.txt\n"
        with patch("subprocess.run", return_value=mock_result):
            assert p.check_scope(staging) is False

    def test_git_unavailable_fails_safe(self, tmp_path):
        p = CodexProvider(repo_root=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert p.check_scope(tmp_path) is False
