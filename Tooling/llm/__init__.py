"""LLM provider registry. Resolve provider by env at call time.

`ASTERISM_LLM_PROVIDER` (provider-wide default):
  'claude' (fallback)  — claude CLI subprocess
  'openai'             — OpenAI-compatible HTTP API (vLLM / Ollama /
                         LM Studio / Anthropic-via-proxy / etc.)
  'gemini'             — Google Gemini CLI subprocess (Code Assist
                         free-tier auth; flash model practical, F38)

F39 — per-pipeline overrides:
  `ASTERISM_BUILDER_PROVIDER` / `ASTERISM_BACKWARD_PROVIDER` take
  precedence when caller passes `kind=` (e.g. spawn_llm forwards its
  own `kind`). Lets a single daemon run mix providers — typical use
  is cheap-LLM Builder + strong-LLM Backward.

Each provider is a separate module so its dependencies and quirks
don't leak. Adding a new backend = adding one file + one branch here.
"""
from __future__ import annotations

import os

from .base import LLMRequest, Provider


def get_provider(kind: str | None = None) -> Provider:
    """Return the provider for one agent invocation.

    Resolution order (F39):
      1. `ASTERISM_<KIND>_PROVIDER` (kind in {'builder','backward'})
      2. `ASTERISM_LLM_PROVIDER`
      3. 'claude' (default)
    """
    name = None
    if kind:
        name = os.environ.get(f"ASTERISM_{kind.upper()}_PROVIDER")
    if not name:
        name = os.environ.get("ASTERISM_LLM_PROVIDER", "claude")
    name = name.lower()
    if name == "claude":
        from .claude_cli import ClaudeCliProvider
        return ClaudeCliProvider()
    if name == "openai":
        from .openai_api import OpenAIProvider
        return OpenAIProvider()
    if name == "gemini":
        from .gemini_cli import GeminiCliProvider
        return GeminiCliProvider()
    raise ValueError(f"unknown ASTERISM_LLM_PROVIDER={name!r}")


__all__ = ["LLMRequest", "Provider", "get_provider"]
