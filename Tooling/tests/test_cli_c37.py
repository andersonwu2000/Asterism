"""Tests for P5 C37 CLI extension: agent test --provider."""
from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from Tooling.agent.provider import AgentResponse, ProviderError
# Import provider modules so the patch() lookups can find them
import Tooling.agent.providers.claude  # noqa: F401
import Tooling.agent.providers.gemini  # noqa: F401
import Tooling.agent.providers.codex   # noqa: F401
from Tooling.cli import build_parser, cmd_agent_test


def _args(**kwargs):
    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParserAgentTest:
    def test_basic_parse(self):
        p = build_parser()
        args = p.parse_args([
            "agent", "test", "--provider", "claude", "--prompt", "hi",
        ])
        assert args.command == "agent"
        assert args.agent_command == "test"
        assert args.provider == "claude"
        assert args.prompt == "hi"
        assert args.model_tier == "sonnet"  # default

    def test_provider_choices(self):
        p = build_parser()
        for prov in ["claude", "gemini", "codex"]:
            args = p.parse_args([
                "agent", "test", "--provider", prov, "--prompt", "x",
            ])
            assert args.provider == prov

    def test_invalid_provider_rejected(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args([
                "agent", "test", "--provider", "bogus", "--prompt", "x",
            ])

    def test_model_tier_choices(self):
        p = build_parser()
        for tier in ["haiku", "sonnet", "opus"]:
            args = p.parse_args([
                "agent", "test", "--provider", "claude",
                "--prompt", "x", "--model-tier", tier,
            ])
            assert args.model_tier == tier

    def test_invalid_tier_rejected(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args([
                "agent", "test", "--provider", "claude",
                "--prompt", "x", "--model-tier", "bogus",
            ])

    def test_prompt_required(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["agent", "test", "--provider", "claude"])

    def test_provider_required(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["agent", "test", "--prompt", "x"])


# ---------------------------------------------------------------------------
# cmd_agent_test
# ---------------------------------------------------------------------------


class TestCmdAgentTest:
    def test_invokes_claude_provider(self, capsys):
        with patch(
            "Tooling.agent.providers.claude.ClaudeProvider.invoke",
            return_value=AgentResponse(
                output="hello", session_id="s1",
                exit_code=0, extra={"model_id": "claude-sonnet-4-6"},
            ),
        ) as mock_invoke:
            with pytest.raises(SystemExit) as exc:
                cmd_agent_test(_args(
                    provider="claude", prompt="hi",
                    model_tier="sonnet",
                ))
            assert exc.value.code == 0
        mock_invoke.assert_called_once()
        out = capsys.readouterr().out
        assert "agent test: claude" in out
        assert "claude-sonnet-4-6" in out
        assert "hello" in out

    def test_invokes_gemini_provider(self, capsys):
        with patch(
            "Tooling.agent.providers.gemini.GeminiProvider.invoke",
            return_value=AgentResponse(
                output="hi from gemini", session_id="s2",
                exit_code=0, extra={"model_id": "gemini-2.5-pro"},
            ),
        ) as mock_invoke:
            with pytest.raises(SystemExit) as exc:
                cmd_agent_test(_args(
                    provider="gemini", prompt="hi",
                    model_tier="sonnet",
                ))
            assert exc.value.code == 0
        mock_invoke.assert_called_once()
        out = capsys.readouterr().out
        assert "agent test: gemini" in out
        assert "gemini-2.5-pro" in out

    def test_invokes_codex_provider(self, capsys):
        with patch(
            "Tooling.agent.providers.codex.CodexProvider.invoke",
            return_value=AgentResponse(
                output="hi from codex", session_id="s3",
                exit_code=0, extra={"model_id": "gpt-5"},
            ),
        ) as mock_invoke:
            with pytest.raises(SystemExit) as exc:
                cmd_agent_test(_args(
                    provider="codex", prompt="hi",
                    model_tier="sonnet",
                ))
            assert exc.value.code == 0
        mock_invoke.assert_called_once()
        out = capsys.readouterr().out
        assert "agent test: codex" in out

    def test_provider_error_exits_2(self, capsys):
        """ProviderError → exit 2 with stderr message."""
        with patch(
            "Tooling.agent.providers.claude.ClaudeProvider.invoke",
            side_effect=ProviderError("simulated failure"),
        ):
            with pytest.raises(SystemExit) as exc:
                cmd_agent_test(_args(
                    provider="claude", prompt="x",
                    model_tier="sonnet",
                ))
            assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "ProviderError" in err
        assert "simulated failure" in err

    def test_nonzero_exit_propagated(self, capsys):
        """Provider-returned non-zero exit_code propagates to sys.exit."""
        with patch(
            "Tooling.agent.providers.claude.ClaudeProvider.invoke",
            return_value=AgentResponse(
                output="oops", session_id="s4", exit_code=7,
                extra={"model_id": "claude-sonnet-4-6"},
            ),
        ):
            with pytest.raises(SystemExit) as exc:
                cmd_agent_test(_args(
                    provider="claude", prompt="x",
                    model_tier="sonnet",
                ))
            assert exc.value.code == 7

    def test_passes_prompt_and_tier_to_provider(self):
        with patch(
            "Tooling.agent.providers.claude.ClaudeProvider.invoke",
            return_value=AgentResponse(
                output="", session_id="s",
                exit_code=0, extra={"model_id": "x"},
            ),
        ) as mock_invoke:
            with pytest.raises(SystemExit):
                cmd_agent_test(_args(
                    provider="claude", prompt="my-actual-prompt",
                    model_tier="haiku",
                ))
        # invoke(model_tier, prompt, scope_dirs, session_id)
        called_args = mock_invoke.call_args[0]
        assert called_args[0] == "haiku"
        assert called_args[1] == "my-actual-prompt"
        assert isinstance(called_args[2], list)
        assert len(called_args[2]) == 1  # tempdir as scope_dirs[0]
