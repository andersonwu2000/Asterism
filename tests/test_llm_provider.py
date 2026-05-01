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


def test_claude_spawn_retry_inlines_error_into_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry path: --resume <uuid> + the lake error inlined directly
    in the -p prompt (no separate RETRY_NOTE.md file → agent sees
    the error immediately, no Read tool round-trip). Prior turn's
    reasoning lives in the session memory."""
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
        retry_context="error: Type mismatch on `ZMod.val_natCast`",
    ))
    cmd = captured[0]
    assert "--resume" in cmd
    assert cmd[cmd.index("--resume") + 1] == "abc123"
    assert "--session-id" not in cmd
    # Lake error embedded in -p prompt; no RETRY_NOTE.md reference
    prompt_idx = cmd.index("-p") + 1
    assert "Type mismatch on `ZMod.val_natCast`" in cmd[prompt_idx]
    assert "RETRY_NOTE" not in cmd[prompt_idx]


def test_claude_spawn_retry_handles_missing_retry_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If retry_context is None (e.g. the prior dead_attempt had an
    empty failure_detail), the prompt still emits a fallback marker
    so the agent isn't shown an empty code block."""
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
        retry_context=None,
    ))
    prompt_idx = captured[0].index("-p") + 1
    assert "lake error not captured" in captured[0][prompt_idx]


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


# ---------------------------------------------------------------------
# F38 — Gemini CLI provider (registry + quota-exhausted detection)
# ---------------------------------------------------------------------

def test_get_provider_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTERISM_LLM_PROVIDER", "gemini")
    p = llm.get_provider()
    assert p.__class__.__name__ == "GeminiCliProvider"


def _capture_gemini_cmd(monkeypatch: pytest.MonkeyPatch,
                        *, returncode: int = 0,
                        stdout: str = "", stderr: str = "") -> list:
    """Patch gemini_cli.subprocess.run to record argv and return a
    canned CompletedProcess. Pretends gemini is on PATH."""
    import subprocess as _sub
    from Tooling.llm import gemini_cli
    captured: list = []

    def _fake_run(cmd, *a, **kw):
        captured.append(cmd)
        return _sub.CompletedProcess(args=cmd, returncode=returncode,
                                     stdout=stdout, stderr=stderr)
    monkeypatch.setattr(gemini_cli.shutil, "which",
                        lambda _: "/fake/gemini")
    monkeypatch.setattr(gemini_cli.subprocess, "run", _fake_run)
    return captured


def test_gemini_spawn_returns_127_when_cli_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path
    from Tooling.llm import gemini_cli
    monkeypatch.setattr(gemini_cli.shutil, "which", lambda _: None)
    p = gemini_cli.GeminiCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
    ))
    assert rc == 127


def test_gemini_spawn_uses_default_model_and_shared_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """Default model is gemini-2.5-flash; shared flags --yolo /
    --skip-trust / --output-format text are always present."""
    from Tooling.llm import gemini_cli
    monkeypatch.delenv("ASTERISM_GEMINI_MODEL", raising=False)
    captured = _capture_gemini_cmd(monkeypatch, returncode=0,
                                   stdout="ok")
    # Pre-create an artifact so spawn doesn't tag it as quota-exhausted
    (tmp_path / "PROPOSAL.md").write_text("done", encoding="utf-8")
    p = gemini_cli.GeminiCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path,
        attempts_dir=tmp_path,
        timeout_sec=60,
    ))
    cmd = captured[0]
    # cmd[0] is the resolved executable path (handles npm bash-shim vs
    # .cmd disambiguation on Windows). Just check it ends with `gemini`
    # so the assertion is platform-insensitive.
    assert cmd[0].endswith("gemini") or cmd[0].endswith("gemini.cmd")
    assert "-m" in cmd
    assert cmd[cmd.index("-m") + 1] == "gemini-2.5-flash"
    assert "--yolo" in cmd
    assert "--skip-trust" in cmd
    assert "--output-format" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "text"


def test_gemini_spawn_model_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    from Tooling.llm import gemini_cli
    monkeypatch.setenv("ASTERISM_GEMINI_MODEL", "gemini-2.5-pro")
    captured = _capture_gemini_cmd(monkeypatch, returncode=0)
    (tmp_path / "PROPOSAL.md").write_text("x", encoding="utf-8")
    p = gemini_cli.GeminiCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path,
        timeout_sec=60,
    ))
    cmd = captured[0]
    assert cmd[cmd.index("-m") + 1] == "gemini-2.5-pro"


def test_gemini_spawn_rc0_with_output_passes_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """rc=0 + agent wrote a .lean file → real success; pass through."""
    from Tooling.llm import gemini_cli
    _capture_gemini_cmd(monkeypatch, returncode=0, stdout="done")
    (tmp_path / "patch.lean").write_text("ok", encoding="utf-8")
    p = gemini_cli.GeminiCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    assert rc == 0


def test_gemini_spawn_rc0_no_output_with_quota_marker_returns_126(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """rc=0 + nothing written + quota phrase in captured output →
    surface as RC_QUOTA_EXHAUSTED so caller can back off."""
    from Tooling.llm import gemini_cli
    _capture_gemini_cmd(
        monkeypatch, returncode=0, stdout="",
        stderr="Attempt 5 failed: You have exhausted your capacity",
    )
    p = gemini_cli.GeminiCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    assert rc == gemini_cli.RC_QUOTA_EXHAUSTED == 126


def test_gemini_spawn_rc0_no_output_no_marker_returns_generic_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """rc=0 + nothing written + no quota phrase → still a failure
    (agent ran but produced nothing) but not classified as quota."""
    from Tooling.llm import gemini_cli
    _capture_gemini_cmd(monkeypatch, returncode=0, stdout="ok",
                        stderr="")
    p = gemini_cli.GeminiCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    assert rc == 1


def test_gemini_spawn_excludes_pre_existing_context_md(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """Context.md is framework-written before spawn — its presence
    must NOT count as agent output. Otherwise quota detection would
    misfire as success on every quota-exhausted call."""
    from Tooling.llm import gemini_cli
    _capture_gemini_cmd(monkeypatch, returncode=0, stdout="",
                        stderr="status: 429")
    (tmp_path / "Context.md").write_text("ctx", encoding="utf-8")
    p = gemini_cli.GeminiCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    assert rc == gemini_cli.RC_QUOTA_EXHAUSTED


def test_gemini_spawn_timeout_returns_124(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    import subprocess as _sub
    from Tooling.llm import gemini_cli
    monkeypatch.setattr(gemini_cli.shutil, "which",
                        lambda _: "/fake/gemini")

    def _timeout(*a, **kw):
        raise _sub.TimeoutExpired(cmd=a[0], timeout=1)
    monkeypatch.setattr(gemini_cli.subprocess, "run", _timeout)
    p = gemini_cli.GeminiCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=1,
    ))
    assert rc == 124


def test_gemini_complete_text_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import gemini_cli
    _capture_gemini_cmd(monkeypatch, returncode=0,
                        stdout="  hi\n  ", stderr="")
    p = gemini_cli.GeminiCliProvider()
    assert p.complete_text(prompt="x") == "hi"


def test_gemini_complete_text_returns_none_on_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty stdout + quota phrase → None (caller treats as
    'unavailable, skip')."""
    from Tooling.llm import gemini_cli
    _capture_gemini_cmd(
        monkeypatch, returncode=0, stdout="",
        stderr="Attempt 3 failed: Too Many Requests",
    )
    p = gemini_cli.GeminiCliProvider()
    assert p.complete_text(prompt="x") is None


def test_gemini_complete_text_returns_none_on_nonzero_rc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import gemini_cli
    _capture_gemini_cmd(monkeypatch, returncode=2, stdout="oops")
    p = gemini_cli.GeminiCliProvider()
    assert p.complete_text(prompt="x") is None


def test_gemini_complete_text_returns_none_when_cli_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import gemini_cli
    monkeypatch.setattr(gemini_cli.shutil, "which", lambda _: None)
    p = gemini_cli.GeminiCliProvider()
    assert p.complete_text(prompt="x") is None


def test_gemini_resolve_prefers_cmd_extension_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """npm installs `gemini` (no-extension bash shim) and `gemini.cmd`
    side-by-side on Windows. shutil.which without extension may return
    the shim, which CreateProcess (subprocess.run) cannot launch
    (WinError 2). Resolver must probe `.cmd` first on win32."""
    from Tooling.llm import gemini_cli
    monkeypatch.setattr(gemini_cli.sys, "platform", "win32")
    seen: list = []

    def fake_which(name):
        seen.append(name)
        if name == "gemini.cmd":
            return r"C:\npm\gemini.cmd"
        if name == "gemini":
            return r"C:\npm\gemini"
        return None

    monkeypatch.setattr(gemini_cli.shutil, "which", fake_which)
    assert gemini_cli._resolve_gemini_executable() == r"C:\npm\gemini.cmd"
    # Resolver must have probed gemini.cmd BEFORE the no-extension shim
    assert seen[0] == "gemini.cmd"


def test_gemini_resolve_uses_plain_name_on_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import gemini_cli
    monkeypatch.setattr(gemini_cli.sys, "platform", "linux")
    monkeypatch.setattr(gemini_cli.shutil, "which",
                        lambda n: "/usr/bin/gemini" if n == "gemini" else None)
    assert gemini_cli._resolve_gemini_executable() == "/usr/bin/gemini"


def test_gemini_spawn_returns_127_on_filenotfounderror(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """If subprocess.run raises FileNotFoundError (e.g. resolved path
    was deleted between resolve and spawn), provider must return 127
    instead of letting the exception escape — otherwise the dispatcher
    catches it as a generic worker exception and re-dispatches in a
    loop without incrementing goal attempts."""
    import subprocess as _sub
    from Tooling.llm import gemini_cli
    monkeypatch.setattr(gemini_cli.shutil, "which", lambda _: "/fake/gemini")

    def _raise_fnf(*a, **kw):
        raise FileNotFoundError(2, "stale path")
    monkeypatch.setattr(gemini_cli.subprocess, "run", _raise_fnf)
    p = gemini_cli.GeminiCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    assert rc == 127


# ---------------------------------------------------------------------
# F39 — per-pipeline provider/model selection (kind-aware resolution)
# ---------------------------------------------------------------------

def test_get_provider_kind_specific_overrides_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASTERISM_BUILDER_PROVIDER takes precedence over LLM_PROVIDER
    when caller passes kind='builder'."""
    monkeypatch.setenv("ASTERISM_LLM_PROVIDER", "claude")
    monkeypatch.setenv("ASTERISM_BUILDER_PROVIDER", "gemini")
    p = llm.get_provider(kind="builder")
    assert p.__class__.__name__ == "GeminiCliProvider"


def test_get_provider_kind_specific_unset_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ASTERISM_BUILDER_PROVIDER not set, kind='builder' falls back
    to ASTERISM_LLM_PROVIDER (then 'claude' default)."""
    monkeypatch.delenv("ASTERISM_BUILDER_PROVIDER", raising=False)
    monkeypatch.setenv("ASTERISM_LLM_PROVIDER", "openai")
    p = llm.get_provider(kind="builder")
    assert p.__class__.__name__ == "OpenAIProvider"


def test_get_provider_kind_specific_with_no_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASTERISM_BUILDER_PROVIDER", raising=False)
    monkeypatch.delenv("ASTERISM_LLM_PROVIDER", raising=False)
    p = llm.get_provider(kind="builder")
    assert p.__class__.__name__ == "ClaudeCliProvider"


def test_get_provider_builder_and_backward_can_differ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hallmark F39 use case — Builder uses cheap LLM, Backward uses
    strong LLM, in the same daemon run."""
    monkeypatch.setenv("ASTERISM_BUILDER_PROVIDER", "gemini")
    monkeypatch.setenv("ASTERISM_BACKWARD_PROVIDER", "claude")
    pb = llm.get_provider(kind="builder")
    pk = llm.get_provider(kind="backward")
    assert pb.__class__.__name__ == "GeminiCliProvider"
    assert pk.__class__.__name__ == "ClaudeCliProvider"


def test_claude_resolve_model_kind_specific_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import claude_cli
    monkeypatch.setenv("ASTERISM_BUILDER_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    assert claude_cli._resolve_model("builder") == "claude-haiku-4-5"
    # Different kind falls through to legacy AGENT_MODEL
    assert claude_cli._resolve_model("backward") == "claude-sonnet-4-6"


def test_claude_resolve_model_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import claude_cli
    monkeypatch.delenv("ASTERISM_BUILDER_MODEL", raising=False)
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-opus-4-7")
    assert claude_cli._resolve_model("builder") == "claude-opus-4-7"


def test_claude_resolve_model_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import claude_cli
    monkeypatch.delenv("ASTERISM_BUILDER_MODEL", raising=False)
    monkeypatch.delenv("ASTERISM_AGENT_MODEL", raising=False)
    assert claude_cli._resolve_model("builder") == claude_cli.DEFAULT_MODEL


def test_gemini_resolve_model_kind_specific_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import gemini_cli
    monkeypatch.setenv("ASTERISM_BUILDER_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("ASTERISM_GEMINI_MODEL", "gemini-2.5-pro")
    assert gemini_cli._resolve_model("builder") == "gemini-2.5-flash"
    assert gemini_cli._resolve_model("backward") == "gemini-2.5-pro"


def test_openai_resolve_model_kind_specific_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import openai_api
    monkeypatch.setenv("ASTERISM_BUILDER_MODEL", "qwen3-coder-30b")
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "qwen3-instruct-7b")
    assert openai_api._resolve_model("builder") == "qwen3-coder-30b"
    assert openai_api._resolve_model("backward") == "qwen3-instruct-7b"


def test_openai_resolve_model_returns_none_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import openai_api
    monkeypatch.delenv("ASTERISM_BUILDER_MODEL", raising=False)
    monkeypatch.delenv("ASTERISM_LLM_MODEL", raising=False)
    assert openai_api._resolve_model("builder") is None


def test_complete_text_uses_builder_kind_for_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F22 auxiliary calls (idiom extract / curate) inherit the
    Builder tier — explicit kind='builder' inside complete_text so a
    user who set ASTERISM_BUILDER_MODEL=cheap-llm gets that, not the
    Backward / agent default."""
    import subprocess as _sub
    from Tooling.llm import claude_cli
    monkeypatch.setenv("ASTERISM_BUILDER_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    captured: list = []

    def _fake_run(cmd, *a, **kw):
        captured.append(cmd)
        return _sub.CompletedProcess(args=cmd, returncode=0,
                                     stdout="ok", stderr="")
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(claude_cli.subprocess, "run", _fake_run)
    p = claude_cli.ClaudeCliProvider()
    p.complete_text(prompt="x")
    cmd = captured[0]
    # complete_text must have used the Builder model (haiku), not the
    # Sonnet legacy default.
    assert cmd[cmd.index("--model") + 1] == "claude-haiku-4-5"


def test_dispatcher_threshold_reads_builder_model_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F39 — threshold gates Builder iteration count, so it must
    detect 'haiku' from the Builder-specific override even when
    ASTERISM_AGENT_MODEL is sonnet."""
    from Tooling import dispatcher as _d
    monkeypatch.setenv("ASTERISM_BUILDER_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    assert _d._model_aware_thresholds() == _d._WEAK_DEFAULTS


def test_dispatcher_threshold_falls_back_to_agent_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling import dispatcher as _d
    monkeypatch.delenv("ASTERISM_BUILDER_MODEL", raising=False)
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-haiku-4-5")
    assert _d._model_aware_thresholds() == _d._WEAK_DEFAULTS
