"""Claude CLI provider (P2).

Wraps `claude -p ...` subprocess with:
  - --add-dir for each scope_dir (read+write isolation)
  - --permission-mode acceptEdits (required for writes outside default CWD)
  - --session-id for session continuity (pipeline-level unique)
  - git status backstop: post-invoke check that no files outside staging were modified
  - session jsonl GC: delete ~/.claude/projects/**/<session_id>*.jsonl on pipeline end

Key design notes (from spike-004):
  - CWD of subprocess = staging_dir (first scope_dirs entry), NOT D:/Asterism.
    This makes CWD's implicit acceptEdits scope align with --add-dir scope.
  - git status is run relative to D:/Asterism repo root to catch any leaks.
  - --permission-mode acceptEdits is mandatory; omitting it blocks all writes
    even inside --add-dir directories when using -p (non-interactive) mode.

Subprocess invocation pattern:
  claude -p "$PROMPT" \\
      --add-dir <dir1> --add-dir <dir2> ... \\
      --permission-mode acceptEdits \\
      --session-id <session_id> \\
      < /dev/null 2>&1

  stdin redirect: avoids "Warning: no stdin data received in 3s"
  2>&1:           ensures stderr is captured in stdout (claude writes to both)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from Tooling.agent.provider import AgentResponse, Provider, ProviderError


# claude CLI tier → model id
CLAUDE_MODEL_MAP: dict[str, str] = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-7",
}

# Timeout for a single claude invocation (seconds)
DEFAULT_INVOKE_TIMEOUT: float = 600.0

# Timeout for the git status backstop check (seconds)
_GIT_TIMEOUT: float = 30.0

# Pattern for modified/added/deleted files in `git status --porcelain`
_PORCELAIN_CHANGED = re.compile(r"^[MADRCU?!]", re.MULTILINE)


class ClaudeProvider(Provider):
    """LLM provider backed by the `claude` CLI (Claude Code)."""

    name = "claude"
    model_map = CLAUDE_MODEL_MAP

    def __init__(
        self,
        *,
        claude_bin: str = "claude",
        invoke_timeout: float = DEFAULT_INVOKE_TIMEOUT,
        repo_root: str | Path | None = None,
    ) -> None:
        """
        Args:
            claude_bin:       Path / name of the claude CLI binary.
            invoke_timeout:   Seconds before the subprocess is killed.
            repo_root:        Root of the git repo used by the git-status backstop.
                              Defaults to CWD at construction time.
        """
        self.claude_bin = claude_bin
        self.invoke_timeout = invoke_timeout
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    def invoke(
        self,
        model_tier: str,
        prompt: str,
        scope_dirs: list[str],
        session_id: str,
        *,
        cwd: str | None = None,
    ) -> AgentResponse:
        """Run one claude agent turn.

        CWD is set to the first scope_dirs entry (staging dir) unless
        explicitly overridden, so the claude CLI's implicit CWD scope
        aligns with --add-dir scope (spike-004 recommendation).
        """
        if not scope_dirs:
            raise ProviderError("scope_dirs must not be empty")

        model_id = self.resolve_model_id(model_tier)
        effective_cwd = cwd or scope_dirs[0]

        cmd = self._build_cmd(model_id, prompt, scope_dirs, session_id)

        try:
            result = subprocess.run(
                cmd,
                capture_output=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,   # merge stderr into stdout (2>&1)
                stdin=subprocess.DEVNULL,   # avoid "no stdin data" warning
                cwd=effective_cwd,
                timeout=self.invoke_timeout,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            # subprocess.run() already killed the child; just surface the error.
            raise ProviderError(f"claude invocation timed out after {self.invoke_timeout}s") from exc
        except FileNotFoundError as exc:
            raise ProviderError(f"claude binary not found: {self.claude_bin!r}") from exc

        output = result.stdout or ""
        return AgentResponse(
            output=output,
            session_id=session_id,
            exit_code=result.returncode,
            extra={"model_id": model_id, "cmd": cmd},
        )

    def gc_session(self, session_id: str) -> None:
        """Delete claude session jsonl files for the given session_id.

        Claude Code stores session transcripts at:
          ~/.claude/projects/<encoded_path>/<session_id>.jsonl

        We scan all projects dirs and remove any file whose stem starts with
        session_id.  Silently skips if files are not found.
        """
        claude_dir = Path.home() / ".claude" / "projects"
        if not claude_dir.exists():
            return
        pattern = f"{session_id}*.jsonl"
        for jsonl_file in claude_dir.rglob(pattern):
            try:
                jsonl_file.unlink(missing_ok=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # git status backstop
    # ------------------------------------------------------------------

    def check_scope(self, staging_dir: str | Path, session_id: str | None = None) -> bool:
        """Return True if no files outside staging_dir were modified.

        Runs `git status --porcelain` from repo_root and checks that every
        changed path is under staging_dir.  Untracked files outside staging
        are also flagged.

        This is the per-provider 'last line of defence' required by impl §6.5.
        """
        staging = Path(staging_dir).resolve()

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.repo_root,
                timeout=_GIT_TIMEOUT,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # If git is unavailable, fail safe (deny).
            return False

        if not result.stdout.strip():
            return True  # clean working tree → pass

        outside: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            # porcelain v1: "XY path" or "XY orig -> path"
            parts = line[3:].strip()
            path_str = parts.split(" -> ")[-1].strip().strip('"')
            abs_path = (self.repo_root / path_str).resolve()
            try:
                abs_path.relative_to(staging)
            except ValueError:
                outside.append(str(abs_path))

        return len(outside) == 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_cmd(
        self,
        model_id: str,
        prompt: str,
        scope_dirs: list[str],
        session_id: str,
    ) -> list[str]:
        """Assemble the claude CLI argv list."""
        cmd: list[str] = [
            self.claude_bin,
            "-p", prompt,
            "--model", model_id,
            "--permission-mode", "acceptEdits",
            "--session-id", session_id,
        ]
        for d in scope_dirs:
            cmd += ["--add-dir", str(d)]
        return cmd


# ------------------------------------------------------------------
# Process-tree kill helper (Windows + POSIX)
# ------------------------------------------------------------------

def _kill_tree(proc: subprocess.Popen | None) -> None:
    """Kill a process and all its children (best-effort)."""
    if proc is None:
        return
    try:
        import psutil
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except Exception:
        # Fallback: platform kill
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            os.killpg(os.getpgid(proc.pid), 9)
