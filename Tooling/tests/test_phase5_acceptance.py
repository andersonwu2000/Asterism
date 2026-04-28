"""P5 Acceptance tests #0a / #0b / #1-#14 (Milestone B subset).

Covers `docs/dev/phase5_construction.md ## Acceptance criteria` to the
extent achievable with **Milestone A (ConstructionSearch + continuous
runtime) deferred** per task.md ## 延後 cycles. Milestone A items
(#0a, #1-#12) are @pytest.mark.skip with the deferral reason — they
re-enable when ConstructionSearch ships.

Active in-process gates (Milestone B):

  AC #0b Demo Multi-provider fallback (real lake)  — manual gate
  AC #13 Provider fallback chain (PROVIDER_MOCK)   — covered
  AC #14 Provider scope-isolation (evil_write)     — covered
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from Tooling.agent.provider import (
    AgentResponse,
    FallbackChain,
    ProviderError,
)
from Tooling.agent.providers.claude import ClaudeProvider
from Tooling.agent.providers.codex import CodexProvider
from Tooling.agent.providers.gemini import GeminiProvider


def _mock_subprocess_success(stdout="ok"):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout)


# ─────────────────────────────────────────────────────────────
# Milestone A — DEFERRED (ConstructionSearch deferral cascade)
# ─────────────────────────────────────────────────────────────


class TestMilestoneADeferred:
    @pytest.mark.skip(reason="DEFERRED: Milestone A demo Hadamard 4×4 needs "
                              "ConstructionSearch pipeline (task.md ## 延後 cycles)")
    def test_0a_hadamard_demo(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #1 construction kind dispatch "
                              "(task.md ## 延後 cycles)")
    def test_1_construction_kind_dispatch(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #2a continuous pool isolation "
                              "(task.md ## 延後 cycles)")
    def test_2a_pool_isolation(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #3 checkpoint write "
                              "(task.md ## 延後 cycles)")
    def test_3_checkpoint_write(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #4 pause/resume continuous task "
                              "(task.md ## 延後 cycles)")
    def test_4_pause_resume(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #5 T_pause_max timeout "
                              "(task.md ## 延後 cycles)")
    def test_5_pause_timeout(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #6 crash recovery for continuous "
                              "task (task.md ## 延後 cycles)")
    def test_6_crash_recovery(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #7 silver→gold construction upgrade "
                              "(task.md ## 延後 cycles)")
    def test_7_silver_to_gold(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #8 derived_from FK cascade "
                              "(task.md ## 延後 cycles)")
    def test_8_derived_from_cascade(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #9 cancellation continuous SIGTERM/KILL "
                              "(task.md ## 延後 cycles)")
    def test_9_cancellation(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #10 best-known promotion + history "
                              "(task.md ## 延後 cycles)")
    def test_10_best_known(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #11a/#11b reproducibility metadata "
                              "(task.md ## 延後 cycles)")
    def test_11_reproducibility(self) -> None:
        pass

    @pytest.mark.skip(reason="DEFERRED: AC #12 first-checkpoint crash → killed "
                              "(task.md ## 延後 cycles)")
    def test_12_first_checkpoint_crash(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# Milestone B
# ─────────────────────────────────────────────────────────────


class TestMilestoneBManualGate:
    @pytest.mark.skip(reason="manual gate: AC #0b Multi-provider fallback "
                              "demo (PROVIDER_MOCK_CLAUDE=fail_always → gemini "
                              "fallback) requires real lake env + claude/gemini/"
                              "codex CLIs + add_comm_demo from P2")
    def test_0b_multi_provider_fallback_demo(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# AC #13: Provider fallback chain (PROVIDER_MOCK env hook)
# ─────────────────────────────────────────────────────────────


class TestAC13ProviderFallbackChain:
    """Spec AC #13 字面: PROVIDER_MOCK_CLAUDE=fail_after_3 +
    PROVIDER_MOCK_GEMINI=fail_after_3 → claude 連 3 次失敗 → 切 gemini →
    gemini 連 3 次失敗 → 切 codex；任一家成功則 outcome 正常；全失敗
    → outcome=exhausted."""

    def test_claude_fail_always_falls_through_to_gemini(
        self, tmp_path, monkeypatch,
    ):
        """Smallest in-process variant of AC #0b — claude failing always
        causes the chain to try gemini, which (mocked) succeeds."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_always")
        chain = FallbackChain(
            providers=[
                ClaudeProvider(repo_root=tmp_path),
                GeminiProvider(repo_root=tmp_path),
                CodexProvider(repo_root=tmp_path),
            ],
            n_retry=3,
        )
        with patch(
            "subprocess.run",
            return_value=_mock_subprocess_success("from gemini"),
        ) as mock_run:
            resp, outcome = chain.run(
                "sonnet", "p", [str(tmp_path)], "s1",
            )
        assert outcome == "success"
        assert resp is not None
        assert resp.output == "from gemini"
        # Only gemini called subprocess.run; claude was short-circuited.
        assert mock_run.call_count == 1

    def test_full_failure_chain_returns_exhausted(self, tmp_path, monkeypatch):
        """All three providers fail → outcome='exhausted'."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_always")
        monkeypatch.setenv("PROVIDER_MOCK_GEMINI", "fail_always")
        monkeypatch.setenv("PROVIDER_MOCK_CODEX", "fail_always")
        chain = FallbackChain(
            providers=[
                ClaudeProvider(repo_root=tmp_path),
                GeminiProvider(repo_root=tmp_path),
                CodexProvider(repo_root=tmp_path),
            ],
            n_retry=2,  # keep test fast
        )
        resp, outcome = chain.run(
            "sonnet", "p", [str(tmp_path)], "s1",
        )
        assert outcome == "exhausted"
        assert resp is None

    def test_claude_immediate_fail_then_codex_via_gemini_immediate_fail(
        self, tmp_path, monkeypatch,
    ):
        """C38 R3 MED-1 rename: spec line 161's literal `fail_after_3`
        env value is **not** what this test exercises — it uses
        fail_after_0 (≡ immediate-fail). Renamed to reflect actual
        coverage. The literal fail_after_3 → 3 successes-then-fail
        path is covered by test_provider_mock_hook.py
        TestFailAfterN.test_claude_fail_after_2 at the unit layer; in
        acceptance scope, exercising fail_after_3 across the chain
        requires validate_scope to also reject those 3 mock-success
        responses, and the chain semantics for that combination remain
        a P5.x patch detail (audit LOW from C38 R2 also flagged this).
        """
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "fail_after_0")
        monkeypatch.setenv("PROVIDER_MOCK_GEMINI", "fail_after_0")
        chain = FallbackChain(
            providers=[
                ClaudeProvider(repo_root=tmp_path),
                GeminiProvider(repo_root=tmp_path),
                CodexProvider(repo_root=tmp_path),
            ],
            n_retry=2,
        )
        with patch(
            "subprocess.run",
            return_value=_mock_subprocess_success("from codex"),
        ):
            resp, outcome = chain.run(
                "sonnet", "p", [str(tmp_path)], "s1",
            )
        assert outcome == "success"
        assert resp is not None
        assert resp.output == "from codex"

    def test_chain_runs_through_in_order(self, tmp_path, monkeypatch):
        """Order is preserved: claude tried first; gemini second; codex
        third. Verified by tracking which provider's invoke is called
        (mock the FIRST provider's invoke directly, then the chain
        moves to the next provider)."""
        chain = FallbackChain(
            providers=[
                ClaudeProvider(repo_root=tmp_path),
                GeminiProvider(repo_root=tmp_path),
                CodexProvider(repo_root=tmp_path),
            ],
            n_retry=1,
        )
        # Mock claude to fail, gemini to succeed; codex never invoked
        with patch.object(
            chain.providers[0], "invoke",
            side_effect=ProviderError("claude down"),
        ) as claude_mock, patch.object(
            chain.providers[1], "invoke",
            return_value=AgentResponse(
                output="gemini ok", session_id="s",
                exit_code=0, extra={},
            ),
        ) as gemini_mock, patch.object(
            chain.providers[2], "invoke",
        ) as codex_mock:
            resp, outcome = chain.run(
                "sonnet", "p", [str(tmp_path)], "s1",
            )
        assert outcome == "success"
        assert claude_mock.called
        assert gemini_mock.called
        assert not codex_mock.called  # never reached


# ─────────────────────────────────────────────────────────────
# AC #14: Provider scope-isolation (evil_write env hook)
# ─────────────────────────────────────────────────────────────


class TestAC14ProviderScopeIsolation:
    """Spec AC #14 字面: 對每個 provider 跑 evil prompt（PROVIDER_MOCK_
    <NAME>=evil_write env hook 強制 agent 在 staging 外 write）→ git
    status 兜底偵測到、該 stage failed、retry 切下一家.

    Test approach: use validate_scope as a fake check_scope that returns
    False if any path outside staging was written. The PROVIDER_MOCK
    evil_write handler writes to staging.parent — outside scope_dirs[0]."""

    def test_evil_write_caught_by_validate_scope(self, tmp_path, monkeypatch):
        """PROVIDER_MOCK_CLAUDE=evil_write writes outside staging.
        validate_scope returns False on the leak → claude attempt rejected.
        The persistent EVIL file makes validate_scope reject every
        subsequent retry too, so outcome=exhausted. Operators inspecting
        the audit trail see the EVIL_claude_* sentinel as evidence of the
        violation (the check_scope failure was real, not silent)."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "evil_write")

        staging = tmp_path / "staging"
        staging.mkdir()

        # validate_scope: True iff no EVIL_* file present in tmp_path
        def fake_validate(staging_dir, session_id):
            for _ in tmp_path.glob("EVIL_*"):
                return False
            return True

        chain = FallbackChain(
            providers=[ClaudeProvider(repo_root=tmp_path)],
            n_retry=2,
            validate_scope=fake_validate,
        )
        resp, outcome = chain.run(
            "sonnet", "p", [str(staging)], "session1234",
            staging_dir=str(staging),
        )
        # Chain rejected claude (validate_scope caught the leak); single-
        # provider chain → outcome=exhausted.
        assert outcome == "exhausted"
        assert resp is None
        # Sentinel file is the persistent evidence of the violation.
        evil_files = list(tmp_path.glob("EVIL_*"))
        assert len(evil_files) >= 1
        assert "EVIL_claude_session1" in evil_files[0].name

    def test_evil_write_each_provider_independent(self, tmp_path, monkeypatch):
        """Each provider's evil_write writes a distinct sentinel file.
        Important for concurrency / observability — operators see which
        provider violated."""
        monkeypatch.setenv("PROVIDER_MOCK_GEMINI", "evil_write")
        staging = tmp_path / "stg"
        staging.mkdir()
        gemini = GeminiProvider(repo_root=tmp_path)
        resp = gemini.invoke("sonnet", "p", [str(staging)], "abc12345")
        assert resp.extra["mock_mode"] == "evil_write"
        assert "EVIL_gemini_" in resp.extra["evil_path"]

    def test_evil_write_chain_switches_to_clean_provider(
        self, tmp_path, monkeypatch,
    ):
        """C38 R3 LOW-1/2/3: AC #14 spec line 162「retry 切下一家」+「對
        每個 provider」coverage. Chain `[claude, gemini, codex]` —
        claude+gemini both PROVIDER_MOCK=evil_write (writes outside);
        codex uncontaminated. validate_scope cleans up the EVIL_*
        sentinels per attempt so each provider's check is isolated.
        Expected: claude rejected → gemini rejected → codex succeeds."""
        monkeypatch.setenv("PROVIDER_MOCK_CLAUDE", "evil_write")
        monkeypatch.setenv("PROVIDER_MOCK_GEMINI", "evil_write")
        # PROVIDER_MOCK_CODEX intentionally unset → codex runs the real
        # subprocess.run path which we patch to succeed.

        staging = tmp_path / "staging"
        staging.mkdir()

        def per_attempt_validate(staging_dir, session_id):
            """Pretend EVIL_* leakage is detected, then sweep it so the
            next provider's attempt starts clean. Mirrors what a real
            git status reset would do between retries — but we keep it
            in-memory to avoid actual git ops in the test."""
            evil = list(tmp_path.glob("EVIL_*"))
            for f in evil:
                f.unlink()
            return not evil  # had any → False; clean → True

        chain = FallbackChain(
            providers=[
                ClaudeProvider(repo_root=tmp_path),
                GeminiProvider(repo_root=tmp_path),
                CodexProvider(repo_root=tmp_path),
            ],
            n_retry=1,
            validate_scope=per_attempt_validate,
        )
        with patch(
            "subprocess.run",
            return_value=_mock_subprocess_success("from codex (clean)"),
        ):
            resp, outcome = chain.run(
                "sonnet", "p", [str(staging)], "session1234",
                staging_dir=str(staging),
            )
        assert outcome == "success"
        assert resp is not None
        assert resp.output == "from codex (clean)"


# ─────────────────────────────────────────────────────────────
# Smoke: chain factory wired in scheduler (cross-cycle gate)
# ─────────────────────────────────────────────────────────────


class TestChainFactorySmoke:
    """Acceptance-level smoke: the scheduler's _make_fallback_chain
    actually wires [claude, gemini, codex] (cross-ref test_scheduler.py
    TestMakeFallbackChain). Pinning here ensures Milestone B sanity gate
    reaches the production fallback path, not a test-only bypass."""

    def test_scheduler_chain_includes_three_providers(self, tmp_path):
        from Tooling.scheduler import Reactor, ReactorConfig
        cfg = ReactorConfig(base_dir=str(tmp_path), pool_size=1)
        r = Reactor(str(tmp_path / "test.db"), cfg)
        chain = r._make_fallback_chain()
        assert len(chain.providers) == 3
        names = [p.name for p in chain.providers]
        assert names == ["claude", "gemini", "codex"]
