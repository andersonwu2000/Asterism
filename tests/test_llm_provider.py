"""LLM provider registry: dispatch by env, error on unknown, default Claude."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling import config, llm


@pytest.fixture(autouse=True)
def _isolate_workspace_config(tmp_path: Path,
                               monkeypatch: pytest.MonkeyPatch):
    """Tests in this module exercise provider / model resolution. The
    real workspace's Asterism.yaml hard-codes claude-sonnet-4-6 for
    builder + backward, which would dominate the env-only tier the
    tests intend to verify. chdir into a clean tmp dir + reset the
    config cache so `config.load()` finds no yaml and the resolution
    chain falls through to env / legacy / default as the test
    expects."""
    monkeypatch.chdir(tmp_path)
    config._reset_cache()
    yield
    config._reset_cache()


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

class _FakePopen:
    """Stand-in for subprocess.Popen in claude_cli tests. Supports
    claude_cli's spawn-loop surface (communicate / poll / kill /
    terminate / wait) AND the context-manager protocol that the stdlib
    `subprocess.run` enters internally (`with Popen(...) as proc:`).
    Tests that monkeypatch `subprocess.Popen` globally need both.

    Watchdog-eligible spawns use the stream-json + reader-thread path
    (added 2026-05-10): the dispatch loop calls `proc.wait(timeout)`
    and drains `.stdout` / `.stderr` line-by-line via reader threads.
    `_FakePopen.stdout` / `.stderr` are StringIO so the reader threads
    see EOF immediately and exit cleanly (no real stream events for
    parser; tests don't assert on parser state, just on cmd shape).
    `wait()` sets returncode so dispatch proceeds with rc."""
    def __init__(self, *, rc: int = 0, stdout: str = "ok",
                 stderr: str = "") -> None:
        import io
        self._rc = rc
        self._stdout = stdout
        self._stderr = stderr
        # Pipe-like .stdout / .stderr for the reader-thread path.
        # Pre-populate with the same text communicate() returns so
        # both paths see the same content.
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.returncode: int | None = None
        # subprocess.run reads .args off the Popen instance to attach
        # to CompletedProcess; without it, complete_text path crashes.
        self.args: list = []

    def communicate(self, input=None, timeout=None):
        # `input` only relevant for subprocess.run pipeline (via
        # `with Popen(...) as p: p.communicate(input, timeout=...)`).
        # Ignored for spawn path which calls communicate(timeout=...).
        self.returncode = self._rc
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        # Watchdog-eligible path: dispatch calls wait() instead of
        # communicate(). Set returncode here so the dispatch loop
        # sees a successful spawn.
        if self.returncode is None:
            self.returncode = self._rc
        return self.returncode

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture_cmd(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch claude_cli.subprocess.Popen to capture the cmd argv and
    return a successful fake Popen instance. claude_cli's spawn was
    refactored to Popen + communicate(timeout=...) for the watchdog;
    callers that mocked subprocess.run won't trigger anymore."""
    from Tooling.llm import claude_cli
    captured: list = []

    def _fake_popen(cmd, *a, **kw):
        captured.append(cmd)
        return _FakePopen(rc=0, stdout="ok")
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(claude_cli.subprocess, "Popen", _fake_popen)
    return captured


def _capture_call(monkeypatch: pytest.MonkeyPatch, *,
                  module_name: str = "claude_cli") -> list:
    """Capture both cmd argv AND kwargs from subprocess patches.
    claude_cli uses Popen now (for watchdog support); gemini_cli still
    uses subprocess.run, so the helper branches by module."""
    import subprocess as _sub
    if module_name == "claude_cli":
        from Tooling.llm import claude_cli as mod
        calls: list = []

        def _fake_popen(cmd, *a, **kw):
            calls.append({"cmd": cmd, "kwargs": kw})
            return _FakePopen(rc=0, stdout="ok")
        monkeypatch.setattr(mod.shutil, "which", lambda _: "/fake/exe")
        monkeypatch.setattr(mod.subprocess, "Popen", _fake_popen)
        return calls
    elif module_name == "gemini_cli":
        from Tooling.llm import gemini_cli as mod
        calls: list = []

        def _fake_run(cmd, *a, **kw):
            calls.append({"cmd": cmd, "kwargs": kw})
            return _sub.CompletedProcess(args=cmd, returncode=0,
                                         stdout="ok", stderr="")
        monkeypatch.setattr(mod.shutil, "which", lambda _: "/fake/exe")
        monkeypatch.setattr(mod.subprocess, "run", _fake_run)
        return calls
    else:
        raise ValueError(module_name)


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
    # F50 — Grep + Bash were added; existing Read/Write/Edit kept
    tools_val = cmd[cmd.index("--tools") + 1]
    for t in ("Read", "Write", "Edit", "Grep", "Bash"):
        assert t in tools_val.split(), f"missing tool {t} in {tools_val!r}"
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


def test_claude_spawn_postmortem_uses_resume_with_loaded_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """F55 — postmortem call: --resume <uuid> + the prompt body loaded
    verbatim from prompt_path (NOT the cold-path framework wrapper).
    Used after a main-spawn timeout to extract a state + blocker note
    via the killed agent's still-intact session memory."""
    from Tooling import llm
    from Tooling.llm import claude_cli

    prompt_file = tmp_path / "backward_postmortem.md"
    prompt_file.write_text(
        "Write _progress.md with state + blocker. Exit.",
        encoding="utf-8")

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=prompt_file,
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=120,
        session_id="killed-session-uuid",
        is_postmortem=True,
    ))
    cmd = captured[0]
    # Resume the killed session, NOT a fresh one
    assert "--resume" in cmd
    assert cmd[cmd.index("--resume") + 1] == "killed-session-uuid"
    assert "--session-id" not in cmd
    # Prompt body is the postmortem template verbatim, no cold-path
    # framework wrapper ("You are running a {kind} task...")
    p_idx = cmd.index("-p")
    prompt_payload = cmd[p_idx + 1]
    assert "Write _progress.md" in prompt_payload
    assert "INSTRUCTIONS" not in prompt_payload  # no cold wrapper
    assert "Read context at" not in prompt_payload  # no cold wrapper


def test_claude_spawn_postmortem_takes_priority_over_retry_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """If both is_postmortem and is_retry are set, postmortem wins —
    the inline lake-error retry prompt is NOT constructed; the
    postmortem template is loaded verbatim. (The pipeline never
    actually sets both, but defense-in-depth.)"""
    from Tooling import llm
    from Tooling.llm import claude_cli

    prompt_file = tmp_path / "p.md"
    prompt_file.write_text("postmortem-only template", encoding="utf-8")

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=prompt_file,
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=120,
        session_id="sid-1",
        is_retry=True,
        retry_context="error: lake failed",
        is_postmortem=True,
    ))
    cmd = captured[0]
    p_idx = cmd.index("-p")
    prompt_payload = cmd[p_idx + 1]
    assert "postmortem-only template" in prompt_payload
    assert "Previous attempt failed lake build" not in prompt_payload


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


# ---------------------------------------------------------------------
# F51 — retry prompt enrichment when stderr contains "Unknown constant"
# ---------------------------------------------------------------------

def test_extract_unknown_constants_basic() -> None:
    """Parse names from a representative lake error line."""
    from Tooling.llm import claude_cli
    stderr = (
        "✖ [8369/8369] Building Problems.foo.proofs.L_x (17s)\n"
        "error: Problems/foo/proofs/L_x.lean:9:18: "
        "Unknown constant `Multiplicative.toAdd_zpow`"
    )
    assert claude_cli._extract_unknown_constants(stderr) == [
        "Multiplicative.toAdd_zpow"]


def test_extract_unknown_constants_handles_lowercase_and_identifier() -> None:
    """Both 'Unknown constant' and 'unknown identifier' phrasings match."""
    from Tooling.llm import claude_cli
    stderr = (
        "error: ... unknown identifier `Foo.bar`\n"
        "error: ... Unknown constant `Baz.qux`\n"
    )
    assert claude_cli._extract_unknown_constants(stderr) == [
        "Foo.bar", "Baz.qux"]


def test_extract_unknown_constants_dedup_and_cap() -> None:
    """Duplicates collapse; total capped at MAX_HINTED_UNKNOWNS so the
    retry prompt size stays bounded even when many distinct names fail."""
    from Tooling.llm import claude_cli
    stderr = "\n".join(
        f"error: Unknown constant `Foo.bar_{i}`" for i in range(10)
    ) + "\nerror: Unknown constant `Foo.bar_0`"  # duplicate
    out = claude_cli._extract_unknown_constants(stderr)
    assert len(out) == claude_cli._MAX_HINTED_UNKNOWNS
    assert out == ["Foo.bar_0", "Foo.bar_1", "Foo.bar_2"]


def test_extract_unknown_constants_no_match() -> None:
    """Errors that aren't unknown-constant (timeout, type mismatch, ...)
    yield empty list — no hint should be appended for those."""
    from Tooling.llm import claude_cli
    stderr = (
        "error: type mismatch\n"
        "error: typeclass instance problem is stuck\n"
    )
    assert claude_cli._extract_unknown_constants(stderr) == []
    assert claude_cli._extract_unknown_constants("") == []


def test_retry_hint_empty_when_no_names() -> None:
    """No unknown constants → empty string. Caller concatenates this
    into the prompt; an empty hint must not add a trailing blank line."""
    from Tooling.llm import claude_cli
    assert claude_cli._retry_hint_for_unknowns([]) == ""


def test_retry_hint_uses_parent_path_for_loogle_query() -> None:
    """For dotted names the Loogle query strips the last segment so
    the agent searches for related lemmas in the parent namespace
    (e.g. `Multiplicative.toAdd_zpow` → query `Multiplicative.toAdd _`)."""
    from Tooling.llm import claude_cli
    hint = claude_cli._retry_hint_for_unknowns(["Multiplicative.toAdd_zpow"])
    assert "`Multiplicative.toAdd_zpow` not found" in hint
    assert "python -m Tooling.loogle 'Multiplicative.toAdd _'" in hint


def test_retry_hint_handles_single_segment_name() -> None:
    """A bare identifier (no dot) Loogles itself rather than empty."""
    from Tooling.llm import claude_cli
    hint = claude_cli._retry_hint_for_unknowns(["wilson_lemma"])
    assert "python -m Tooling.loogle 'wilson_lemma _'" in hint


def test_retry_hint_size_bounded(
) -> None:
    """Even with the cap of names hit, the hint stays small (< 600
    chars) — that's the whole point of capping at MAX_HINTED_UNKNOWNS.
    Guards against future regressions that bloat per-name overhead."""
    from Tooling.llm import claude_cli
    names = [f"Foo.bar_long_name_{i}" for i in range(claude_cli._MAX_HINTED_UNKNOWNS)]
    hint = claude_cli._retry_hint_for_unknowns(names)
    assert len(hint) < 600


def test_spawn_retry_appends_unknown_constant_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: when retry_context contains 'Unknown constant `X`',
    the spawned -p prompt includes the F51 verification hint inline."""
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
        retry_context=(
            "error: Problems/foo.lean:9:18: Unknown constant "
            "`Multiplicative.toAdd_zpow`"
        ),
    ))
    prompt = captured[0][captured[0].index("-p") + 1]
    assert "Multiplicative.toAdd_zpow" in prompt  # error preserved
    assert "verify the name in Mathlib" in prompt  # F51 hint preamble
    assert "python -m Tooling.loogle" in prompt    # actionable command


def test_spawn_retry_no_unknown_constant_hint_for_other_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stderr without `Unknown constant` shouldn't trigger the F51
    Loogle-name verification hint. The generic F53/3b pattern table
    may still fire — that's a separate diagnosis covered below."""
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
        retry_context="error: typeclass instance problem is stuck",
    ))
    prompt = captured[0][captured[0].index("-p") + 1]
    assert "typeclass instance problem is stuck" in prompt
    # F51-specific (unknown-constant) hint absent
    assert "verify the name in Mathlib" not in prompt
    assert "python -m Tooling.loogle" not in prompt


# ---------------------------------------------------------------------
# F53/3b — generic stderr → diagnostic-hint table for the retry prompt
# ---------------------------------------------------------------------

@pytest.mark.parametrize("stderr,must_appear", [
    # expected token (notation/scope/unicode) — Sonnet's recurring
    # pain point on inner-product / norm goals.
    ("error: L_x.lean:8:48: expected token",
     "expected token"),
    # typeclass stuck — F41-class type-drift symptom
    ("error: typeclass instance problem is stuck\n  Norm ?m.1",
     "typeclass instance problem is stuck"),
    # autoImplicit unknown identifier
    ("error: L_x.lean:7:22: Function expected at\n"
     "Hint: The identifier `P` is unknown",
     "Function expected at … identifier unknown"),
    # tactic made no progress
    ("error: L_x.lean:24:42: `ring_nf` made no progress on the goal",
     "didn't progress on the current goal"),
    # leftover sorry in patch
    ("warning: Problems/p/proofs/_strategy_s5.lean:6:8: "
     "declaration uses `sorry`",
     "strategy patch (`_strategy_s<id>.lean`) still has"),
])
def test_pattern_hints_emit_for_known_stderr(
    stderr: str, must_appear: str,
) -> None:
    """Each known stderr family yields a non-empty, distinct hint
    so the resumed agent has a pointed clue instead of guessing."""
    from Tooling.llm import claude_cli
    out = claude_cli._retry_hint_for_patterns(stderr)
    assert "Retry hints based on the lake error above" in out
    assert must_appear in out


def test_pattern_hints_empty_for_unknown_stderr() -> None:
    """An error message that doesn't match any known family yields
    no hint (empty string), so the retry prompt isn't padded with
    irrelevant noise."""
    from Tooling.llm import claude_cli
    out = claude_cli._retry_hint_for_patterns(
        "error: stack overflow during elaboration")
    assert out == ""


def test_sorry_hint_scoped_to_patch_not_substubs() -> None:
    """P1-#9 (c): the leftover-sorry hint must NOT fire on standalone
    `new_<sub>.lean` warnings (those legitimately carry `:= by sorry`
    until the sub-goal is proved). Only fires when the warning's path
    points at `_strategy_s<id>.lean` or `patch.lean`.
    """
    from Tooling.llm import claude_cli
    sub_warning = (
        "warning: Problems/p/proofs/L_s5_sub_2.lean:6:8: "
        "declaration uses `sorry`"
    )
    assert claude_cli._retry_hint_for_patterns(sub_warning) == ""
    patch_warning = (
        "warning: Problems/p/proofs/_strategy_s5.lean:6:8: "
        "declaration uses `sorry`"
    )
    assert "strategy patch (`_strategy_s<id>.lean`) still has" in (
        claude_cli._retry_hint_for_patterns(patch_warning))


def test_manifest_hint_placeholder_not_appended_when_empty() -> None:
    """When a Manifest hint is just `Foo.bar` with no commentary, the
    rendered Mathlib-lemmas bullet must NOT carry a spurious
    `(manifest hint)` placeholder — was previously a fallback string,
    now silently omitted."""
    from Tooling.manifest import Manifest
    # Stub lemma_lookup to "find" the name with a fake signature
    from unittest.mock import patch as _patch
    mfst = Manifest(problem="p", statement="T",
                    mathlib_hints=["Nat.factorial"])
    fake_info = type("LI", (), {
        "name": "Nat.factorial", "signature": "ℕ → ℕ", "found": True,
    })()
    from Tooling import context as _ctx
    with _patch.object(_ctx.lemma_lookup, "lookup_batch",
                       return_value={"Nat.factorial": fake_info}):
        section = _ctx._section_mathlib_hints_stable(mfst,
                                             workspace=Path("/tmp"))
    body = "\n".join(section)
    assert "Nat.factorial" in body
    assert "ℕ → ℕ" in body
    assert "(manifest hint)" not in body  # no placeholder


def test_manifest_hint_keeps_real_commentary() -> None:
    """When a Manifest hint DOES carry author commentary
    (e.g. `Foo.bar — explanation`), preserve it next to the resolved
    signature."""
    from Tooling.manifest import Manifest
    from unittest.mock import patch as _patch
    mfst = Manifest(problem="p", statement="T",
                    mathlib_hints=["Nat.factorial — n! is positive"])
    fake_info = type("LI", (), {
        "name": "Nat.factorial", "signature": "ℕ → ℕ", "found": True,
    })()
    from Tooling import context as _ctx
    with _patch.object(_ctx.lemma_lookup, "lookup_batch",
                       return_value={"Nat.factorial": fake_info}):
        section = _ctx._section_mathlib_hints_stable(mfst,
                                             workspace=Path("/tmp"))
    body = "\n".join(section)
    assert "n! is positive" in body


def test_pattern_hints_capped_at_two() -> None:
    """Even when stderr matches 3+ patterns, only the first two are
    emitted to keep prompt growth bounded — matching errors usually
    share a root cause."""
    from Tooling.llm import claude_cli
    stderr = (
        "error: expected token\n"
        "error: typeclass instance problem is stuck\n"
        "error: `simp` made no progress on the goal\n"
        "warning: declaration uses `sorry`\n"
    )
    out = claude_cli._retry_hint_for_patterns(stderr)
    # Two `- ` bullet lines max
    assert out.count("\n- ") == 2


def test_spawn_retry_appends_pattern_hint_for_typeclass_stuck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: typeclass-stuck stderr → 3b hint inlined into -p
    prompt, no F51 Loogle hint (no unknown-constant cited)."""
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
        retry_context=(
            "error: L_s139_sub_3.lean:7:21: typeclass instance "
            "problem is stuck\n  Norm ?m.1"
        ),
    ))
    prompt = captured[0][captured[0].index("-p") + 1]
    assert "Retry hints based on the lake error above" in prompt
    assert "Lean can't figure out a type argument" in prompt
    # F51 unknown-constant hint absent because no `Unknown constant ...`
    assert "verify the name in Mathlib" not in prompt


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
    rc=1. spawn must surface this as SpawnRC.STALE_SESSION (=125) so
    the caller (pipeline.run_builder) can clear the DB id and retry
    cold."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli
    from Tooling.llm.base import SpawnRC

    monkeypatch.setattr(claude_cli.shutil, "which",
                        lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(
            rc=1, stdout="",
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
    assert rc == SpawnRC.STALE_SESSION
    assert int(SpawnRC.STALE_SESSION) == 125


def test_claude_spawn_quota_exhausted_returns_rc_126(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Anthropic quota is exhausted, claude.exe returns rc=1 with
    'You've hit your limit · resets …' on STDOUT (not stderr). spawn
    must reclassify this as SpawnRC.QUOTA_EXHAUSTED (=126) so the
    dispatcher's infra-reason cooldown path applies; otherwise budget
    is consumed retrying a deterministically-failing spawn until
    CONSEC_SPAWN_FAIL_LIMIT bails the daemon."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli
    from Tooling.llm.base import SpawnRC

    monkeypatch.setattr(claude_cli.shutil, "which",
                        lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(
            rc=1,
            stdout="You've hit your limit · resets May 11, 8am (Asia/Taipei)",
            stderr="",
        ))
    p = claude_cli.ClaudeCliProvider()
    rc = p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
    ))
    assert rc == SpawnRC.QUOTA_EXHAUSTED
    assert int(SpawnRC.QUOTA_EXHAUSTED) == 126


def test_claude_spawn_stale_marker_only_on_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stale-session sentinel is meaningful only on --resume.
    A --session-id call that fails for any reason should pass through
    its real rc — we don't want to misclassify an unrelated rc=1
    as 'stale session'."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    monkeypatch.setattr(claude_cli.shutil, "which",
                        lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(
            rc=1, stdout="",
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
    assert gemini_cli.resolve_gemini_executable() == r"C:\npm\gemini.cmd"
    # Resolver must have probed gemini.cmd BEFORE the no-extension shim
    assert seen[0] == "gemini.cmd"


def test_gemini_resolve_uses_plain_name_on_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import gemini_cli
    monkeypatch.setattr(gemini_cli.sys, "platform", "linux")
    monkeypatch.setattr(gemini_cli.shutil, "which",
                        lambda n: "/usr/bin/gemini" if n == "gemini" else None)
    assert gemini_cli.resolve_gemini_executable() == "/usr/bin/gemini"


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
    assert claude_cli.resolve_model("builder") == "claude-haiku-4-5"
    # Different kind falls through to legacy AGENT_MODEL
    assert claude_cli.resolve_model("backward") == "claude-sonnet-4-6"


def test_claude_resolve_model_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import claude_cli
    monkeypatch.delenv("ASTERISM_BUILDER_MODEL", raising=False)
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-opus-4-7")
    assert claude_cli.resolve_model("builder") == "claude-opus-4-7"


def test_claude_resolve_model_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.llm import claude_cli
    monkeypatch.delenv("ASTERISM_BUILDER_MODEL", raising=False)
    monkeypatch.delenv("ASTERISM_AGENT_MODEL", raising=False)
    assert claude_cli.resolve_model("builder") == claude_cli.DEFAULT_MODEL


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


# Note: F31's substring-based threshold tier was retired together with
# the Asterism.yaml introduction. The threshold resolution chain is
# tested via tests/test_config.py + tests/test_dispatcher.py; weak-tier
# users now set `dispatch.builder_threshold: 5` explicitly.


# ---------------------------------------------------------------------
# F44 — agent cwd anchored at problem_dir (soft sandbox)
# ---------------------------------------------------------------------

def test_claude_spawn_cwd_is_problem_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F44 — claude subprocess runs with cwd=problem_dir, so relative
    paths the agent reads/writes resolve inside the Problem instead
    of at workspace root. Soft sandbox: doesn't block absolute-path
    Read on workspace files (claude CLI doesn't enforce that), but
    shifts the cognitive 'I am here' frame toward the Problem."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    calls = _capture_call(monkeypatch, module_name="claude_cli")
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/Problems/myproblem"),
        attempts_dir=Path("/x/.attempts/abc"),
        timeout_sec=60,
    ))
    assert calls, "subprocess.run should be invoked"
    assert calls[0]["kwargs"].get("cwd") == str(Path("/x/Problems/myproblem"))


def test_claude_spawn_adds_packages_dir_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """M3 — F44 narrows cwd to problem_dir; claude CLI then treats
    `cwd subtree ∪ --add-dir` as the implicit trust boundary, denying
    absolute-path Read/Grep on Mathlib even when `--allowed-tools` lists
    it. Spawn must add `.lake/packages` as a third --add-dir so the
    allowlist's path patterns actually take effect.

    Conditional: only adds when the dir physically exists, since claude
    CLI errors on missing --add-dir paths (fresh checkout pre-`lake build`)."""
    from Tooling import llm
    from Tooling.llm import claude_cli

    workspace = tmp_path
    (workspace / ".lake" / "packages").mkdir(parents=True)
    problem_dir = workspace / "Problems" / "myproblem"
    problem_dir.mkdir(parents=True)

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=workspace / "p.md",
        problem_dir=problem_dir,
        attempts_dir=workspace / ".attempts" / "abc",
        timeout_sec=60,
    ))
    cmd = captured[0]
    expected = str(workspace / ".lake" / "packages")
    add_dir_values = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--add-dir"]
    assert expected in add_dir_values, (
        f"--add-dir for {expected} missing from {add_dir_values}")


def test_claude_spawn_skips_packages_dir_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When `.lake/packages` doesn't exist (fresh checkout, before
    `lake build`), spawn must NOT pass --add-dir for it — claude CLI
    errors on missing --add-dir paths and would block the spawn."""
    from Tooling import llm
    from Tooling.llm import claude_cli

    problem_dir = tmp_path / "Problems" / "myproblem"
    problem_dir.mkdir(parents=True)
    # NOTE: no `.lake/packages` created

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=tmp_path / "p.md",
        problem_dir=problem_dir,
        attempts_dir=tmp_path / ".attempts" / "abc",
        timeout_sec=60,
    ))
    cmd = captured[0]
    add_dir_values = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--add-dir"]
    missing = str(tmp_path / ".lake" / "packages")
    assert missing not in add_dir_values


def test_gemini_spawn_cwd_is_problem_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F44 — same cwd anchoring for the gemini provider; both code
    paths must agree so a daemon mixing providers gets uniform
    behavior."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import gemini_cli

    calls = _capture_call(monkeypatch, module_name="gemini_cli")
    # Gemini also needs the Windows .cmd resolver patched so it
    # doesn't return None.
    monkeypatch.setattr(
        gemini_cli, "resolve_gemini_executable", lambda: "/fake/gemini.cmd")
    p = gemini_cli.GeminiCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/Problems/myproblem"),
        attempts_dir=Path("/x/.attempts/abc"),
        timeout_sec=60,
    ))
    assert calls, "subprocess.run should be invoked"
    assert calls[0]["kwargs"].get("cwd") == str(Path("/x/Problems/myproblem"))


# ---------------------------------------------------------------------
# F50 — Grep + Bash(Loogle) added to default tool surface
# ---------------------------------------------------------------------

def test_default_tools_include_grep_and_bash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F50 — agents need Grep for keyword search and Bash for the
    Loogle invocation. Both must be in DEFAULT_TOOLS so the system
    prompt advertises them."""
    from Tooling.llm import claude_cli
    assert "Grep" in claude_cli.DEFAULT_TOOLS
    assert "Bash" in claude_cli.DEFAULT_TOOLS


def test_spawn_passes_allowed_tools_for_loogle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F50 — Bash is gated via --allowed-tools so the agent can ONLY
    invoke `python -m Tooling.loogle`. Other Bash commands (rm, curl,
    git, ...) stay blocked by the permission system."""
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
    ))
    cmd = captured[0]
    assert "--allowed-tools" in cmd
    val = cmd[cmd.index("--allowed-tools") + 1]
    # Must scope to loogle invocation; arbitrary Bash blocked
    assert "Tooling.loogle" in val
    assert val.startswith("Bash(")


def test_allowed_tools_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASTERISM_CLAUDE_ALLOWED_TOOLS env replaces the default whitelist
    — for rare flows that legitimately need extra Bash commands."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    monkeypatch.setenv("ASTERISM_CLAUDE_ALLOWED_TOOLS",
                       "Bash(echo *) Bash(ls *)")
    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
    ))
    cmd = captured[0]
    val = cmd[cmd.index("--allowed-tools") + 1]
    assert val == "Bash(echo *) Bash(ls *)"


def test_allowed_tools_empty_env_omits_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting ASTERISM_CLAUDE_ALLOWED_TOOLS='' (explicit empty)
    drops the flag entirely — useful for debugging or when the
    operator wants Bash fully blocked."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    monkeypatch.setenv("ASTERISM_CLAUDE_ALLOWED_TOOLS", "")
    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/prob"),
        attempts_dir=Path("/x/att"),
        timeout_sec=60,
    ))
    cmd = captured[0]
    assert "--allowed-tools" not in cmd


def test_allowed_tools_scopes_read_to_problem_and_mathlib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path-scoped allowlist: Read/Grep on the active problem dir +
    workspace-Mathlib only. Other Problems/<...>/ deliberately absent
    so the agent can't burn turns probing unrelated problems."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/ws/p.md"),
        problem_dir=Path("/ws/Problems/active_problem"),
        attempts_dir=Path("/ws/.attempts/pid-x"),
        timeout_sec=60,
    ))
    cmd = captured[0]
    val = cmd[cmd.index("--allowed-tools") + 1]
    # Active problem + sandbox + entire Lake-packages tree in Read scope.
    # M1: scope is `.lake/packages/**` (not just `mathlib/Mathlib/**`)
    # so Sonnet's natural `rg .lake/packages/mathlib/...` queries hit
    # the allowlist instead of being denied (observed 18×/run).
    assert "Read(/ws/Problems/active_problem/**)" in val
    assert "Read(/ws/.attempts/pid-x/**)" in val
    assert "Read(/ws/.lake/packages/**/*.lean)" in val
    # Grep allowlist mirrors Read for the lemma-discovery use case
    assert "Grep(/ws/Problems/active_problem/**)" in val
    assert "Grep(/ws/.lake/packages/**)" in val
    # Other Problems must NOT be in scope — the F44 sandbox boundary
    # is what F53 rerun showed Sonnet wandering across.
    assert "Read(/ws/Problems/other" not in val
    # Bash allowlist (Loogle) preserved
    assert "Bash(python -m Tooling.loogle *)" in val


# ---------------------------------------------------------------------
# F45 — inline prompt body into -p (no Read-tool round-trip / no
# workspace prompts/ access requirement after F44 narrowed cwd)
# ---------------------------------------------------------------------

def test_claude_spawn_inlines_prompt_body_into_p(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """F45 — the prompt template content must be inlined into the -p
    flag so the agent doesn't need read access to the workspace
    Tooling/prompts/ directory (which is outside --add-dir after F44)."""
    from Tooling import llm
    from Tooling.llm import claude_cli

    prompt_file = tmp_path / "backward.md"
    prompt_file.write_text("INLINED PROMPT BODY MARKER", encoding="utf-8")
    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=prompt_file,
        problem_dir=tmp_path,
        attempts_dir=tmp_path,
        timeout_sec=60,
    ))
    cmd = captured[0]
    p_idx = cmd.index("-p") + 1
    # Prompt body must be present verbatim in -p
    assert "INLINED PROMPT BODY MARKER" in cmd[p_idx]
    # And must NOT instruct agent to Read the prompt path (the previous
    # broken pattern that depended on workspace access)
    assert "Read agent prompt at" not in cmd[p_idx]


def test_claude_spawn_missing_prompt_still_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """If the prompt file is unreadable (deleted, permission, etc.),
    spawn must still call subprocess and surface a marker — never crash
    or leave the daemon stuck. The agent will fail downstream with a
    normal failure_reason."""
    from Tooling import llm
    from Tooling.llm import claude_cli

    captured = _capture_cmd(monkeypatch)
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=tmp_path / "nonexistent.md",
        problem_dir=tmp_path,
        attempts_dir=tmp_path,
        timeout_sec=60,
    ))
    assert captured, "subprocess.run must still be invoked"
    p_idx = captured[0].index("-p") + 1
    assert "prompt file unavailable" in captured[0][p_idx]


def test_gemini_spawn_inlines_prompt_body_into_p(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """F45 — same inlining for the gemini provider."""
    from Tooling.llm import gemini_cli

    prompt_file = tmp_path / "backward.md"
    prompt_file.write_text("GEMINI PROMPT MARKER", encoding="utf-8")
    (tmp_path / "patch.lean").write_text("ok", encoding="utf-8")
    captured = _capture_gemini_cmd(monkeypatch, returncode=0)
    p = gemini_cli.GeminiCliProvider()
    p.spawn(llm.LLMRequest(
        kind="backward",
        prompt_path=prompt_file,
        problem_dir=tmp_path,
        attempts_dir=tmp_path,
        timeout_sec=60,
    ))
    cmd = captured[0]
    p_idx = cmd.index("-p") + 1
    assert "GEMINI PROMPT MARKER" in cmd[p_idx]
    assert "Read agent prompt at" not in cmd[p_idx]


def test_claude_complete_text_has_no_cwd_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F44 only sandboxes the file-IO `spawn` path. complete_text
    (F22 playbook idiom calls) is text-in / text-out — no tool use,
    no working dir relevance — so cwd stays unset (inherits
    daemon's cwd, which is fine)."""
    from Tooling.llm import claude_cli

    calls = _capture_call(monkeypatch, module_name="claude_cli")
    p = claude_cli.ClaudeCliProvider()
    p.complete_text(prompt="hi")
    assert calls
    assert "cwd" not in calls[0]["kwargs"]


def test_claude_spawn_sets_thinking_budget_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MAX_THINKING_TOKENS + CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING
    restored 2026-05-10 (originally from 9d05d19). Cap prevents
    Sonnet 4.6's adaptive thinking from producing 30-90K-char single
    thinking blocks that hit max_tokens before the agent calls any
    Write tool. Cap formula: max(1000, timeout_sec // 60 * 1000)
    tokens per turn. Multi-step thinking still accumulates across
    turns (each tool result starts a fresh per-turn budget).

    The retired alternative (watchdog + rescue spawn) was post-hoc
    cleanup: detect trap → SIGKILL → fresh-sid takeover. Cap is
    preventive: trap doesn't manifest because the API forces a
    transition when budget is hit."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    calls = _capture_call(monkeypatch, module_name="claude_cli")
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/Problems/myproblem"),
        attempts_dir=Path("/x/.attempts/abc"),
        timeout_sec=600,
    ))
    env = calls[0]["kwargs"]["env"]
    assert env.get("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING") == "1"
    # 600s spawn → 10000 tokens cap (1000 per minute).
    assert env.get("MAX_THINKING_TOKENS") == "10000"


def test_claude_spawn_thinking_budget_floors_at_1000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Floor of 1000 tokens for short spawns (e.g. 60s probe / 30s
    auxiliary). Avoids 0-cap which would block thinking entirely."""
    from pathlib import Path
    from Tooling import llm
    from Tooling.llm import claude_cli

    calls = _capture_call(monkeypatch, module_name="claude_cli")
    p = claude_cli.ClaudeCliProvider()
    p.spawn(llm.LLMRequest(
        kind="builder",
        prompt_path=Path("/x/p.md"),
        problem_dir=Path("/x/Problems/myproblem"),
        attempts_dir=Path("/x/.attempts/abc"),
        timeout_sec=30,  # below 60s/min baseline
    ))
    env = calls[0]["kwargs"]["env"]
    assert env.get("MAX_THINKING_TOKENS") == "1000"
