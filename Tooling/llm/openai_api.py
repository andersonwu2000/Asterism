"""OpenAI-compatible HTTP API provider — vLLM, Ollama, LM Studio, etc.

Placeholder. Single-shot completion model means the agent cannot
multi-turn explore (no Bash / Read tools), so prompts under
`Tooling/prompts/` need single-shot variants before this provider
becomes usable. Tracked in step 2 of the LLM-provider extraction
work.

Until then, selecting `ASTERISM_LLM_PROVIDER=openai` raises a clear
NotImplementedError on instantiation rather than silently falling
back.
"""
from __future__ import annotations

from .base import LLMRequest


class OpenAIProvider:
    def __init__(self) -> None:
        raise NotImplementedError(
            "OpenAI-compatible provider is a step-2 task; not yet "
            "implemented. Set ASTERISM_LLM_PROVIDER=claude (default) "
            "for now."
        )

    def spawn(self, req: LLMRequest) -> int:  # pragma: no cover
        raise NotImplementedError
