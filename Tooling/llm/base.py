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
  126 quota exhausted (gemini free-tier limit)
  127 dependency missing (CLI not on PATH / SDK not installed)
  128 stuck thinking — watchdog killed spawn after >N min without any
      tool_use event in the session jsonl. Distinct from 124 (full
      wall hit) so the retry helper can route to a tight-budget
      rescue spawn rather than a regular retry.
  129 shutdown — dispatcher requested abort (budget exceeded / gateway
      permanently down). spawn_llm short-circuits without invoking the
      CLI; the retry helper treats it as terminal-no-retry so the
      worker thread exits in seconds instead of waiting through the
      remaining retry budget × subprocess_timeout.
  other non-zero  agent error / API failure
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Protocol


def which_launchable(name: "str") -> "str | None":
    """`shutil.which`, minus the Windows trap that costs a whole spawn.

    An npm-installed CLI puts TWO files on PATH: `foo` (a POSIX shell
    script, for Git Bash) and `foo.cmd` (for Windows). `shutil.which`
    returns the extensionless one — and `CreateProcess` cannot run it:
    `[WinError 193] %1 is not a valid Win32 application`, raised at
    Popen, so the pipeline sees a worker exception rather than anything
    resembling "the CLI is not launchable".

    MEASURED on this machine 2026-08-12: `codex`, `gemini` and `npm`
    itself all resolve to the extensionless shim; `claude` and `agy`
    happen to be `.EXE` today, which is the only reason this never bit
    before — and `claude_cli.resolve_claude_executable` already carries
    an `npm/claude.cmd` fallback, so a machine that installed claude
    through npm is one `which` away from the same failure.

    So: try the PATHEXT spellings first and accept the bare name only
    when it is itself launchable (a real `.exe` found under its own
    name, or any name on POSIX).
    """
    if sys.platform != "win32":
        return shutil.which(name)
    exts = [e for e in os.environ.get("PATHEXT", "").split(os.pathsep) if e]
    for ext in exts:
        found = shutil.which(name + ext)
        if found:
            return found
    found = shutil.which(name)
    if found and Path(found).suffix.upper() in {e.upper() for e in exts}:
        return found
    return None


#: The directory name every provider's rescued transcripts live under,
#: one level below `.asterism/`. Providers pick their own leaf name.
ATTEMPTS_DIRNAME = ".attempts"


def transcript_dest(attempts_dir: "Path | str", leaf: str) -> "Path | None":
    """`<ws>/.asterism/<leaf>/<path under .attempts>`, or None.

    ANCHORED, NOT COUNTED. Two providers shipped
    `attempts_dir.parent.parent` as "the workspace", which is right only
    for `<ws>/.attempts/<pid>`. The Adversary runs one level deeper
    (`<pid>/adversary/r1`), so on 2026-08-15 a rescued transcript was
    written to `<ws>/.attempts/<pid>/.asterism/...` — inside the tree
    the rescue exists to escape — and every pipeline's first round
    claimed the same folder name `r1`.

    Carrying the whole path below `.attempts` fixes both at once: the
    workspace is the parent of the `.attempts` ancestor, and the id is
    the rest, so rounds nest instead of colliding.

    None when there is no `.attempts` ancestor. A caller that cannot
    locate the workspace must say so, not guess a level."""
    p = Path(attempts_dir).resolve()
    for parent in p.parents:
        if parent.name == ATTEMPTS_DIRNAME:
            return parent.parent / ".asterism" / leaf / p.relative_to(parent)
    return None


class SpawnRC(IntEnum):
    """Typed names for the rc convention. Pipeline branches on
    `rc == SpawnRC.TIMEOUT` etc. instead of magic numbers, while
    providers can still return raw int (IntEnum compares equal to
    its underlying int)."""
    OK = 0
    TIMEOUT = 124
    STALE_SESSION = 125
    QUOTA_EXHAUSTED = 126
    MISSING_DEP = 127
    STUCK_THINKING = 128
    SHUTDOWN = 129


# Watchdog 2026-05-10 v4: trap_check_sec replaces rescue_timeout_sec
# as the primary watchdog config. Stage budgets are derived:
#   combined_takeover_budget = spawn_timeout - trap_check + postmortem
#   timeout_path_stage2_budget = spawn_timeout - trap_check
# Both consumers compute these directly from `dispatch.trap_check_sec`
# + `dispatch.spawn_timeout_sec` + `dispatch.postmortem_timeout_sec`,
# so no separate constant is exported here.


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
      trap_check_sec: optional per-spawn override of the watchdog's
                    `dispatch.trap_check_sec` (the single-shot mid-thinking
                    silence check). None = use the global config value. Set
                    larger for a kind whose thinking time scales with its
                    input size (classify reasons over N kept-decls in one
                    block) so a legitimately long think is not mistaken for a
                    trap. Other kinds leave it None.
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
      retry_reason:  the prior attempt's failure_reason (e.g.
                    `agent_stuck_thinking`). Lets the provider frame the
                    retry honestly — a thinking-trap death is not a lake
                    error (rc=0), so the prompt must not claim "failed
                    lake build". None for the first attempt / unknown.
      is_postmortem: postmortem call after a main-spawn timeout.
                    Uses --resume so the prior turn's session memory is
                    intact, loads `prompt_path` verbatim (a short prompt
                    asking the agent to summarize state + blockers into
                    `_progress.md` and exit). Mutually exclusive with
                    is_retry. Providers without session support skip.
      continuation: staged-pipeline work turn (Formalizer): the intake
                    turn opened this session; resume it and send the
                    work-stage `prompt_path` verbatim (rendered). Unlike
                    is_postmortem this is a FULL work attempt — normal
                    timeout and watchdog apply. Mutually exclusive with
                    is_retry / is_postmortem.
      mcp_config_path: Optional path to an MCP config JSON file. When
                    set and the provider supports it (claude CLI),
                    the spawn includes `--mcp-config <path>` so the
                    agent gets MCP-backed tools (e.g. LSP-driven
                    apply_edit / goal_at / errors_at via the long-
                    living `Tooling.lsp_gateway` HTTP server). Builder
                    + Backward pipelines set this; Reflection leaves
                    it None.
      extra_read_dirs: additional directories the spawn may Read/Grep
                    beyond its kind's standard scope. Adversary sets
                    this to the problem's landed `proofs/` (2026-08-04,
                    user call): the projection's cited-file staging +
                    cap truncated the judge's evidence late in a big
                    problem; landed proofs are ground truth, not
                    strategist narrative, so reading them in place
                    widens no independence boundary. Read-only — the
                    write fence is untouched. Providers whose reads are
                    already workspace-wide (agy) need no rendering.
      inline_prompt: When set, the provider sends this string verbatim
                    as the `-p` payload to claude (bypasses the normal
                    template loading from `prompt_path`). Used for
                    fresh-rescue stage 2 / stage 3 where the helper
                    crafts the prompt with the broken session's jsonl
                    path baked in. The session is cold (`--session-id
                    <fresh>`), not resumed. Watchdog is skipped for
                    these spawns (the budget is short — they're
                    rescue/postmortem replacements, not full attempts).
                    Mutually exclusive with is_postmortem / is_retry.
    """
    kind: str
    prompt_path: Path
    problem_dir: Path
    attempts_dir: Path
    timeout_sec: int
    trap_check_sec: int | None = None
    session_id: str | None = None
    is_retry: bool = False
    retry_context: str | None = None
    retry_reason: str | None = None
    is_postmortem: bool = False
    continuation: bool = False
    mcp_config_path: Path | None = None
    inline_prompt: str | None = None
    extra_read_dirs: "tuple[Path, ...] | None" = None
    # Conditional-block flags for the prompt template (D8 2026-07-24):
    # `<!-- #if name -->…<!-- #endif -->` blocks render only when
    # flags[name] is truthy; absent flag (or None) keeps the block.
    prompt_flags: "dict[str, bool] | None" = None


class Provider(Protocol):
    """All LLM backends implement this one method.

    `spawn` runs a full agent invocation that writes outputs to disk.

    There used to be a second, `complete_text` — a one-shot
    text-in/text-out call kept "for future use" after the per-problem
    playbook flow that needed it was retired. It went four providers
    deep with zero call sites, and its claude implementation still
    resolved a model through `builder`, a config key the v33 Formalizer
    merge had already retired. That is the cost of a speculative
    interface method: every new backend implements it, nobody calls it,
    and it rots where no test can notice. A future need can add it back
    with a caller attached.
    """
    def spawn(self, req: LLMRequest) -> int: ...
