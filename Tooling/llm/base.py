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
  125 stale session (claude --resume on a GC'd session UUID)
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
      session_id:   claude CLI session UUID. Caller-controlled. First
                    attempt uses --session-id <id> to pin the session
                    id; subsequent in-pipeline retries use --resume
                    <id> on the same UUID. Providers without session
                    support (OpenAI HTTP) ignore this field.
      is_retry:     True when caller is reusing session_id from the
                    prior in-pipeline attempt. Provider may switch to
                    a shorter prompt (assumes prior turn's context
                    lives in session memory).
      retry_context: short text (typically the smart-truncated lake
                    error from the prior in-pipeline attempt) that
                    the provider inlines into the retry prompt. Lets
                    the agent see the error immediately without a
                    Read tool round-trip. Ignored when is_retry=False.
      is_postmortem: F55 — postmortem call after a main-spawn timeout.
                    Uses --resume so the prior turn's session memory is
                    intact, loads `prompt_path` verbatim (a short prompt
                    asking the agent to summarize state + blockers into
                    `_progress.md` and exit). Mutually exclusive with
                    is_retry. Providers without session support skip.
      mcp_config_path: Optional path to an MCP config JSON file. When
                    set and the provider supports it (claude CLI),
                    the spawn includes `--mcp-config <path>` so the
                    agent gets MCP-backed tools (e.g. LSP-driven
                    apply_edit / goal_at / errors_at via
                    `Tooling.lsp_mcp_server`). Builder pipeline sets
                    this; other kinds (Backward / Reflection) leave
                    it None.
    """
    kind: str
    prompt_path: Path
    problem_dir: Path
    attempts_dir: Path
    timeout_sec: int
    session_id: str | None = None
    is_retry: bool = False
    retry_context: str | None = None
    is_postmortem: bool = False
    mcp_config_path: Path | None = None


class Provider(Protocol):
    """All LLM backends implement these two methods.

    `spawn` runs a full agent invocation that writes outputs to disk
    (Backward / Builder / Verify). `complete_text` is a one-shot
    text-in/text-out call retained for short auxiliary tasks where
    file IO would be overkill (no current call sites since the F22
    playbook flow was retired in favor of inline goal annotations,
    but the surface stays in place for future use).
    """
    def spawn(self, req: LLMRequest) -> int: ...

    def complete_text(self, *, prompt: str, timeout_sec: int = 60) -> str | None:
        """One-shot completion. Returns response text or None on
        failure (provider unavailable, timeout, parse error)."""
        ...
