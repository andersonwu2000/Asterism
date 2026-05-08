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
  128 stuck thinking — watchdog killed spawn after >N min without any
      tool_use event in the session jsonl. Distinct from 124 (full
      wall hit) so the retry helper can route to a tight-budget
      rescue spawn rather than a regular retry.
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
    STUCK_THINKING = 128


# Rescue spawn budget (seconds). Cross-referenced by:
#   - claude_cli._watchdog: wall-clock kill threshold = req.timeout_sec
#     minus this, so the helper has a guaranteed window for rescue.
#   - agent.spawn_llm / pipeline callers: timeout_sec_override on the
#     rescue spawn itself. Keeping both sides on one constant prevents
#     the wall_cap and rescue timeout from drifting apart.
# Tunable by editing here only — every consumer reads this name.
RESCUE_BUDGET_SEC = 180


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
                    apply_edit / goal_at / errors_at via the long-
                    living `Tooling.lsp_gateway` HTTP server). Builder
                    + Backward pipelines set this; Reflection leaves
                    it None.
      is_rescue:    True when this is a stuck-thinking rescue spawn —
                    triggered after the watchdog kills a prior spawn
                    that produced no tool_use for too long. The
                    provider should: (1) skip its watchdog (rescue is
                    already short), (2) use the rescue prompt
                    inline (no prompt_path template), (3) honour the
                    tight timeout passed in `timeout_sec`. Mutually
                    exclusive with is_postmortem.
      rescue_prompt: When `is_rescue=True`, the inline force-ship
                    prompt to send to the resumed session (no template
                    rendering). Ignored when is_rescue=False.
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
    is_rescue: bool = False
    rescue_prompt: str | None = None


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
