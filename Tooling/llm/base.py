"""LLM provider abstract interface.

A Provider receives an `LLMRequest` describing a single agent invocation
and is responsible for: resolving model name, sandboxing, running the
inference, and writing outputs (PROPOSAL.md, patch.lean, new_*.lean)
into `attempts_dir`. The pipeline checks the directory contents
afterwards — providers don't return anything but the rc.

Return code convention (mirrors claude CLI; see SpawnRC enum below
for typed names — providers may return either int or SpawnRC since
SpawnRC is an IntEnum):
  0   success (output files in attempts_dir; pipeline parses them)
  124 timeout
  125 stale session (claude --resume on a GC'd session UUID, F33)
  126 quota exhausted (gemini free-tier limit, F38)
  127 dependency missing (CLI not on PATH / SDK not installed)
  other non-zero  agent error / API failure
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Protocol


class SpawnRC(IntEnum):
    """Typed names for the rc convention. P2-#3 — pipeline branches
    on `rc == SpawnRC.TIMEOUT` etc. instead of magic numbers, while
    providers can still return raw int (IntEnum compares equal to
    its underlying int)."""
    OK = 0
    TIMEOUT = 124
    STALE_SESSION = 125
    QUOTA_EXHAUSTED = 126
    MISSING_DEP = 127


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
      session_id:   F33 — claude CLI session UUID. Caller-controlled.
                    First attempt uses --session-id <id> to pin the
                    session id; retry attempts use --resume <id>.
                    Providers without session support (OpenAI HTTP)
                    ignore this field.
      is_retry:     F33 — True when caller is reusing session_id from
                    a prior attempt. Provider may switch to a shorter
                    prompt (assumes prior turn's context lives in the
                    session memory).
      retry_context: F33 — short text (typically the smart-truncated
                    lake error from the prior attempt) that the
                    provider inlines into the retry prompt. Replaces
                    a separate RETRY_NOTE.md file: the agent sees the
                    error immediately without needing a Read tool
                    round-trip. Ignored when is_retry=False.
    """
    kind: str
    prompt_path: Path
    problem_dir: Path
    attempts_dir: Path
    timeout_sec: int
    session_id: str | None = None
    is_retry: bool = False
    retry_context: str | None = None


class Provider(Protocol):
    """All LLM backends implement these two methods.

    `spawn` runs a full agent invocation that writes outputs to disk
    (Backward / Builder / Verify). `complete_text` is a one-shot
    text-in/text-out call used by short auxiliary tasks (F22 playbook
    idiom extraction + curation) where file IO would be overkill.
    """
    def spawn(self, req: LLMRequest) -> int: ...

    def complete_text(self, *, prompt: str, timeout_sec: int = 60) -> str | None:
        """One-shot completion. Returns response text or None on
        failure (provider unavailable, timeout, parse error)."""
        ...
