"""WorkArea + LLM dispatch.

Context.md compilation lives in `Tooling.context`. This module holds
only the WorkArea sandbox lifecycle and the synchronous dispatch shim
into `Tooling.llm`. Callers needing `compile_context` or the
`_section_*` helpers import them from `Tooling.context` directly.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from ..core import config
from .. import llm


WORKER_TIMEOUT_SEC = 900  # 15 min. Phase 2 LSP cantor_xi had 6
                          # spawns hit the prior 600s wall while making
                          # real progress (esp. measure-theory leaves
                          # like cantorxi_next_*_vol). 900s gives Sonnet
                          # room to finish; fewer-but-longer spawns
                          # paired with shelve_threshold=4 keeps total
                          # cost on stuck goals bounded.

# Postmortem spawn after a main-spawn timeout. Uses --resume so
# session memory is intact; agent writes a short state + blocker note
# (`_progress.md`) and exits. 120s was empirically too tight for
# Sonnet to write a usable note on dense root-level state; 180s gives
# ~50% more breathing room for the same pattern.
POSTMORTEM_TIMEOUT_SEC = 180


def render_prompt_template(text: str, *, is_postmortem: bool = False) -> str:
    """Substitute prompt template placeholders against live config.

    Replacements:
      - `{timeout_min}` — per-spawn wall-clock (WORKER_TIMEOUT_SEC for
        body prompts, POSTMORTEM_TIMEOUT_SEC for postmortems).
      - `{interval_min}` — Strategist T1 routine cadence (minutes;
        `strategist.interval_min` config knob). Only strategist.md
        uses this placeholder today; the substitution is a no-op for
        other prompts.
    """
    timeout_sec = (POSTMORTEM_TIMEOUT_SEC if is_postmortem
                   else WORKER_TIMEOUT_SEC)
    interval_min = config.get(
        "strategist.interval_min", default=60.0,
        env_var="ASTERISM_STRATEGIST_INTERVAL_MIN", cast=float,
    )
    return (text
            .replace("{timeout_min}", str(timeout_sec // 60))
            .replace("{interval_min}", _format_minutes(interval_min)))


def _format_minutes(value: float) -> str:
    """Render a minutes value compactly: integer when whole, one
    decimal otherwise. Avoids '60.0' noise for the common default."""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


class WorkArea:
    """Ephemeral working area for one pipeline run.

    Holds two paths under `.attempts/`:
      * `attempts` = `.attempts/<pid>/`         agent sandbox, Context.md, outputs
      * `backup`   = `.attempts/_backup_<pid>/` Backward's pre-write proofs/ snapshot

    Both are unconditionally rmtree'd on `__exit__` (best-effort). A worker
    that needs to consume `backup` (e.g. Backward restoring on lake fail)
    must `shutil.move` it before the context exits — `__exit__` only cleans
    whatever is still on disk.
    """
    def __init__(self, workspace: Path, pipeline_id: str):
        self.workspace = workspace
        self.pipeline_id = pipeline_id
        self.attempts = workspace / ".attempts" / pipeline_id
        self.backup = workspace / ".attempts" / f"_backup_{pipeline_id}"

    def __enter__(self) -> "WorkArea":
        self.attempts.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Release the gateway session before tearing down attempts/.
        # `_write_mcp_config` only releases the PREVIOUS retry's token
        # (when overwriting on a fresh retry), so the LAST token of
        # each pipeline (and the only token of single-shot pipelines)
        # would otherwise leak — gateway accumulates SessionMetadata
        # entries indefinitely. Best-effort: release_session swallows
        # urlopen errors, so a dead gateway / network blip won't block
        # the rmtree.
        token_file = self.attempts / "_gateway_session.token"
        if token_file.exists():
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except OSError:
                token = ""
            if token:
                from ..lsp import lifecycle as gateway_lifecycle
                gateway_lifecycle.release_session(token)
        for p in (self.attempts, self.backup):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        return False


def spawn_llm(*, kind: str, prompt_path: Path, problem_dir: Path,
              attempts_dir: Path,
              session_id: str | None = None,
              is_retry: bool = False,
              retry_context: str | None = None,
              is_postmortem: bool = False,
              timeout_sec: int | None = None,
              mcp_config_path: Path | None = None,
              inline_prompt: str | None = None,
              timeout_sec_override: int | None = None) -> int:
    """Dispatch to the configured LLM provider for one agent invocation.

    Provider is resolved per-kind: `ASTERISM_<KIND>_PROVIDER` →
    `ASTERISM_LLM_PROVIDER` → 'claude'. Likewise the model string is
    looked up per-kind inside each provider. Returns the provider's
    rc (0 success, 124 timeout, 125 stale session, 126 quota
    exhausted, 127 missing dep, 128 stuck thinking, other = error).

    `session_id` / `is_retry` / `retry_context`: in-pipeline same-
    session retry. Pass a UUID + is_retry=False on first attempt;
    same UUID + is_retry=True + the prior lake error string in
    `retry_context` on subsequent attempts within the same pipeline
    (Phase 7 — sid is a local var owned by the retry helper, not
    persisted across pipeline calls).

    `is_postmortem`: set on the postmortem spawn after a main
    timeout. Provider uses `--resume <session_id>`, loads `prompt_path`
    verbatim (a short instruction asking the agent to dump state +
    blockers into `_progress.md`). `timeout_sec` defaults to
    `POSTMORTEM_TIMEOUT_SEC` (180s) for postmortem calls and
    `WORKER_TIMEOUT_SEC` (600s) otherwise.

    `inline_prompt`: 2026-05-10 — fresh-rescue stage 2 / stage 3
    inline prompt. Caller has minted a fresh `session_id` and copied
    the broken session's jsonl to `attempts_dir/_broken_session.jsonl`
    so the agent can Read it. Provider sends `inline_prompt` verbatim
    as `-p` (no template loading), uses `--session-id <session_id>`
    (cold), skips the watchdog (these are short rescue/postmortem
    replacements). Pair with `timeout_sec_override` (typically 180s)
    for tight budgets.
    """
    if timeout_sec is None:
        if is_postmortem:
            timeout_sec = config.get(
                "dispatch.postmortem_timeout_sec",
                default=POSTMORTEM_TIMEOUT_SEC,
                env_var="ASTERISM_POSTMORTEM_TIMEOUT_SEC", cast=int,
            )
        else:
            timeout_sec = config.get(
                "dispatch.spawn_timeout_sec",
                default=WORKER_TIMEOUT_SEC,
                env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int,
            )
    if timeout_sec_override is not None:
        timeout_sec = timeout_sec_override
    return llm.get_provider(kind=kind).spawn(llm.LLMRequest(
        kind=kind,
        prompt_path=prompt_path,
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
        timeout_sec=timeout_sec,
        session_id=session_id,
        is_retry=is_retry,
        retry_context=retry_context,
        is_postmortem=is_postmortem,
        mcp_config_path=mcp_config_path,
        inline_prompt=inline_prompt,
    ))


def new_pipeline_id() -> str:
    return str(uuid.uuid4())


def attempts_dir_for(workspace: Path, pipeline_id: str) -> Path:
    d = workspace / ".attempts" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d
