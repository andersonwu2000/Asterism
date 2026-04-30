"""Claude CLI provider — subprocess to `claude` executable.

Inherits the existing claude CLI workflow: `--add-dir` for sandboxing,
`--no-session-persistence`, `acceptEdits` permission, text output.
The agent reads `Context.md` and the prompt template from disk and
writes outputs back to `attempts_dir/`.

Model selection: `ASTERISM_AGENT_MODEL` env (default: Sonnet).
"""
from __future__ import annotations

import os
import shutil
import subprocess

from .base import LLMRequest


DEFAULT_MODEL = "claude-sonnet-4-6"


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
        auxiliary calls (idiom extract / curate)."""
        if not shutil.which("claude"):
            return None
        model = os.environ.get("ASTERISM_AGENT_MODEL", DEFAULT_MODEL)
        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--no-session-persistence",
            "--output-format", "text",
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
