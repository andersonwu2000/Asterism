"""Gemini CLI provider (P5 C35).

Wraps `gemini -p ...` subprocess with provider-specific scope-isolation
mapping per spike-019 D-19-1:
  - --include-directories <p1>,<p2>,... (csv, single flag)
  - --approval-mode auto_edit (auto-approve edit tools, prompt for shell)
  - -m, --model <model_id>
  - git status backstop (model-independent fallback per spike-004)

Differences from claude provider:
  - Scope flag: claude uses repeated --add-dir, gemini uses comma-joined
    --include-directories.
  - Approval flag: claude --permission-mode acceptEdits, gemini
    --approval-mode auto_edit.
  - Session tracking: gemini does NOT support specifying a fresh session
    id via flag (only -r/--resume <existing-id|latest|index>). The
    session_id parameter is echoed back on `AgentResponse.session_id`
    (top-level field, identical to ClaudeProvider) so callers see the
    framework session id in audit logs even though the gemini CLI auto-
    generates its own internal id. `AgentResponse.extra` carries the
    resolved `model_id` and a redacted `argv` for diagnostics, but does
    NOT carry session_id — that lives at the top level by design.
    gc_session is a no-op for P5 C35 — gemini stores sessions under
    platform-specific dirs and the framework cleanup discipline is
    provider-specific; will revisit at P5.C38 demo if gemini sessions
    accumulate during fallback runs.

Subprocess invocation pattern:
  gemini -p "$PROMPT" \
      --include-directories "<p1>,<p2>,..." \
      --approval-mode auto_edit \
      -m <model_id> \
      < /dev/null 2>&1

  stdin redirect avoids any TTY-attach hang.
  stderr merged into stdout for capture parity with ClaudeProvider.

Public API: GeminiProvider (Provider subclass) + GEMINI_MODEL_MAP dict.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from Tooling.agent.provider import AgentResponse, Provider, ProviderError


# Gemini tier → model id (per spike-020 D-20-1: opus tier shares pro id
# since gemini lacks a strict opus equivalent in the 2.5 line).
GEMINI_MODEL_MAP: dict[str, str] = {
    "haiku":  "gemini-2.5-flash",
    "sonnet": "gemini-2.5-pro",
    "opus":   "gemini-2.5-pro",
}

DEFAULT_INVOKE_TIMEOUT: float = 600.0
_GIT_TIMEOUT: float = 30.0


class GeminiProvider(Provider):
    """LLM provider backed by the `gemini` CLI."""

    name = "gemini"
    model_map = GEMINI_MODEL_MAP

    def __init__(
        self,
        *,
        gemini_bin: str = "gemini",
        invoke_timeout: float = DEFAULT_INVOKE_TIMEOUT,
        repo_root: str | Path | None = None,
    ) -> None:
        self.gemini_bin = gemini_bin
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

        # P5 C37: PROVIDER_MOCK_GEMINI env hook (test-only).
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
                text=True, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(
                f"gemini invocation timed out after {self.invoke_timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise ProviderError(
                f"gemini binary not found: {self.gemini_bin!r}"
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
        """No-op for P5 C35.

        Gemini does NOT use the fresh-id-per-call pattern that ClaudeProvider
        relies on (no --session-id <new-uuid> flag); sessions are auto-id'd
        and can be enumerated via `gemini --list-sessions`. Cleanup discipline
        is provider-specific; revisit if demo runs at P5.C38 show session
        accumulation. Empty session_id check kept for parity with
        ClaudeProvider.gc_session.
        """
        if not session_id:
            raise ValueError("session_id must be non-empty")
        return

    def check_scope(
        self,
        staging_dir: str | Path,
        session_id: str | None = None,
    ) -> bool:
        """Identical to ClaudeProvider.check_scope — git status backstop is
        model-independent (spike-004 design). session_id unused here but
        kept for FallbackChain.validate_scope signature parity.

        Returns True iff no files outside staging_dir were modified per
        `git status --porcelain` of repo_root.
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
        """Assemble the gemini CLI argv list per spike-019 D-19-1.

        scope_dirs[0] becomes the subprocess cwd (set by caller); the rest
        are passed as a comma-joined --include-directories value. Only one
        --include-directories flag is sent so the CSV form is canonical
        (gemini --help allows both repeated and CSV; CSV keeps argv shorter).
        """
        cmd: list[str] = [
            self.gemini_bin,
            "-p", prompt,
            "-m", model_id,
            "--approval-mode", "auto_edit",
        ]
        # gemini's CWD is implicitly part of the workspace; only extra dirs
        # need --include-directories. scope_dirs[0] is the cwd by convention
        # (matches ClaudeProvider behaviour where cwd defaults to scope_dirs[0]).
        extra_dirs = [str(d) for d in scope_dirs[1:]]
        if extra_dirs:
            cmd += ["--include-directories", ",".join(extra_dirs)]
        return cmd
