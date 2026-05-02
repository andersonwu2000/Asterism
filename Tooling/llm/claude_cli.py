"""Claude CLI provider — subprocess to `claude` executable.

Inherits the existing claude CLI workflow: `--add-dir` for sandboxing,
`acceptEdits` permission, text output. The agent reads `Context.md`
from `attempts_dir/` and writes outputs back there. The prompt
template content is inlined into `-p` (F45) so the agent doesn't
need read access to the workspace `Tooling/prompts/` directory.

Model selection: `ASTERISM_AGENT_MODEL` env (default: Sonnet).

System-prompt trim (F27): direct measurement of the claude CLI 2.1
default vs the optimized flags below shows ~20.7K → ~7.8K prefix
tokens per call (-62%) on Sonnet. The 4 flags strip tool descriptions
Asterism doesn't use (Bash, Glob, Grep, WebFetch, WebSearch,
NotebookEdit, mcp__*), skip CLAUDE.md / auto-memory / settings load,
and stabilize per-machine sections so prompt caching reuses across
calls. Override the tool list via `ASTERISM_CLAUDE_TOOLS` if a future
flow needs a different surface.

Same-session retry (F33): when LLMRequest.session_id is provided,
the cold path uses `--session-id <uuid>` to pin the session id; a
retry (is_retry=True) uses `--resume <uuid>` and a short prompt
(builder_retry.md) that relies on the session memory carrying the
prior turn's reasoning. `--no-session-persistence` is dropped on
those calls — sessions persist to disk so Asterism can resume them.
Sessions without session_id (e.g. Backward) keep the old
`--no-session-persistence` behavior.

Stale session sentinel (F33): `claude --resume <uuid>` against a
session id whose on-disk file is gone (GC'd / never existed) returns
rc=1 with stderr `"No conversation found with session ID"`. spawn
maps that to rc=125 so the caller (pipeline) knows to clear the
DB session_id and retry with a fresh uuid (cold path).
"""
from __future__ import annotations

import os
import shutil
import subprocess

from .base import LLMRequest


DEFAULT_MODEL = "claude-sonnet-4-6"

# F33 — sentinel rc returned when claude reports "No conversation
# found with session ID: ...". Caller's contract: on rc=125, clear
# the goal's builder_session_id and retry once with a fresh uuid.
RC_STALE_SESSION = 125
_STALE_SESSION_MARKER = "no conversation found with session id"

# Asterism's pipelines only ever need Read / Write / Edit. Backward,
# Builder, Verify each manipulate sandbox files; lemma signatures and
# stderr hints come pre-resolved by the framework (F9, F20). Override
# via env if a future use case needs more (e.g. Bash for ad-hoc shell).
DEFAULT_TOOLS = "Read Write Edit"


def _resolve_model(kind: str | None) -> str:
    """Model resolution chain for the claude provider (per
    Tooling/config.get):

    1. `ASTERISM_<KIND>_MODEL` env  (kind in {'builder','backward'})
    2. Asterism.yaml `<kind>.model`
    3. `ASTERISM_AGENT_MODEL` env  (legacy provider-wide)
    4. `DEFAULT_MODEL`
    """
    from .. import config
    if kind:
        v = config.get(
            f"{kind}.model",
            env_var=f"ASTERISM_{kind.upper()}_MODEL",
            legacy_env=("ASTERISM_AGENT_MODEL",),
            default=DEFAULT_MODEL,
        )
        return str(v)
    return os.environ.get("ASTERISM_AGENT_MODEL", DEFAULT_MODEL)


def _load_prompt(req: LLMRequest) -> str:
    """Read the prompt template file. F45: inlined into `-p` instead
    of pointed-to so the agent never needs read access to the workspace
    `Tooling/prompts/` directory (which lives outside `--add-dir` after
    F44 narrowed cwd to problem_dir). On read error, return a marker
    string so the spawn still proceeds and the failure surfaces as a
    normal agent error rather than a silent crash."""
    try:
        return req.prompt_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"(prompt file unavailable: {e})"


def _build_cold_prompt(req: LLMRequest) -> str:
    """Compose the `-p` payload for a cold (non-retry) spawn: the full
    prompt template content, followed by short framework instructions
    pointing at Context.md and the output directory."""
    body = _load_prompt(req)
    return (
        f"You are running a {req.kind} task. Follow the instructions "
        f"below exactly.\n\nAfter reading them, read context at "
        f"{req.attempts_dir}/Context.md and write outputs into "
        f"{req.attempts_dir}/.\n\n"
        f"=== INSTRUCTIONS ===\n{body}\n=== END INSTRUCTIONS ==="
    )


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

        model = _resolve_model(req.kind)

        # F33 — retry path uses `--resume`, a short inline prompt with
        # the lake error embedded directly (no separate RETRY_NOTE.md
        # file → agent doesn't need a Read tool round-trip), and skips
        # the file-based prompt fetch (prior turn's context lives in
        # claude's session memory).
        if req.is_retry and req.session_id:
            session_flags = ["--resume", req.session_id]
            session_lifetime_flag: list[str] = []  # session persists
            err = (req.retry_context or "(lake error not captured)").strip()
            prompt = (
                f"Previous attempt failed lake build with:\n\n"
                f"```\n{err}\n```\n\n"
                f"Produce a fresh patch.lean (same scope) addressing "
                f"this error. Reuse the prior PROPOSAL.md unless the "
                f"strategy needs to change. Write outputs into "
                f"{req.attempts_dir}/."
            )
        elif req.session_id:
            # Cold path with a caller-pinned session id (so a future
            # retry can resume).
            session_flags = ["--session-id", req.session_id]
            session_lifetime_flag = []  # persist
            prompt = _build_cold_prompt(req)
        else:
            # Legacy non-session path: ephemeral session, original prompt.
            session_flags = []
            session_lifetime_flag = ["--no-session-persistence"]
            prompt = _build_cold_prompt(req)

        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--permission-mode", "acceptEdits",
            "--add-dir", str(req.problem_dir),
            "--add-dir", str(req.attempts_dir),
            "--output-format", "text",
            *session_flags,
            *session_lifetime_flag,
            *_trim_flags(),
        ]
        try:
            r = subprocess.run(
                cmd, timeout=req.timeout_sec,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                # F44 — anchor agent cwd at problem_dir, not workspace.
                # Soft-sandbox: relative paths the agent writes resolve
                # under the Problem; reduces wandering reads to other
                # Problems / workspace-root files. attempts_dir is still
                # passed as absolute path in the prompt above so reads
                # there continue to work regardless of cwd.
                cwd=str(req.problem_dir),
            )
            # F33 — detect stale session: claude returns rc=1 with
            # "No conversation found with session ID: ..." in stderr.
            # Surface as RC_STALE_SESSION so pipeline can clear the
            # DB session_id and retry with a fresh one.
            if (r.returncode != 0 and req.is_retry
                    and _STALE_SESSION_MARKER in (r.stderr or "").lower()):
                print(f"[llm:claude] stale session "
                      f"{req.session_id[:8] if req.session_id else '?'}",
                      flush=True)
                return RC_STALE_SESSION
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
        invokes tools, but the same trim applies to the system prompt.
        F22 auxiliary calls inherit the 'builder' tier (cheap-LLM role)."""
        if not shutil.which("claude"):
            return None
        model = _resolve_model("builder")
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
