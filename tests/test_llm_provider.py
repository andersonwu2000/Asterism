"""LLM provider registry: dispatch by env, error on unknown, default Claude."""
from __future__ import annotations

import pytest

from Tooling import llm


def test_get_provider_default_is_claude_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTERISM_LLM_PROVIDER", raising=False)
    p = llm.get_provider()
    assert p.__class__.__name__ == "ClaudeCliProvider"


def test_get_provider_explicit_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTERISM_LLM_PROVIDER", "claude")
    p = llm.get_provider()
    assert p.__class__.__name__ == "ClaudeCliProvider"


def test_get_provider_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTERISM_LLM_PROVIDER", "CLAUDE")
    p = llm.get_provider()
    assert p.__class__.__name__ == "ClaudeCliProvider"


def test_get_provider_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTERISM_LLM_PROVIDER", "definitely-not-real")
    with pytest.raises(ValueError):
        llm.get_provider()


def test_llm_request_dataclass_fields() -> None:
    """Smoke test: LLMRequest accepts expected kwargs."""
    from pathlib import Path
    req = llm.LLMRequest(
        kind="backward",
        prompt_path=Path("/x/y.md"),
        problem_dir=Path("/x/p"),
        attempts_dir=Path("/x/a"),
        timeout_sec=600,
    )
    assert req.kind == "backward"
    assert req.timeout_sec == 600


# ---------------------------------------------------------------------
# F22 — complete_text one-shot interface (unit tests; mocks subprocess
# / urllib so we don't actually call claude or HTTP)
# ---------------------------------------------------------------------

def test_claude_complete_text_returns_none_when_cli_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `claude` on PATH → None (not an exception). Caller treats
    None as "provider unavailable, skip"."""
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: None)
    p = claude_cli.ClaudeCliProvider()
    assert p.complete_text(prompt="hello") is None


def test_claude_complete_text_returns_stdout_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess as _sub
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=0, stdout="  hi\n  ", stderr=""))
    p = claude_cli.ClaudeCliProvider()
    assert p.complete_text(prompt="hello") == "hi"


def test_claude_complete_text_returns_none_on_nonzero_rc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat any non-zero exit as failure — don't return partial / error
    output as if it were a real reply."""
    import subprocess as _sub
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=2, stdout="error msg", stderr=""))
    p = claude_cli.ClaudeCliProvider()
    assert p.complete_text(prompt="hello") is None


def test_claude_complete_text_returns_none_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess as _sub
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")

    def _timeout(*a, **kw):
        raise _sub.TimeoutExpired(cmd=a[0], timeout=1)
    monkeypatch.setattr(claude_cli.subprocess, "run", _timeout)
    p = claude_cli.ClaudeCliProvider()
    assert p.complete_text(prompt="hello", timeout_sec=1) is None


def test_openai_complete_text_returns_none_without_model_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caller never set ASTERISM_LLM_MODEL — no model to send to.
    Provider must fail-gracefully rather than POST a bogus request."""
    from Tooling.llm import openai_api
    monkeypatch.delenv("ASTERISM_LLM_MODEL", raising=False)
    p = openai_api.OpenAIProvider()
    assert p.complete_text(prompt="hello") is None
