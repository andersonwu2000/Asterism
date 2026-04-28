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

import subprocess
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
        # P6.x patch 7: snapshot of git status BEFORE invoke (keyed by
        # resolved staging_dir). check_scope compares post-invoke status
        # against this baseline so pre-existing working-tree changes do
        # not count as scope violations.
        self._scope_baseline: dict[str, set[str]] = {}

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

        # P5 C37: PROVIDER_MOCK_CLAUDE env hook (test-only).
        mock_resp = self._maybe_apply_mock(scope_dirs, session_id)
        if mock_resp is not None:
            return mock_resp

        model_id = self.resolve_model_id(model_tier)
        effective_cwd = cwd or scope_dirs[0]

        # P6.x patch 7: snapshot baseline before invoke so check_scope can
        # compute delta. Key by resolved staging_dir.
        staging_key = str(Path(scope_dirs[0]).resolve())
        self._scope_baseline[staging_key] = self._capture_git_status()

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
                text=True, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            # subprocess.run() already killed the child; just surface the error.
            raise ProviderError(f"claude invocation timed out after {self.invoke_timeout}s") from exc
        except FileNotFoundError as exc:
            raise ProviderError(f"claude binary not found: {self.claude_bin!r}") from exc

        output = result.stdout or ""
        # Redact the prompt from the argv echo so AgentResponse.extra
        # stays small if a caller serializes it (P2.C13 commit batch /
        # events row).  The full prompt is recoverable from session jsonl.
        argv_redacted = ["<PROMPT>" if c is prompt else c for c in cmd]
        return AgentResponse(
            output=output,
            session_id=session_id,
            exit_code=result.returncode,
            extra={"model_id": model_id, "argv": argv_redacted},
        )

    def gc_session(self, session_id: str) -> None:
        """Delete claude session jsonl files for the given session_id.

        Claude Code stores session transcripts at:
          ~/.claude/projects/<encoded_path>/<session_id>.jsonl

        We scan all projects dirs and remove any file whose stem starts with
        session_id.  The trailing `*` in the glob is intentional: it catches
        claude CLI variants such as fork / branched session jsonls (e.g.
        `<session_id>-fork.jsonl`).  Silently skips if files are not found.

        Raises ValueError on empty session_id — empty string would expand to
        `*.jsonl` and wipe every session under ~/.claude/projects/.
        """
        if not session_id:
            raise ValueError("session_id must be non-empty")
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

        `session_id` is unused here but kept in the signature to match
        FallbackChain.validate_scope(staging_dir, session_id) callable.
        Other providers (gemini / codex, P5) may use it for per-session
        tracking.

        This is the per-provider 'last line of defence' required by impl §6.5.
        """
        staging = Path(staging_dir).resolve()

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,

                encoding="utf-8", errors="replace",
                cwd=self.repo_root,
                timeout=_GIT_TIMEOUT,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # If git is unavailable, fail safe (deny).
            return False

        # P6.x patch 7: filter against baseline snapshot taken before invoke.
        # Only NEW status entries (post-invoke) count as scope violations.
        current_lines = {
            ln.rstrip() for ln in result.stdout.splitlines() if ln.strip()
        }
        baseline = self._scope_baseline.pop(str(staging), set())
        delta_lines = current_lines - baseline

        if not delta_lines:
            return True  # no new changes since invoke

        outside: list[str] = []
        for line in delta_lines:
            # porcelain v1: "XY path" or "XY orig -> path"
            parts = line[3:].strip()
            path_str = parts.split(" -> ")[-1].strip().strip('"')
            abs_path = (self.repo_root / path_str).resolve()
            try:
                abs_path.relative_to(staging)
            except ValueError:
                outside.append(str(abs_path))

        return len(outside) == 0

    def _capture_git_status(self) -> set[str]:
        """P6.x patch 7: capture git status --porcelain output as a set of
        lines for baseline comparison. Empty set on git failure (the
        check_scope path will still run and treat current state as the
        delta — fail-safe upstream)."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                cwd=self.repo_root,
                timeout=_GIT_TIMEOUT,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return set()
        return {
            ln.rstrip() for ln in result.stdout.splitlines() if ln.strip()
        }

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
