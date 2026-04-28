"""Codex CLI provider (P5 C36).

Wraps `codex exec ...` subprocess with provider-specific scope-isolation
mapping per spike-019 D-19-1 (as corrected by C34 R3 audit MED-1):
  - `codex exec` is the non-interactive subcommand (positional PROMPT)
  - `-C, --cd <DIR>` sets the working root (preferred over subprocess
    `cwd=` because codex's sandbox uses cwd as primary writable workspace)
  - `--add-dir <DIR>` adds extra writable directories — repeatable, same
    shape as claude's --add-dir (字面對齊)
  - `-s, --sandbox workspace-write` allows writes to cwd + --add-dir,
    blocks anything else
  - `--full-auto` is the alias for `--sandbox workspace-write` plus
    auto-execute (no per-tool approval prompts)
  - `-m, --model <id>` selects the model
  - git status backstop is preserved (model-independent fallback per
    spike-004; codex sandbox is stricter than claude/gemini, but the
    framework does not depend on provider sandbox correctness)

Differences from claude/gemini providers:
  - `codex exec` (subcommand), not direct `codex -p`
  - PROMPT is a positional arg of `codex exec`, not `-p <prompt>`
  - Sandbox mode is explicit (`workspace-write` + `--full-auto`); claude
    relies on --permission-mode acceptEdits, gemini on --approval-mode
    auto_edit
  - Session tracking: codex has session ids and resume but P5 C36 does
    not pass --session-id on fresh runs (mirrors gemini behaviour);
    gc_session is a no-op pending a P5.x review of session disk usage

Subprocess invocation pattern:
  codex exec "$PROMPT" \
      -C <p1> \
      --add-dir <p2> --add-dir <p3> ... \
      --sandbox workspace-write \
      --full-auto \
      -m <model_id> \
      < /dev/null 2>&1

Public API: CodexProvider (Provider subclass) + CODEX_MODEL_MAP dict.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from Tooling.agent.provider import AgentResponse, Provider, ProviderError


# Codex tier → model id (per spike-020 D-20-1: codex single-tier in P5;
# the full tier mapping waits for P5.x patch when codex tier semantics
# settle. All three tiers map to gpt-5 for now.)
CODEX_MODEL_MAP: dict[str, str] = {
    "haiku":  "gpt-5",
    "sonnet": "gpt-5",
    "opus":   "gpt-5",
}

DEFAULT_INVOKE_TIMEOUT: float = 600.0
_GIT_TIMEOUT: float = 30.0


class CodexProvider(Provider):
    """LLM provider backed by the `codex exec` CLI."""

    name = "codex"
    model_map = CODEX_MODEL_MAP

    def __init__(
        self,
        *,
        codex_bin: str = "codex",
        invoke_timeout: float = DEFAULT_INVOKE_TIMEOUT,
        repo_root: str | Path | None = None,
    ) -> None:
        self.codex_bin = codex_bin
        self.invoke_timeout = invoke_timeout
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()

    def invoke(
        self,
        model_tier: str,
        prompt: str,
        scope_dirs: list[str],
        session_id: str,
        *,
        cwd: str | None = None,
    ) -> AgentResponse:
        if not scope_dirs:
            raise ProviderError("scope_dirs must not be empty")

        # P5 C37: PROVIDER_MOCK_CODEX env hook (test-only).
        mock_resp = self._maybe_apply_mock(scope_dirs, session_id)
        if mock_resp is not None:
            return mock_resp

        model_id = self.resolve_model_id(model_tier)
        effective_cwd = cwd or scope_dirs[0]
        cmd = self._build_cmd(model_id, prompt, scope_dirs)

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=effective_cwd,
                timeout=self.invoke_timeout,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(
                f"codex invocation timed out after {self.invoke_timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise ProviderError(
                f"codex binary not found: {self.codex_bin!r}"
            ) from exc

        output = result.stdout or ""
        argv_redacted = ["<PROMPT>" if c is prompt else c for c in cmd]
        return AgentResponse(
            output=output,
            session_id=session_id,
            exit_code=result.returncode,
            extra={"model_id": model_id, "argv": argv_redacted},
        )

    def gc_session(self, session_id: str) -> None:
        """No-op for P5 C36 (mirrors GeminiProvider.gc_session).

        Codex stores sessions under ~/.codex (resume / fork picker UIs
        suggest a stable id model), but P5 fresh runs do not specify
        --session-id on `codex exec` — the framework session_id is kept
        only as an audit-trail extra. Cleanup discipline waits for P5.x
        when demo runs reveal whether session accumulation is a problem.
        """
        if not session_id:
            raise ValueError("session_id must be non-empty")
        return

    def check_scope(
        self,
        staging_dir: str | Path,
        session_id: str | None = None,
    ) -> bool:
        """Identical to ClaudeProvider/GeminiProvider check_scope — git
        status backstop is model-independent (spike-004 design)."""
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
            return False

        if not result.stdout.strip():
            return True

        outside: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line[3:].strip()
            path_str = parts.split(" -> ")[-1].strip().strip('"')
            abs_path = (self.repo_root / path_str).resolve()
            try:
                abs_path.relative_to(staging)
            except ValueError:
                outside.append(str(abs_path))
        return len(outside) == 0

    def _build_cmd(
        self,
        model_id: str,
        prompt: str,
        scope_dirs: list[str],
    ) -> list[str]:
        """Assemble the codex exec argv list per spike-019 D-19-1
        (post-C34 R3 fix).

        scope_dirs[0] is set both as -C <DIR> and as the subprocess cwd
        (caller passes cwd=scope_dirs[0]); scope_dirs[1:] become repeated
        --add-dir <DIR> flags. workspace-write sandbox + --full-auto
        gives auto-approve on cwd + add-dir, blocks anything else.
        """
        cmd: list[str] = [
            self.codex_bin,
            "exec",
            "-m", model_id,
            "-C", str(scope_dirs[0]),
            "--sandbox", "workspace-write",
            "--full-auto",
        ]
        for d in scope_dirs[1:]:
            cmd += ["--add-dir", str(d)]
        cmd.append(prompt)
        return cmd
