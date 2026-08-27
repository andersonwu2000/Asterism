"""LLM provider registry. Resolve provider by env at call time.

`ASTERISM_LLM_PROVIDER` (provider-wide default):
  'claude' (fallback)  — claude CLI subprocess
  'openai'             — OpenAI-compatible HTTP API (vLLM / Ollama /
                         LM Studio / Anthropic-via-proxy / etc.)
  'antigravity'        — Antigravity CLI (`agy`) subprocess; the
                         subscription-priced path to Gemini models
  ('gemini' retired 2026-08-28 — see the teaching refusal below)

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
        # Retired, not unknown — the name deserves a road sign. The
        # standalone Gemini CLI provider was a pre-MCP surface (no
        # framework tool plane, no session resume), never seated by
        # this workspace, and Google cut its individual tiers off
        # 2026-06-18.
        raise ValueError(
            "provider 'gemini' retired 2026-08-28: Gemini models run "
            "through provider 'antigravity' (the agy CLI, subscription "
            "path); an API key can front them via provider 'openai' "
            "with a compatible endpoint.")
    if name in ("antigravity", "agy"):
        from .antigravity_cli import AntigravityCliProvider
        return AntigravityCliProvider()
    if name == "codex":
        from .codex_cli import CodexCliProvider
        return CodexCliProvider()
    if name == "zen":
        # OpenCode Zen: the codex CLI pointed at the local translation
        # shim (Tooling/llm/zen_shim.py) — see codex_cli._render_config.
        from .codex_cli import CodexCliProvider
        return CodexCliProvider(flavor="zen")
    raise ValueError(f"unknown ASTERISM_LLM_PROVIDER={name!r}")


__all__ = ["LLMRequest", "Provider", "get_provider"]
