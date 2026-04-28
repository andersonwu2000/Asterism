"""Unit tests for PROVIDER_MOCK_<NAME> env hook (P5 C37).

Verifies the env-hook handler in Provider._maybe_apply_mock and its
wire-in at each provider's invoke() entrypoint. Per docs/dev/test_hooks.md:

  PROVIDER_MOCK_CLAUDE | PROVIDER_MOCK_GEMINI | PROVIDER_MOCK_CODEX
  modes: fail_always | fail_after_<N> | evil_write
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from Tooling.agent.provider import AgentResponse, ProviderError
from Tooling.agent.providers.claude import ClaudeProvider
from Tooling.agent.providers.gemini import GeminiProvider
from Tooling.agent.providers.codex import CodexProvider


# ---------------------------------------------------------------------------
# fail_always — every call raises
# ---------------------------------------------------------------------------


class TestFailAlways:
    def test_claude_fail_always(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_always")
        p = ClaudeProvider(repo_root=tmp_path)
        with pytest.raises(ProviderError, match="fail_always"):
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_gemini_fail_always(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROVIDER_MOCK_GEMINI", "fail_always")
        p = GeminiProvider(repo_root=tmp_path)
        with pytest.raises(ProviderError, match="fail_always"):
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_codex_fail_always(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROVIDER_MOCK_CODEX", "fail_always")
        p = CodexProvider(repo_root=tmp_path)
        with pytest.raises(ProviderError, match="fail_always"):
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_no_subprocess_call_when_mocked(self, tmp_path, monkeypatch):
        """fail_always must short-circuit BEFORE subprocess.run is called."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_always")
        p = ClaudeProvider(repo_root=tmp_path)
        with patch("subprocess.run") as mock_run:
            with pytest.raises(ProviderError):
                p.invoke("sonnet", "p", [str(tmp_path)], "s1")
        mock_run.assert_not_called()

    def test_isolation_per_provider_env(self, tmp_path, monkeypatch):
        """Setting PROVIDER_MOCK_CLAUDE only affects ClaudeProvider; gemini
        and codex remain unaffected (per-provider env semantics)."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_always")
        # Gemini should still try the real subprocess (which we mock)
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="ok",
            ),
        ):
            p = GeminiProvider(repo_root=tmp_path)
            resp = p.invoke("sonnet", "p", [str(tmp_path)], "s1")
            assert resp.exit_code == 0


# ---------------------------------------------------------------------------
# fail_after_<N> — succeed N times, then raise
# ---------------------------------------------------------------------------


class TestFailAfterN:
    def test_claude_fail_after_2(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_after_2")
        p = ClaudeProvider(repo_root=tmp_path)
        # Calls 1, 2 should succeed (mock returns AgentResponse)
        r1 = p.invoke("sonnet", "p", [str(tmp_path)], "s1")
        r2 = p.invoke("sonnet", "p", [str(tmp_path)], "s2")
        assert r1.extra["call_count"] == 1
        assert r2.extra["call_count"] == 2
        # Call 3 should raise
        with pytest.raises(ProviderError, match="fail_after_2"):
            p.invoke("sonnet", "p", [str(tmp_path)], "s3")

    def test_fail_after_zero_raises_immediately(self, tmp_path, monkeypatch):
        """fail_after_0 means raise on the very first call."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_after_0")
        p = ClaudeProvider(repo_root=tmp_path)
        with pytest.raises(ProviderError, match="fail_after_0"):
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_invalid_n_raises_value_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_after_xyz")
        p = ClaudeProvider(repo_root=tmp_path)
        with pytest.raises(ValueError, match="fail_after_<integer>"):
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_counter_per_instance_not_shared(self, tmp_path, monkeypatch):
        """Two provider instances each get their own counter."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_after_1")
        p1 = ClaudeProvider(repo_root=tmp_path)
        p2 = ClaudeProvider(repo_root=tmp_path)
        # Each provider's first call succeeds
        r1 = p1.invoke("sonnet", "p", [str(tmp_path)], "s1")
        r2 = p2.invoke("sonnet", "p", [str(tmp_path)], "s2")
        assert r1.extra["call_count"] == 1
        assert r2.extra["call_count"] == 1


# ---------------------------------------------------------------------------
# evil_write — write outside scope_dirs[0]
# ---------------------------------------------------------------------------


class TestEvilWrite:
    def test_writes_outside_staging(self, tmp_path, monkeypatch):
        """evil_write writes to a path OUTSIDE scope_dirs[0] (the staging
        dir parent), so a downstream check_scope catches the leak."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "evil_write")
        staging = tmp_path / "staging"
        staging.mkdir()
        p = ClaudeProvider(repo_root=tmp_path)
        resp = p.invoke("sonnet", "p", [str(staging)], "abcdef1234")
        # Sentinel file lives in tmp_path (parent of staging), NOT in staging
        evil_path = Path(resp.extra["evil_path"])
        assert evil_path.parent == tmp_path
        assert evil_path.exists()
        assert "PROVIDER_MOCK=evil_write" in evil_path.read_text()

    def test_evil_write_returns_success_response(self, tmp_path, monkeypatch):
        """evil_write returns AgentResponse (exit_code=0) so the caller's
        validate_scope is what catches the leak, not invoke itself."""
        monkeypatch.setenv("PROVIDER_MOCK_GEMINI", "evil_write")
        staging = tmp_path / "stg"
        staging.mkdir()
        p = GeminiProvider(repo_root=tmp_path)
        resp = p.invoke("sonnet", "p", [str(staging)], "session_xyz")
        assert resp.exit_code == 0
        assert resp.extra["mock_mode"] == "evil_write"

    def test_each_provider_writes_unique_sentinel(self, tmp_path, monkeypatch):
        """Each provider's evil_write produces a distinct sentinel file
        so concurrent fail-different-provider scenarios don't clobber."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "evil_write")
        monkeypatch.setenv("PROVIDER_MOCK_CODEX", "evil_write")
        staging = tmp_path / "s"
        staging.mkdir()
        c = ClaudeProvider(repo_root=tmp_path)
        x = CodexProvider(repo_root=tmp_path)
        r_claude = c.invoke("sonnet", "p", [str(staging)], "session_aaaaaaaa")
        r_codex = x.invoke("sonnet", "p", [str(staging)], "session_bbbbbbbb")
        assert "EVIL_claude_" in r_claude.extra["evil_path"]
        assert "EVIL_codex_" in r_codex.extra["evil_path"]
        assert r_claude.extra["evil_path"] != r_codex.extra["evil_path"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestModeValidation:
    def test_unknown_mode_raises_value_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "bogus_mode")
        p = ClaudeProvider(repo_root=tmp_path)
        with pytest.raises(ValueError, match="unknown PROVIDER_MOCK_CLAUDE"):
            p.invoke("sonnet", "p", [str(tmp_path)], "s1")

    def test_no_env_runs_real_path(self, tmp_path, monkeypatch):
        """When env is not set, _maybe_apply_mock returns None and invoke
        proceeds to the real subprocess.run path."""
        monkeypatch.delenv("PROVIDER_MOCK_CLAUDE", raising=False)
        p = ClaudeProvider(repo_root=tmp_path)
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="real",
            ),
        ) as mock_run:
            resp = p.invoke("sonnet", "p", [str(tmp_path)], "s1")
        mock_run.assert_called_once()
        assert resp.output == "real"

    def test_empty_env_treated_as_no_mock(self, tmp_path, monkeypatch):
        """Empty string env value is treated the same as unset — fall through."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "")
        p = ClaudeProvider(repo_root=tmp_path)
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="real",
            ),
        ):
            resp = p.invoke("sonnet", "p", [str(tmp_path)], "s1")
        assert resp.output == "real"


# ---------------------------------------------------------------------------
# Integration: FallbackChain falls through claude → gemini on PROVIDER_MOCK_CLAUDE=fail_always
# ---------------------------------------------------------------------------


class TestFallbackChainIntegration:
    def test_chain_fails_over_to_gemini_when_claude_mocked_fail(
        self, tmp_path, monkeypatch,
    ):
        """Acceptance #14 sketch: PROVIDER_MOCK_CLAUDE=fail_always →
        FallbackChain.run drops claude and tries gemini, which (mocked
        below) succeeds on first try."""
        from Tooling.agent.provider import FallbackChain

        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_always")
        chain = FallbackChain(
            providers=[
                ClaudeProvider(repo_root=tmp_path),
                GeminiProvider(repo_root=tmp_path),
            ],
            n_retry=1,
        )
        with patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="from gemini",
            ),
        ) as mock_run:
            resp, outcome = chain.run(
                "sonnet", "p", [str(tmp_path)], "s1",
            )
        assert outcome == "success"
        assert resp is not None
        assert resp.output == "from gemini"
        # Only gemini's subprocess.run should have been called (claude was
        # short-circuited by the mock fail).
        assert mock_run.call_count == 1
