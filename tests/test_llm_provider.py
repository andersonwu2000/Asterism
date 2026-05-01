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


# ---------------------------------------------------------------------
# F27 — system-prompt trim flags must accompany every claude invocation
# ---------------------------------------------------------------------

def _capture_cmd(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch claude_cli.subprocess.run to capture the cmd argv and
    return success without executing."""
    import subprocess as _sub
    from Tooling.llm import claude_cli
    captured: list = []

    def _fake_run(cmd, *a, **kw):
        captured.append(cmd)
        return _sub.CompletedProcess(args=cmd, returncode=0,
                                     stdout="ok", stderr="")
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(claude_cli.subprocess, "run", _fake_run)
    return captured


def test_claude_spawn_includes_trim_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spawn() should pass the 4 trim flags so the system prompt
    excludes Bash/Glob/etc. tool descriptions and skips CLAUDE.md
    auto-discovery."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
    ))
    assert captured, "subprocess.run should be invoked"
    cmd = captured[0]
    assert "--tools" in cmd
    assert cmd[cmd.index("--tools") + 1] == "Read Write Edit"
    assert "--setting-sources" in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert "--disable-slash-commands" in cmd
    assert "--exclude-dynamic-system-prompt-sections" in cmd


def test_claude_complete_text_includes_trim_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete_text() (F22 playbook calls) carries the same trim."""
    from Tooling.llm import claude_cli

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.complete_text(prompt="hi")
    assert captured
    cmd = captured[0]
    assert "--tools" in cmd
    assert "--disable-slash-commands" in cmd
    assert "--exclude-dynamic-system-prompt-sections" in cmd
    assert "--setting-sources" in cmd


def test_claude_tools_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASTERISM_CLAUDE_TOOLS env replaces the default tool list — for
    rare flows that legitimately need extra surface."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    monkeypatch.setenv("ASTERISM_CLAUDE_TOOLS", "Read Bash")
    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
    ))
    cmd = captured[0]
    assert cmd[cmd.index("--tools") + 1] == "Read Bash"


# ---------------------------------------------------------------------
# F33 — same-session Builder retry: --session-id (cold) / --resume
# (retry) / stale-session sentinel rc=125
# ---------------------------------------------------------------------

def test_claude_spawn_cold_with_session_id_uses_session_id_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First Builder attempt: caller mints a uuid, passes session_id
    + is_retry=False. spawn must use --session-id <uuid> (not --resume)
    and persist the session to disk (no --no-session-persistence)."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
        session_id="abc123",
        is_retry=False,
    ))
    cmd = captured[0]
    assert "--session-id" in cmd
    assert cmd[cmd.index("--session-id") + 1] == "abc123"
    assert "--resume" not in cmd
    # Session must persist for the future retry to find it
    assert "--no-session-persistence" not in cmd


def test_claude_spawn_retry_uses_resume_and_short_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry path: --resume <uuid> + a prompt that points the agent
    at RETRY_NOTE.md (the prior turn's reasoning lives in the session
    memory; we only inject the new lake error)."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
        session_id="abc123",
        is_retry=True,
    ))
    cmd = captured[0]
    assert "--resume" in cmd
    assert cmd[cmd.index("--resume") + 1] == "abc123"
    assert "--session-id" not in cmd
    # Prompt should reference RETRY_NOTE.md, not Context.md
    prompt_idx = cmd.index("-p") + 1
    assert "RETRY_NOTE.md" in cmd[prompt_idx]


def test_claude_spawn_no_session_id_keeps_legacy_ephemeral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward / Verify and OpenAI fallback don't pass session_id;
    behavior must stay unchanged (--no-session-persistence retained)."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
    ))
    cmd = captured[0]
    assert "--session-id" not in cmd
    assert "--resume" not in cmd
    assert "--no-session-persistence" in cmd


def test_claude_spawn_stale_session_returns_rc_125(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `--resume <uuid>` finds no on-disk session, claude prints
    'No conversation found with session ID: ...' to stderr and returns
    rc=1. spawn must surface this as RC_STALE_SESSION (=125) so the
    caller (pipeline.run_builder) can clear the DB id and retry cold."""
    import subprocess as _sub
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    monkeypatch.setattr(claude_cli.shutil, "which",
                        lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=1, stdout="",
            stderr="No conversation found with session ID: abc123",
        ))
    p = claude_cli.ClaudeCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
        session_id="abc123",
        is_retry=True,
    ))
    assert rc == claude_cli.RC_STALE_SESSION
    assert claude_cli.RC_STALE_SESSION == 125


def test_claude_spawn_stale_marker_only_on_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stale-session sentinel is meaningful only on --resume.
    A --session-id call that fails for any reason should pass through
    its real rc — we don't want to misclassify an unrelated rc=1
    as 'stale session'."""
    import subprocess as _sub
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    monkeypatch.setattr(claude_cli.shutil, "which",
                        lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=1, stdout="",
            stderr="No conversation found with session ID: abc123",
        ))
    p = claude_cli.ClaudeCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
        session_id="abc123",
        is_retry=False,  # cold path
    ))
    # Cold path can't be a stale session — pass through real rc
    assert rc == 1
