"""LLM provider registry. Resolve provider by env at call time.

`ASTERISM_LLM_PROVIDER` (provider-wide default):
  'claude' (fallback)  — claude CLI subprocess
  'openai'             — OpenAI-compatible HTTP API (vLLM / Ollama /
                         LM Studio / Anthropic-via-proxy / etc.)
  'gemini'             — Google Gemini CLI subprocess (API-key /
                         enterprise Code Assist only: the individual
                         tiers were cut off 2026-06-18)
  'antigravity'        — Antigravity CLI (`agy`) subprocess; the
                         subscription-priced path to Gemini models

Per-pipeline overrides:
  `ASTERISM_BUILDER_PROVIDER` / `ASTERISM_BACKWARD_PROVIDER` take
  precedence when caller passes `kind=` (e.g. spawn_llm forwards its
  own `kind`). Lets a single daemon run mix providers — typical use
  is cheap-LLM Builder + strong-LLM Backward.

Each provider is a separate module so its dependencies and quirks
don't leak. Adding a new backend = adding one file + one branch here.
"""
from __future__ import annotations

import os

from ..core import config
from .base import LLMRequest, Provider


def get_provider(kind: str | None = None) -> Provider:
    """Return the provider for one agent invocation.

    Resolution order (per Tooling/config.get):
      1. `ASTERISM_<KIND>_PROVIDER` env (kind in {'builder','backward'})
      2. Asterism.yaml `<kind>.provider`
      3. `ASTERISM_LLM_PROVIDER` env (legacy)
      4. 'claude' (default)
    """
    if kind:
        name = config.get(
            f"{kind}.provider",
            env_var=f"ASTERISM_{kind.upper()}_PROVIDER",
            legacy_env=("ASTERISM_LLM_PROVIDER",),
            default="claude",
        )
    else:
        # No kind context (legacy path) — only env+default chain.
        name = os.environ.get("ASTERISM_LLM_PROVIDER", "claude")
    name = str(name).lower()
    if name == "claude":
        from .claude_cli import ClaudeCliProvider
        return ClaudeCliProvider()
    if name == "openai":
        from .openai_api import OpenAIProvider
        return OpenAIProvider()
    if name == "gemini":
        from .gemini_cli import GeminiCliProvider
        return GeminiCliProvider()
    if name in ("antigravity", "agy"):
        from .antigravity_cli import AntigravityCliProvider
        return AntigravityCliProvider()
    raise ValueError(f"unknown ASTERISM_LLM_PROVIDER={name!r}")


__all__ = ["LLMRequest", "Provider", "get_provider"]
