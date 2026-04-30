"""Claude CLI provider — subprocess to `claude` executable.

Inherits the existing claude CLI workflow: `--add-dir` for sandboxing,
`--no-session-persistence`, `acceptEdits` permission, text output.
The agent reads `Context.md` and the prompt template from disk and
writes outputs back to `attempts_dir/`.

Model selection: `ASTERISM_AGENT_MODEL` env (default: Sonnet).

System-prompt trim (F27): direct measurement of the claude CLI 2.1
default vs the optimized flags below shows ~20.7K → ~7.8K prefix
tokens per call (-62%) on Sonnet. The 4 flags strip tool descriptions
Asterism doesn't use (Bash, Glob, Grep, WebFetch, WebSearch,
NotebookEdit, mcp__*), skip CLAUDE.md / auto-memory / settings load,
and stabilize per-machine sections so prompt caching reuses across
calls. Override the tool list via `ASTERISM_CLAUDE_TOOLS` if a future
flow needs a different surface.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from .base import LLMRequest


DEFAULT_MODEL = "claude-sonnet-4-6"

# Asterism's pipelines only ever need Read / Write / Edit. Backward,
# Builder, Verify each manipulate sandbox files; lemma signatures and
# stderr hints come pre-resolved by the framework (F9, F20). Override
# via env if a future use case needs more (e.g. Bash for ad-hoc shell).
DEFAULT_TOOLS = "Read Write Edit"


def _trim_flags() -> list[str]:
    """The four CLI flags that strip system-prompt overhead Asterism
    doesn't benefit from. Centralized so spawn() and complete_text()
    use the same trim consistently."""
    tools = os.environ.get("ASTERISM_CLAUDE_TOOLS", DEFAULT_TOOLS)
    return [
        "--tools", tools,
        "--setting-sources", "",
        "--disable-slash-commands",
        "--exclude-dynamic-system-prompt-sections",
    ]


class ClaudeCliProvider:
    def spawn(self, req: LLMRequest) -> int:
        if not shutil.which("claude"):
            print("[llm:claude] claude CLI not found; skipping spawn",
                  flush=True)
            return 127

        model = os.environ.get("ASTERISM_AGENT_MODEL", DEFAULT_MODEL)
        prompt = (
            f"{req.kind} task. Read agent prompt at {req.prompt_path} "
            f"and follow it exactly.\n"
            f"Read context at {req.attempts_dir}/Context.md.\n"
            f"Write output to {req.attempts_dir}/."
        )

        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--permission-mode", "acceptEdits",
            "--add-dir", str(req.problem_dir),
            "--add-dir", str(req.attempts_dir),
            "--no-session-persistence",
            "--output-format", "text",
            *_trim_flags(),
        ]
        try:
            r = subprocess.run(
                cmd, timeout=req.timeout_sec,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            return r.returncode
        except subprocess.TimeoutExpired:
            print(f"[llm:claude] timed out after {req.timeout_sec}s",
                  flush=True)
            return 124

    def complete_text(
        self, *, prompt: str, timeout_sec: int = 60,
    ) -> str | None:
        """One-shot completion via `claude -p <prompt>`. Captures
        stdout text rather than producing files. Used by F22 short
        auxiliary calls (idiom extract / curate). complete_text never
        invokes tools, but the same trim applies to the system prompt."""
        if not shutil.which("claude"):
            return None
        model = os.environ.get("ASTERISM_AGENT_MODEL", DEFAULT_MODEL)
        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--no-session-persistence",
            "--output-format", "text",
            *_trim_flags(),
        ]
        try:
            r = subprocess.run(
                cmd, timeout=timeout_sec,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                return None
            return r.stdout.strip()
        except subprocess.TimeoutExpired:
            return None
