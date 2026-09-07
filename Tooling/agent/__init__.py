"""Agent package: WorkArea + LLM dispatch + Context.md compilation.

The `runtime` submodule holds the original `agent.py` content (WorkArea,
spawn_llm, helpers). Re-export at package level so callers can still
write `from Tooling.agent import WorkArea` without caring about the
internal split.
"""
from __future__ import annotations

from .runtime import (
    WorkArea,
    attempts_dir_for,
    new_pipeline_id,
    render_prompt_template,
    spawn_llm,
)

__all__ = [
    "WorkArea",
    "attempts_dir_for",
    "new_pipeline_id",
    "render_prompt_template",
    "spawn_llm",
]
