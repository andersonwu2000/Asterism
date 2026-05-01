"""LLM provider registry. Resolve provider by env at call time.

`ASTERISM_LLM_PROVIDER`:
  'claude' (default) — claude CLI subprocess
  'openai'           — OpenAI-compatible HTTP API (vLLM / Ollama / LM
                       Studio / Anthropic-via-proxy / etc.)
  'gemini'           — Google Gemini CLI subprocess (Code Assist
                       free-tier auth; flash model practical, F38)

Each provider is a separate module so its dependencies and quirks
don't leak. Adding a new backend = adding one file + one branch here.
"""
from __future__ import annotations

import os

from .base import LLMRequest, Provider


def get_provider() -> Provider:
    name = os.environ.get("ASTERISM_LLM_PROVIDER", "claude").lower()
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
