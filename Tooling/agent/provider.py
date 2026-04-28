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
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Framework model defaults (two-layer config)
# ---------------------------------------------------------------------------

FRAMEWORK_MODEL_DEFAULTS: dict[str, str] = {
    "builder.tactic_llm": "haiku",
    "backward.agent": "sonnet",
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
        """
        for provider in self.providers:
            for attempt in range(self.n_retry):
                try:
                    response = provider.invoke(
                        model_tier, prompt, scope_dirs, session_id, cwd=cwd
                    )
                except ProviderError:
                    continue

                if self._validate_scope is not None and staging_dir is not None:
                    if not self._validate_scope(staging_dir, session_id):
                        continue

                return response, "success"

        return None, "exhausted"
