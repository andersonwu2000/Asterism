"""Unit tests for Tooling/agent/provider.py and providers/claude.py.

All subprocess calls are mocked — no real claude CLI or git invocations.

Test coverage:
  1. AgentResponse dataclass fields
  2. Provider.resolve_model_id — tier lookup + literal passthrough
  3. ModelResolver — framework default, META.md override, missing key
  4. FallbackChain — single-entry pass-through, success, exhausted on repeated error
  5. ClaudeProvider._build_cmd — --add-dir / --permission-mode / --session-id args
  6. ClaudeProvider.invoke — subprocess args, output capture, timeout → ProviderError
  7. ClaudeProvider.check_scope — clean tree, staged-only changes, outside write detected
  8. ClaudeProvider.gc_session — jsonl cleanup
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from Tooling.agent.provider import (
    AgentResponse,
    FallbackChain,
    FRAMEWORK_MODEL_DEFAULTS,
    ModelResolver,
    Provider,
    ProviderError,
)
from Tooling.agent.providers.claude import CLAUDE_MODEL_MAP, ClaudeProvider


# ---------------------------------------------------------------------------
# 1. AgentResponse dataclass
# ---------------------------------------------------------------------------

class TestAgentResponse:
    def test_fields(self):
        r = AgentResponse(output="hello", session_id="s1", exit_code=0)
        assert r.output == "hello"
        assert r.session_id == "s1"
        assert r.exit_code == 0
        assert r.extra == {}

    def test_extra(self):
        r = AgentResponse(output="x", session_id="s2", extra={"key": "val"})
        assert r.extra["key"] == "val"


# ---------------------------------------------------------------------------
# 2. Provider.resolve_model_id
# ---------------------------------------------------------------------------

class TestResolveModelId:
    """ClaudeProvider inherits resolve_model_id from Provider."""

    def test_tier_lookup(self):
        p = ClaudeProvider()
        assert p.resolve_model_id("haiku") == CLAUDE_MODEL_MAP["haiku"]
        assert p.resolve_model_id("sonnet") == CLAUDE_MODEL_MAP["sonnet"]
        assert p.resolve_model_id("opus") == CLAUDE_MODEL_MAP["opus"]

    def test_literal_passthrough(self):
        # A literal model-id not in model_map is returned unchanged.
        p = ClaudeProvider()
        assert p.resolve_model_id("claude-custom-model") == "claude-custom-model"


# ---------------------------------------------------------------------------
# 3. ModelResolver — two-layer lookup
# ---------------------------------------------------------------------------

class TestModelResolver:
    def test_framework_default_builder(self):
        r = ModelResolver()
        assert r.resolve("builder", "tactic_llm") == FRAMEWORK_MODEL_DEFAULTS["builder.tactic_llm"]

    def test_framework_default_backward(self):
        r = ModelResolver()
        assert r.resolve("backward", "agent") == FRAMEWORK_MODEL_DEFAULTS["backward.agent"]

    def test_meta_override(self):
        r = ModelResolver(meta_models={"backward.agent": "opus"})
        assert r.resolve("backward", "agent") == "opus"

    def test_meta_override_partial(self):
        # Only backward.agent overridden; builder.tactic_llm uses framework default.
        r = ModelResolver(meta_models={"backward.agent": "opus"})
        assert r.resolve("builder", "tactic_llm") == FRAMEWORK_MODEL_DEFAULTS["builder.tactic_llm"]

    def test_meta_override_exact_id(self):
        # META.md can specify a literal model-id, not just a tier name.
        r = ModelResolver(meta_models={"backward.agent": "claude-sonnet-4-6"})
        assert r.resolve("backward", "agent") == "claude-sonnet-4-6"

    def test_missing_key_raises(self):
        r = ModelResolver()
        with pytest.raises(KeyError, match="no_pipeline.no_stage"):
            r.resolve("no_pipeline", "no_stage")


# ---------------------------------------------------------------------------
# 4. FallbackChain — single-entry (P2)
# ---------------------------------------------------------------------------

class MockProvider(Provider):
    name = "mock"
    model_map = {"haiku": "mock-haiku", "sonnet": "mock-sonnet", "opus": "mock-opus"}

    def __init__(self, responses=None, raise_after=None):
        self._responses = list(responses or [])
        self._raise_after = raise_after  # raise ProviderError after N calls
        self._call_count = 0

    def invoke(self, model_tier, prompt, scope_dirs, session_id, *, cwd=None):
        self._call_count += 1
        if self._raise_after is not None and self._call_count > self._raise_after:
            raise ProviderError("mock error")
        if self._responses:
            return self._responses.pop(0)
        return AgentResponse(output="mock output", session_id=session_id)

    def gc_session(self, session_id):
        pass


class TestFallbackChain:
    def test_empty_providers_raises(self):
        with pytest.raises(ValueError):
            FallbackChain(providers=[])

    def test_single_entry_success(self):
        provider = MockProvider()
        chain = FallbackChain(providers=[provider])
        resp, outcome = chain.run("sonnet", "prompt", ["/staging"], "sess1")
        assert outcome == "success"
        assert resp is not None
        assert resp.output == "mock output"

    def test_exhausted_on_repeated_provider_error(self):
        # Provider always raises ProviderError → chain returns exhausted.
        provider = MockProvider(raise_after=0)
        chain = FallbackChain(providers=[provider], n_retry=3)
        resp, outcome = chain.run("sonnet", "prompt", ["/staging"], "sess1")
        assert outcome == "exhausted"
        assert resp is None
        assert provider._call_count == 3

    def test_scope_violation_causes_retry(self):
        # validate_scope returns False for first 2 calls, True on 3rd.
        call_count = {"n": 0}

        def fake_validate(staging_dir, session_id):
            call_count["n"] += 1
            return call_count["n"] >= 3

        provider = MockProvider()
        chain = FallbackChain(
            providers=[provider],
            n_retry=5,
            validate_scope=fake_validate,
        )
        resp, outcome = chain.run(
            "sonnet", "prompt", ["/staging"], "sess1", staging_dir="/staging"
        )
        assert outcome == "success"
        assert provider._call_count == 3

    def test_scope_always_fails_exhausted(self):
        # validate_scope always False → exhausted after n_retry.
        provider = MockProvider()
        chain = FallbackChain(
            providers=[provider],
            n_retry=3,
            validate_scope=lambda *_: False,
        )
        resp, outcome = chain.run(
            "sonnet", "prompt", ["/staging"], "sess1", staging_dir="/staging"
        )
        assert outcome == "exhausted"
        assert provider._call_count == 3

    def test_session_id_unique_per_invoke(self):
        """P7演習 fix: chain.run must mint a fresh session_id per inner
        provider.invoke call, otherwise claude CLI rejects the second call
        with 'Session ID ... is already in use' on every retry path
        (ProviderError, scope-fail). Patch 11 (Backward._run_loop) only
        addressed the OUTER max_retries, not the inner chain retries.

        Verify by spying on session_id values across n_retry invocations
        with a provider that always raises (so we hit the retry branch).
        """
        captured_session_ids = []

        class CapturingProvider(Provider):
            name = "capture"
            model_map = {"sonnet": "x"}

            def invoke(self, model_tier, prompt, scope_dirs, session_id,
                       *, cwd=None):
                captured_session_ids.append(session_id)
                raise ProviderError("force retry")

            def gc_session(self, session_id):
                pass

        chain = FallbackChain(providers=[CapturingProvider()], n_retry=4)
        resp, outcome = chain.run(
            "sonnet", "prompt", ["/staging"], "pipeline-base-sess"
        )
        assert outcome == "exhausted"
        assert len(captured_session_ids) == 4
        # All four IDs must be distinct (no claude CLI collision).
        assert len(set(captured_session_ids)) == 4
        # And none should equal the caller-supplied base session_id —
        # base is reserved for pipeline-level tracing, not provider calls.
        assert "pipeline-base-sess" not in captured_session_ids

    def test_session_id_unique_across_providers(self):
        """Same invariant must hold across providers in the chain — mixing
        claude → gemini → codex with reused session_id would also fail
        for any provider that enforces session uniqueness.
        """
        captured = []

        class P1(Provider):
            name = "p1"
            model_map = {"sonnet": "x"}

            def invoke(self, model_tier, prompt, scope_dirs, session_id,
                       *, cwd=None):
                captured.append(("p1", session_id))
                raise ProviderError("p1 fail")

            def gc_session(self, session_id):
                pass

        class P2(Provider):
            name = "p2"
            model_map = {"sonnet": "x"}

            def invoke(self, model_tier, prompt, scope_dirs, session_id,
                       *, cwd=None):
                captured.append(("p2", session_id))
                raise ProviderError("p2 fail")

            def gc_session(self, session_id):
                pass

        chain = FallbackChain(providers=[P1(), P2()], n_retry=2)
        chain.run("sonnet", "prompt", ["/staging"], "base-sess")

        # 2 providers × 2 retries = 4 calls, all with distinct session_ids.
        assert len(captured) == 4
        ids = [sid for (_, sid) in captured]
        assert len(set(ids)) == 4


# ---------------------------------------------------------------------------
# 5. ClaudeProvider._build_cmd
# ---------------------------------------------------------------------------

class TestBuildCmd:
    def _provider(self):
        return ClaudeProvider(claude_bin="claude")

    def test_basic_cmd(self):
        p = self._provider()
        cmd = p._build_cmd("claude-sonnet-4-6", "hello", ["/staging"], "sess1")
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "hello" in cmd
        assert "--model" in cmd
        assert "claude-sonnet-4-6" in cmd

    def test_add_dir_flags(self):
        p = self._provider()
        cmd = p._build_cmd(
            "claude-sonnet-4-6", "p",
            ["/staging", "/problem"],
            "sess1",
        )
        assert cmd.count("--add-dir") == 2
        idx1 = cmd.index("--add-dir")
        assert cmd[idx1 + 1] == "/staging"
        idx2 = cmd.index("--add-dir", idx1 + 1)
        assert cmd[idx2 + 1] == "/problem"

    def test_permission_mode_acceptEdits(self):
        p = self._provider()
        cmd = p._build_cmd("claude-sonnet-4-6", "p", ["/s"], "sess1")
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "acceptEdits"

    def test_session_id_flag(self):
        p = self._provider()
        cmd = p._build_cmd("claude-sonnet-4-6", "p", ["/s"], "my-session-xyz")
        assert "--session-id" in cmd
        idx = cmd.index("--session-id")
        assert cmd[idx + 1] == "my-session-xyz"

    def test_multiple_add_dirs(self):
        p = self._provider()
        scope = ["/staging", "/problem_dir", "/library"]
        cmd = p._build_cmd("claude-sonnet-4-6", "p", scope, "sess1")
        add_dir_positions = [i for i, x in enumerate(cmd) if x == "--add-dir"]
        assert len(add_dir_positions) == 3
        for pos, expected in zip(add_dir_positions, scope):
            assert cmd[pos + 1] == expected


# ---------------------------------------------------------------------------
# 6. ClaudeProvider.invoke — subprocess mocked
# ---------------------------------------------------------------------------

def _mock_completed(stdout="agent output", returncode=0):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.returncode = returncode
    return m


class TestClaudeInvoke:
    def test_successful_invoke(self, tmp_path):
        p = ClaudeProvider(repo_root=tmp_path)
        with patch("subprocess.run", return_value=_mock_completed("done")) as mock_run:
            resp = p.invoke("sonnet", "my prompt", [str(tmp_path)], "sess1")
        assert resp.output == "done"
        assert resp.exit_code == 0
        assert resp.session_id == "sess1"

    def test_cmd_args_passed_to_subprocess(self, tmp_path):
        p = ClaudeProvider(repo_root=tmp_path)
        with patch("subprocess.run", return_value=_mock_completed()) as mock_run:
            p.invoke("haiku", "prompt", [str(tmp_path)], "sess42")
        cmd_passed = mock_run.call_args[0][0]
        assert "--permission-mode" in cmd_passed
        assert "acceptEdits" in cmd_passed
        assert "--session-id" in cmd_passed
        assert "sess42" in cmd_passed
        assert "--add-dir" in cmd_passed

    def test_model_tier_resolved(self, tmp_path):
        p = ClaudeProvider(repo_root=tmp_path)
        with patch("subprocess.run", return_value=_mock_completed()) as mock_run:
            p.invoke("opus", "prompt", [str(tmp_path)], "sess1")
        cmd_passed = mock_run.call_args[0][0]
        assert CLAUDE_MODEL_MAP["opus"] in cmd_passed

    def test_timeout_raises_provider_error(self, tmp_path):
        p = ClaudeProvider(invoke_timeout=1.0, repo_root=tmp_path)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 1.0)):
            with pytest.raises(ProviderError, match="timed out"):
                p.invoke("sonnet", "prompt", [str(tmp_path)], "sess1")

    def test_binary_not_found_raises_provider_error(self, tmp_path):
        p = ClaudeProvider(claude_bin="nonexistent_bin", repo_root=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(ProviderError, match="not found"):
                p.invoke("sonnet", "prompt", [str(tmp_path)], "sess1")

    def test_cwd_defaults_to_first_scope_dir(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = ClaudeProvider(repo_root=tmp_path)
        with patch("subprocess.run", return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "prompt", [str(staging), str(tmp_path)], "sess1")
        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == str(staging)

    def test_cwd_override(self, tmp_path):
        p = ClaudeProvider(repo_root=tmp_path)
        custom_cwd = str(tmp_path / "custom")
        with patch("subprocess.run", return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "prompt", [str(tmp_path)], "sess1", cwd=custom_cwd)
        assert mock_run.call_args[1]["cwd"] == custom_cwd

    def test_empty_scope_dirs_raises(self, tmp_path):
        p = ClaudeProvider(repo_root=tmp_path)
        with pytest.raises(ProviderError, match="scope_dirs"):
            p.invoke("sonnet", "prompt", [], "sess1")

    def test_stdin_devnull(self, tmp_path):
        p = ClaudeProvider(repo_root=tmp_path)
        with patch("subprocess.run", return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "prompt", [str(tmp_path)], "sess1")
        kwargs = mock_run.call_args[1]
        assert kwargs["stdin"] is subprocess.DEVNULL

    def test_stderr_merged_into_stdout(self, tmp_path):
        p = ClaudeProvider(repo_root=tmp_path)
        with patch("subprocess.run", return_value=_mock_completed()) as mock_run:
            p.invoke("sonnet", "prompt", [str(tmp_path)], "sess1")
        kwargs = mock_run.call_args[1]
        assert kwargs["stderr"] is subprocess.STDOUT

    def test_extra_redacts_prompt(self, tmp_path):
        # AgentResponse.extra.argv should replace the prompt string with
        # "<PROMPT>" placeholder to avoid retention of full prompt text.
        p = ClaudeProvider(repo_root=tmp_path)
        prompt_text = "secret-prompt-content-xyz"
        with patch("subprocess.run", return_value=_mock_completed()):
            resp = p.invoke("sonnet", prompt_text, [str(tmp_path)], "sess1")
        argv = resp.extra["argv"]
        assert prompt_text not in argv
        assert "<PROMPT>" in argv
        # Other args (flags, model id, session id) must still be present.
        assert "--permission-mode" in argv
        assert "acceptEdits" in argv
        assert "sess1" in argv


# ---------------------------------------------------------------------------
# 7. ClaudeProvider.check_scope — git status backstop
# ---------------------------------------------------------------------------

class TestCheckScope:
    def _provider(self, tmp_path):
        return ClaudeProvider(repo_root=tmp_path)

    def _mock_git(self, output: str, returncode: int = 0):
        result = MagicMock()
        result.stdout = output
        result.returncode = returncode
        return result

    def test_clean_tree_passes(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        with patch("subprocess.run", return_value=self._mock_git("")):
            assert p.check_scope(staging) is True

    def test_staging_only_changes_pass(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        # git porcelain output: only a file inside staging
        git_output = "M  staging/proof.lean\n"
        with patch("subprocess.run", return_value=self._mock_git(git_output)):
            assert p.check_scope(staging) is True

    def test_outside_change_fails(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        # A file outside staging was modified
        git_output = "M  Tooling/cli.py\n"
        with patch("subprocess.run", return_value=self._mock_git(git_output)):
            assert p.check_scope(staging) is False

    def test_mixed_inside_outside_fails(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        git_output = "M  staging/proof.lean\nM  Tooling/cli.py\n"
        with patch("subprocess.run", return_value=self._mock_git(git_output)):
            assert p.check_scope(staging) is False

    def test_untracked_inside_staging_passes(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        git_output = "?? staging/new_file.lean\n"
        with patch("subprocess.run", return_value=self._mock_git(git_output)):
            assert p.check_scope(staging) is True

    def test_untracked_outside_staging_fails(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        git_output = "?? some_other_dir/evil.txt\n"
        with patch("subprocess.run", return_value=self._mock_git(git_output)):
            assert p.check_scope(staging) is False

    def test_git_unavailable_fails_safe(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert p.check_scope(staging) is False

    def test_git_timeout_fails_safe(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        p = self._provider(tmp_path)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            assert p.check_scope(staging) is False


# ---------------------------------------------------------------------------
# 8. ClaudeProvider.gc_session
# ---------------------------------------------------------------------------

class TestGcSession:
    def test_gc_removes_jsonl(self, tmp_path):
        # Set up fake ~/.claude/projects/<project>/<session_id>.jsonl
        projects_dir = tmp_path / ".claude" / "projects" / "myproject"
        projects_dir.mkdir(parents=True)
        session_id = "abc-123-def"
        jsonl_file = projects_dir / f"{session_id}.jsonl"
        jsonl_file.write_text("transcript data")

        p = ClaudeProvider()
        with patch("pathlib.Path.home", return_value=tmp_path):
            p.gc_session(session_id)

        assert not jsonl_file.exists()

    def test_gc_leaves_other_sessions(self, tmp_path):
        projects_dir = tmp_path / ".claude" / "projects" / "p"
        projects_dir.mkdir(parents=True)
        session_id = "target-session"
        other_id = "other-session"
        target = projects_dir / f"{session_id}.jsonl"
        other = projects_dir / f"{other_id}.jsonl"
        target.write_text("a")
        other.write_text("b")

        p = ClaudeProvider()
        with patch("pathlib.Path.home", return_value=tmp_path):
            p.gc_session(session_id)

        assert not target.exists()
        assert other.exists()

    def test_gc_no_claude_dir_silent(self, tmp_path):
        p = ClaudeProvider()
        with patch("pathlib.Path.home", return_value=tmp_path):
            p.gc_session("nonexistent-session")  # should not raise

    def test_gc_empty_session_id_raises(self, tmp_path):
        # Empty session_id would expand glob to "*.jsonl" and wipe everything.
        p = ClaudeProvider()
        with pytest.raises(ValueError, match="session_id must be non-empty"):
            p.gc_session("")
