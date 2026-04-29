"""Provider abstraction for agent stage runtime (P2).

Hierarchy:
  Provider (ABC)            – one per LLM vendor
  AgentResponse             – uniform return type
  ModelResolver             – two-layer model-id lookup (framework default + Problem META.md)
  FallbackChain             – P2 single-entry; P5 will extend to multi-provider

Model tiers (vocabulary shared across providers):
  haiku  → cheapest/fastest
  sonnet → balanced  (framework default for backward.agent)
  opus   → strongest

Framework model defaults (P2):
  builder.tactic_llm → haiku
  backward.agent     → sonnet

Model resolution order (two layers; Strategist third layer留P7):
  1. Problem META.md models.<pipeline_kind>.<stage>  (per-problem override)
  2. framework agent.model_defaults.<pipeline_kind>.<stage>

P5 C37 PROVIDER_MOCK_<NAME> env hook (test-only, see test_hooks.md):
  - PROVIDER_MOCK_CLAUDE / PROVIDER_MOCK_GEMINI / PROVIDER_MOCK_CODEX
  - mode = fail_always | fail_after_<N> | evil_write
  - handled by Provider._maybe_apply_mock at the top of each subclass's
    invoke() so the real subprocess never runs when the hook is set
"""
from __future__ import annotations

import abc
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# AgentResponse
# ---------------------------------------------------------------------------

@dataclass
class AgentResponse:
    """Uniform response from any provider's invoke()."""
    output: str                        # raw text output from the agent
    session_id: str                    # echoed back (may differ if provider rotated)
    exit_code: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider ABC
# ---------------------------------------------------------------------------

class Provider(abc.ABC):
    """Abstract base class for LLM CLI providers.

    Subclasses: claude (P2), gemini (P5), codex (P5).
    """

    name: str  # 'claude' | 'gemini' | 'codex'

    # tier vocab → provider-specific model id
    model_map: dict[str, str] = {}

    # PROVIDER_MOCK_<NAME>=fail_after_<N> per-instance counter; not class-level
    # so concurrent providers don't share state. Initialised lazily in
    # _maybe_apply_mock (avoids forcing every Provider subclass to call super().__init__).
    _mock_call_count: int = 0

    @abc.abstractmethod
    def invoke(
        self,
        model_tier: str,
        prompt: str,
        scope_dirs: list[str],
        session_id: str,
        *,
        cwd: str | None = None,
    ) -> AgentResponse:
        """Run the agent for one turn.

        Args:
            model_tier:  'haiku' | 'sonnet' | 'opus'  (or a literal model-id
                         from META.md override — provider resolves it)
            prompt:      Full prompt string.
            scope_dirs:  Paths the agent is allowed to read/write.
                         Provider is responsible for translating to its own
                         scope-isolation flag (e.g. --add-dir for claude).
            session_id:  Pipeline-level unique id; provider stores session
                         state and GC's it on pipeline end.
            cwd:         Working directory for the subprocess.  Defaults to
                         the first entry of scope_dirs (staging dir).
        """

    @abc.abstractmethod
    def gc_session(self, session_id: str) -> None:
        """Clean up any session state (jsonl logs, temp files) for session_id."""

    def resolve_model_id(self, model_tier: str) -> str:
        """Map a tier name (or literal id) to the provider's model id.

        If model_tier is already a provider-recognized literal id (not in
        model_map keys), return it unchanged — lets META.md specify exact ids.
        """
        return self.model_map.get(model_tier, model_tier)

    def _maybe_apply_mock(
        self,
        scope_dirs: list[str],
        session_id: str,
    ) -> "AgentResponse | None":
        """P5 C37: PROVIDER_MOCK_<NAME> env-hook handler.

        Returns an AgentResponse (mock success path), raises ProviderError
        (mock failure path), or returns None (no mock — caller proceeds
        with the real subprocess invocation).

        Modes (env value):
          fail_always       — every call raises ProviderError
          fail_after_<N>    — after N successful mock returns, raise
                              ProviderError on the (N+1)-th call
          evil_write        — write a sentinel file OUTSIDE scope_dirs[0]
                              (in cwd) so a downstream check_scope catches
                              the leak; returns success otherwise
        """
        env_var = f"PROVIDER_MOCK_{self.name.upper()}"
        mode = os.environ.get(env_var)
        if not mode:
            return None

        if mode == "fail_always":
            raise ProviderError(
                f"{self.name} PROVIDER_MOCK={mode} simulated failure"
            )

        if mode.startswith("fail_after_"):
            try:
                n = int(mode.removeprefix("fail_after_"))
            except ValueError as exc:
                raise ValueError(
                    f"invalid {env_var} value {mode!r}: "
                    "expected fail_after_<integer>"
                ) from exc
            self._mock_call_count += 1
            if self._mock_call_count > n:
                raise ProviderError(
                    f"{self.name} PROVIDER_MOCK={mode} "
                    f"simulated failure on call #{self._mock_call_count}"
                )
            return AgentResponse(
                output=f"[mock {self.name} call #{self._mock_call_count}]",
                session_id=session_id,
                exit_code=0,
                extra={"mock_mode": mode, "call_count": self._mock_call_count},
            )

        if mode == "evil_write":
            # Write a sentinel file outside scope_dirs[0] (the staging dir).
            # The path is the parent dir of staging — guaranteed outside
            # whatever the FallbackChain's validate_scope considers "in scope".
            #
            # Root-corner-case caveat (C37 R3 LOW-2): if staging IS the
            # filesystem root (`Path("/").parent == Path("/")`), the
            # fallback writes the sentinel inside staging, which means
            # validate_scope can NOT detect it as a leak. This degenerate
            # case never occurs under pytest tmp_path / production
            # Problems/<p>/Goals/<id>_<slug>/Staging/<sess> layout
            # (staging is always 5+ levels deep), so it's documented but
            # not raised — operator's responsibility to never use the FS
            # root as a staging dir.
            if not scope_dirs:
                raise ProviderError(
                    f"{self.name} PROVIDER_MOCK={mode} requires scope_dirs"
                )
            staging = Path(scope_dirs[0])
            target_dir = staging.parent if staging.parent != staging else staging
            target = target_dir / f"EVIL_{self.name}_{session_id[:8]}.txt"
            target.write_text(
                f"PROVIDER_MOCK={mode} from {self.name}\n",
                encoding="utf-8",
            )
            return AgentResponse(
                output=f"[mock {self.name} evil_write -> {target}]",
                session_id=session_id,
                exit_code=0,
                extra={"mock_mode": mode, "evil_path": str(target)},
            )

        raise ValueError(
            f"unknown {env_var} value {mode!r}: "
            "expected fail_always | fail_after_<N> | evil_write"
        )


# ---------------------------------------------------------------------------
# Framework model defaults (two-layer config)
# ---------------------------------------------------------------------------

FRAMEWORK_MODEL_DEFAULTS: dict[str, str] = {
    "builder.tactic_llm": "haiku",
    "backward.agent": "sonnet",
    "refuter.agent": "sonnet",
    # P7 C50: Strategist defaults to opus per architecture_pipelines.md §5
    # (heavy inventory reasoning + decision schema authoring; spike-029 will
    # decide whether to keep this default).
    "strategist.agent": "opus",
    # P7 C52/C53: Forward / Generalizer agents per architecture_pipelines.md
    # §4/§8 (statement authoring; sonnet per spec recommendation).
    "forward.agent": "sonnet",
    "generalizer.agent": "sonnet",
}


# ---------------------------------------------------------------------------
# ModelResolver — two-layer lookup
# ---------------------------------------------------------------------------

class ModelResolver:
    """Resolve model tier for a given pipeline stage.

    Layer 1 (highest priority): Problem META.md models dict
    Layer 2: framework FRAMEWORK_MODEL_DEFAULTS

    Strategist override (third layer)留P7.
    """

    def __init__(self, meta_models: dict[str, str] | None = None) -> None:
        # meta_models: parsed from META.md models: section; e.g.
        #   {"backward.agent": "opus", "builder.tactic_llm": "sonnet"}
        self._meta: dict[str, str] = meta_models or {}

    def resolve(self, pipeline_kind: str, agent_stage: str) -> str:
        """Return model tier for the given pipeline + stage combination.

        pipeline_kind: 'builder' | 'backward' | ...
        agent_stage:   'tactic_llm' | 'agent' | ...
        """
        key = f"{pipeline_kind}.{agent_stage}"
        if key in self._meta:
            return self._meta[key]
        if key in FRAMEWORK_MODEL_DEFAULTS:
            return FRAMEWORK_MODEL_DEFAULTS[key]
        raise KeyError(
            f"No model default for '{key}'. "
            "Add it to FRAMEWORK_MODEL_DEFAULTS or Problem META.md models:."
        )


# ---------------------------------------------------------------------------
# FallbackChain — P2 single-entry
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Raised by a Provider when the subprocess fails unrecoverably."""


class FallbackChain:
    """Execute invoke() through an ordered list of providers.

    P2: single-entry list [claude].
    P5: extend to [claude, gemini, codex] with per-provider retry.

    Retry logic (per provider):
      - Up to n_retry attempts.
      - After each successful invoke() call, validate_scope() is checked.
      - Scope violation → retry the same provider.
      - ProviderError or timeout → retry the same provider.
      - Provider exhausted → move to next provider in chain (P5).
      - All providers exhausted → return outcome='exhausted'.
    """

    def __init__(
        self,
        providers: list[Provider],
        n_retry: int = 10,
        validate_scope: Any = None,
    ) -> None:
        if not providers:
            raise ValueError("FallbackChain requires at least one provider.")
        self.providers = providers
        self.n_retry = n_retry
        # validate_scope(staging_dir, session_id) -> bool
        # If None, scope validation is skipped (useful in tests).
        self._validate_scope = validate_scope

    def run(
        self,
        model_tier: str,
        prompt: str,
        scope_dirs: list[str],
        session_id: str,
        staging_dir: str | None = None,
        *,
        cwd: str | None = None,
    ) -> tuple[AgentResponse | None, str]:
        """Run the chain.

        Returns (response, outcome) where outcome is:
          'success'   – valid response obtained
          'exhausted' – all providers / retries failed

        P7 演習 fix (FallbackChain session_id collision): claude CLI
        rejects --session-id values that have ever been used. The original
        loop reused the caller-supplied `session_id` across every
        provider × n_retry call, so the second invoke inside the chain
        always failed with "Session ID ... is already in use" regardless
        of why the first attempt failed (ProviderError, scope-fail, etc.).
        Patch 11 fixed retries at the Backward._run_loop layer (outer
        max_retries) but not inside the chain.

        Mint a fresh per-invoke session_id derived from the pipeline
        session_id. The base session_id is still echoed back via
        AgentResponse.session_id (provider's responsibility) so pipeline-
        level tracing is preserved; per-invoke IDs are only used to keep
        the claude CLI happy.
        """
        for provider_idx, provider in enumerate(self.providers):
            for attempt in range(self.n_retry):
                # Fresh sub-session per claude CLI call; suffix encodes
                # which provider/attempt for forensic log readability.
                # Truncate base UUID to keep total length reasonable.
                base = session_id[:8] if len(session_id) >= 8 else session_id
                invoke_session_id = (
                    f"{base}-{provider.name}-{provider_idx}-{attempt}-"
                    f"{uuid.uuid4().hex[:8]}"
                )
                try:
                    response = provider.invoke(
                        model_tier, prompt, scope_dirs, invoke_session_id,
                        cwd=cwd,
                    )
                except ProviderError:
                    continue

                if self._validate_scope is not None and staging_dir is not None:
                    if not self._validate_scope(staging_dir, invoke_session_id):
                        continue

                return response, "success"

        return None, "exhausted"
