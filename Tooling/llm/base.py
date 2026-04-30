"""LLM provider abstract interface.

A Provider receives an `LLMRequest` describing a single agent invocation
and is responsible for: resolving model name, sandboxing, running the
inference, and writing outputs (PROPOSAL.md, patch.lean, new_*.lean)
into `attempts_dir`. The pipeline checks the directory contents
afterwards — providers don't return anything but the rc.

Return code convention (mirrors claude CLI):
  0   success (output files in attempts_dir; pipeline parses them)
  124 timeout
  127 dependency missing (CLI not on PATH / SDK not installed)
  other non-zero  agent error / API failure
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class LLMRequest:
    """Single agent invocation contract.

    Attributes:
      kind:         'backward' or 'builder' — selects prompt template +
                    expected output shape downstream.
      prompt_path:  prompt template file the provider should obey.
      problem_dir:  Problems/<problem>/ — read scope for the agent.
      attempts_dir: .attempts/<pid>/ — sandbox; agent writes outputs here.
                    Must already contain Context.md.
      timeout_sec:  hard wall-clock cap. Provider must enforce.
    """
    kind: str
    prompt_path: Path
    problem_dir: Path
    attempts_dir: Path
    timeout_sec: int


class Provider(Protocol):
    """All LLM backends implement this single method."""
    def spawn(self, req: LLMRequest) -> int: ...
