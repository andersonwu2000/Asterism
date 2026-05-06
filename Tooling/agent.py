"""WorkArea + LLM dispatch.

P2-#2: Context.md compilation moved to `Tooling.context`. This module
keeps the responsibilities its docstring originally promised — sandbox
dir, ephemeral pipeline workspace, and the synchronous dispatch
shim into `Tooling.llm`. Section helpers + `compile_context` re-export
below for back-compat with existing call sites
(`agent.compile_context`, `agent._section_*`).
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from . import llm

# Re-export everything Context-related so legacy callers
# (`agent.compile_context`, `agent._section_X`, `agent._digest_failure`)
# keep working transparently. P2-#2 moved the implementation to
# Tooling/context.py — these names live there now.
from .context import (  # noqa: F401  (re-export)
    _LEAN_PATH_DUMP_RE,
    _FIRST_ERROR_RE,
    _ago,
    _collect_lemma_names,
    _digest_failure,
    _section_builder_declines,
    _section_dead_strategies,
    _section_header,
    _section_library_available,
    _section_manifest_forbidden,
    _section_manifest_notes,
    _section_mathlib_lemmas,
    _section_parent_strategy,
    _section_past_attempts,
    _section_past_backward,
    _section_prior_partial,
    _section_playbook,
    _section_sandbox,
    _section_strategy_naming,
    compile_context,
)


WORKER_TIMEOUT_SEC = 600  # 10 min, see architecture.md §13

# F55 — postmortem spawn after a main-spawn timeout. Uses --resume so
# session memory is intact; agent writes a short state + blocker note
# (`_progress.md`) and exits. 120s was empirically too tight for
# Sonnet to write a usable note on dense root-level state; 180s gives
# ~50% more breathing room for the same pattern.
POSTMORTEM_TIMEOUT_SEC = 180


def render_prompt_template(text: str, *, is_postmortem: bool = False) -> str:
    """Substitute `{timeout_min}` in a prompt template with the live
    timeout (in minutes). Body prompts report `WORKER_TIMEOUT_SEC`;
    postmortem prompts (F55) report `POSTMORTEM_TIMEOUT_SEC`."""
    timeout_sec = (POSTMORTEM_TIMEOUT_SEC if is_postmortem
                   else WORKER_TIMEOUT_SEC)
    return text.replace("{timeout_min}", str(timeout_sec // 60))


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
        for p in (self.attempts, self.backup):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        return False


def _attempts_dir(workspace: Path, pipeline_id: str) -> Path:
    d = workspace / ".attempts" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def spawn_llm(*, kind: str, prompt_path: Path, problem_dir: Path,
              attempts_dir: Path,
              session_id: str | None = None,
              is_retry: bool = False,
              retry_context: str | None = None,
              is_postmortem: bool = False,
              timeout_sec: int | None = None) -> int:
    """Dispatch to the configured LLM provider for one agent invocation.

    Provider is resolved per-kind (F39): `ASTERISM_<KIND>_PROVIDER` →
    `ASTERISM_LLM_PROVIDER` → 'claude'. Likewise the model string is
    looked up per-kind inside each provider. Returns the provider's
    rc (0 success, 124 timeout, 125 stale session (F33), 126 quota
    exhausted (F38 gemini), 127 missing dep, other = error).

    `session_id` / `is_retry` / `retry_context`: F33 same-session
    Builder retry. Pass a UUID + is_retry=False on first attempt;
    same UUID + is_retry=True + the prior lake error string in
    `retry_context` on subsequent attempts.

    `is_postmortem`: F55 — set on the postmortem spawn after a main
    timeout. Provider uses `--resume <session_id>`, loads `prompt_path`
    verbatim (a short instruction asking the agent to dump state +
    blockers into `_progress.md`). `timeout_sec` defaults to
    `POSTMORTEM_TIMEOUT_SEC` (180s) for postmortem calls and
    `WORKER_TIMEOUT_SEC` (600s) otherwise.
    """
    if timeout_sec is None:
        timeout_sec = (POSTMORTEM_TIMEOUT_SEC if is_postmortem
                       else WORKER_TIMEOUT_SEC)
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
    ))


def new_pipeline_id() -> str:
    return str(uuid.uuid4())


def attempts_dir_for(workspace: Path, pipeline_id: str) -> Path:
    return _attempts_dir(workspace, pipeline_id)
