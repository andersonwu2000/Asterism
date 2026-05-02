"""Gemini CLI provider — subprocess to `gemini` executable.

Targets the Google Gemini CLI's free tier (Code Assist personal-account
auth). The CLI handles its own retry on 429 with exponential backoff
(~3-5 attempts) before giving up; this provider just wraps subprocess
and treats no-output as quota exhaustion.

Model selection: `ASTERISM_GEMINI_MODEL` env (default: gemini-2.5-flash).
gemini-2.5-pro has nearly-zero free-tier quota in practice — flash is
the sole practical target unless the user has paid access.

No session / retry support: `gemini --resume` uses session index
(integer / "latest"), not UUID, so F33 same-session retry doesn't map
cleanly. `LLMRequest.session_id` / `is_retry` / `retry_context` are
ignored. Each invocation is a fresh session.

Quota-exhausted sentinel: gemini CLI returns rc=0 even when ALL
internal retries fail (observed: pro model exhausted, 5 attempts each
returning "You have exhausted your capacity on this model", final
rc=0). To distinguish, after subprocess.run we check whether the
agent actually wrote anything into `attempts_dir`. If not AND a
quota / rate-limit phrase appears in stderr+stdout, return
`RC_QUOTA_EXHAUSTED` so callers can back off rather than misread it
as a normal failure.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .base import LLMRequest


DEFAULT_MODEL = "gemini-2.5-flash"

# Quota-exhausted sentinel rc — distinct from 124 (timeout), 125 (stale
# claude session, F33), 127 (CLI missing). Caller may surface as a
# distinct dead_attempt failure_reason or trigger a wait-and-retry.
RC_QUOTA_EXHAUSTED = 126


def _resolve_model(kind: str | None) -> str:
    """Model resolution chain for the gemini provider (per
    Tooling/config.get):

    1. `ASTERISM_<KIND>_MODEL` env  (kind in {'builder','backward'})
    2. Asterism.yaml `<kind>.model`
    3. `ASTERISM_GEMINI_MODEL` env  (legacy gemini-wide)
    4. `DEFAULT_MODEL` (gemini-2.5-flash)
    """
    from .. import config
    if kind:
        v = config.get(
            f"{kind}.model",
            env_var=f"ASTERISM_{kind.upper()}_MODEL",
            legacy_env=("ASTERISM_GEMINI_MODEL",),
            default=DEFAULT_MODEL,
        )
        return str(v)
    return os.environ.get("ASTERISM_GEMINI_MODEL", DEFAULT_MODEL)


def _resolve_gemini_executable() -> str | None:
    """Return a launchable path for `gemini`, or None if not installed.

    npm installs gemini side-by-side as `gemini` (a no-extension bash
    shim, for MSYS / WSL / Git Bash) and `gemini.cmd` (Windows batch
    wrapper). On Windows, only the .cmd is launchable via CreateProcess
    / subprocess.run; passing the bash shim raises FileNotFoundError
    (WinError 2). `shutil.which("gemini")` from a Bash session may
    return the shim, so we explicitly probe `.cmd` / `.bat` / `.exe`
    first on Windows. Linux / macOS skip this and fall through to the
    plain name.
    """
    if sys.platform == "win32":
        for ext in (".cmd", ".bat", ".exe"):
            p = shutil.which(f"gemini{ext}")
            if p:
                return p
    return shutil.which("gemini")

# Substrings that confirm an apparent rc=0 was actually a quota / rate
# refusal masquerading as success. Lowercased before matching.
_QUOTA_MARKERS = (
    "exhausted your capacity",
    "too many requests",
    "rate limit",
    "status: 429",
)


def _shared_flags() -> list[str]:
    """CLI flags every Gemini invocation needs:

      --yolo            auto-approve all tool calls (non-interactive use)
      --skip-trust      bypass workspace-trust prompt (Asterism cwd
                        is its own repo, not a user-curated trusted
                        folder)
      --output-format text  plain stdout (no streaming JSON wrapper)
    """
    return [
        "--yolo",
        "--skip-trust",
        "--output-format", "text",
    ]


def _output_present(attempts_dir: Path) -> bool:
    """Did the agent write any expected artifact? Backward emits
    `new_*.lean` + `PROPOSAL.md` + `patch_*.lean`; Builder emits
    `patch.lean`. Pre-existing `Context.md` is excluded — it's
    framework-written, not agent output."""
    if not attempts_dir.exists():
        return False
    for p in attempts_dir.iterdir():
        if p.name == "Context.md":
            continue
        if p.suffix in (".lean", ".md"):
            return True
    return False


def _quota_message_in(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _QUOTA_MARKERS)


class GeminiCliProvider:
    def spawn(self, req: LLMRequest) -> int:
        gemini_exe = _resolve_gemini_executable()
        if not gemini_exe:
            print("[llm:gemini] gemini CLI not found; skipping spawn",
                  flush=True)
            return 127

        model = _resolve_model(req.kind)

        prompt = (
            f"{req.kind} task. Read agent prompt at "
            f"{req.prompt_path} and follow it exactly.\n"
            f"Read context at {req.attempts_dir}/Context.md.\n"
            f"Write output to {req.attempts_dir}/."
        )

        cmd = [
            gemini_exe,
            "-m", model,
            "-p", prompt,
            "--include-directories",
            f"{req.problem_dir},{req.attempts_dir}",
            *_shared_flags(),
        ]

        try:
            r = subprocess.run(
                cmd, timeout=req.timeout_sec,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                # F44 — anchor agent cwd at problem_dir (matches
                # claude_cli; soft-sandbox so relative reads/writes
                # land inside the Problem instead of at workspace).
                cwd=str(req.problem_dir),
            )
        except subprocess.TimeoutExpired:
            print(f"[llm:gemini] timed out after {req.timeout_sec}s",
                  flush=True)
            return 124
        except FileNotFoundError as e:
            # Defensive: _resolve_gemini_executable returned a path
            # whose target was deleted between checks, or PATHEXT
            # produced a stale hit. Surface as missing-CLI rather
            # than letting subprocess raise.
            print(f"[llm:gemini] launch failed ({e})", flush=True)
            return 127

        # rc=0 from gemini does NOT prove the model produced anything —
        # the CLI swallows quota exhaustion (after its own retries) and
        # exits clean. Verify by checking that the agent actually wrote
        # an artifact AND, when nothing was written, looking for a
        # quota / rate-limit phrase in the captured output.
        if r.returncode == 0 and not _output_present(req.attempts_dir):
            combined = (r.stderr or "") + "\n" + (r.stdout or "")
            if _quota_message_in(combined):
                print("[llm:gemini] quota exhausted (rc=0 + no output)",
                      flush=True)
                return RC_QUOTA_EXHAUSTED
            # No output, no quota phrase — still a failure (agent ran
            # but produced nothing usable). Generic non-zero so the
            # pipeline records a dead_attempt.
            print("[llm:gemini] rc=0 but no agent output written",
                  flush=True)
            return 1
        return r.returncode

    def complete_text(
        self, *, prompt: str, timeout_sec: int = 60,
    ) -> str | None:
        """One-shot completion via `gemini -p`. Returns stdout text or
        None on quota exhaustion / timeout / failure. Used by F22 short
        auxiliary calls (idiom extract / curate)."""
        gemini_exe = _resolve_gemini_executable()
        if not gemini_exe:
            return None
        # F22 auxiliary calls inherit the 'builder' tier.
        model = _resolve_model("builder")
        cmd = [
            gemini_exe,
            "-m", model,
            "-p", prompt,
            *_shared_flags(),
        ]
        try:
            r = subprocess.run(
                cmd, timeout=timeout_sec,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if r.returncode != 0:
            return None
        text = r.stdout.strip()
        # Empty stdout + quota phrase in captured output → quota lie.
        if not text and _quota_message_in((r.stderr or "")
                                          + "\n" + (r.stdout or "")):
            return None
        return text or None
