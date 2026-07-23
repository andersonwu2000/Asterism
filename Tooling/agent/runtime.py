"""WorkArea + LLM dispatch.

Context.md compilation lives in `Tooling.context`. This module holds
only the WorkArea sandbox lifecycle and the synchronous dispatch shim
into `Tooling.llm`. Callers needing `compile_context` or the
`_section_*` helpers import them from `Tooling.context` directly.
"""
from __future__ import annotations

import re
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


_PROMPT_COND_RE = re.compile(
    r"[ \t]*<!-- #if (\w+) -->[ \t]*\n(.*?)[ \t]*<!-- #endif -->[ \t]*\n?",
    re.DOTALL)


def render_prompt_template(text: str, *, is_postmortem: bool = False,
                           flags: "dict[str, bool] | None" = None) -> str:
    """Substitute prompt template placeholders against live config.

    Replacements:
      - `{timeout_min}` — per-spawn wall-clock (WORKER_TIMEOUT_SEC for
        body prompts, POSTMORTEM_TIMEOUT_SEC for postmortems).
      - `{interval_min}` — Strategist T1 routine cadence (minutes;
        `strategist.interval_min` config knob). Only the strategist
        prompts (`strategist/*.md`) use this placeholder today; the
        substitution is a no-op for other prompts.
      - `<!-- #if name -->…<!-- #endif -->` — conditional block (D8
        2026-07-24: fresh-problem wakes drop the not-yet-applicable
        paragraphs without wording changes). The block stays when
        `flags` is None or the name is absent (fail-open); it is
        dropped only on an explicit falsy flag. Marker lines are
        always stripped.
    """
    def _cond(m: "re.Match[str]") -> str:
        if flags is None or flags.get(m.group(1), True):
            return m.group(2)
        return ""
    text = _PROMPT_COND_RE.sub(_cond, text)
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
              retry_reason: str | None = None,
              is_postmortem: bool = False,
              timeout_sec: int | None = None,
              mcp_config_path: Path | None = None,
              inline_prompt: str | None = None,
              timeout_sec_override: int | None = None,
              trap_check_sec_override: int | None = None,
              usage_workspace: Path | None = None,
              usage_problem: str | None = None,
              usage_pipeline_id: str | None = None,
              prompt_flags: "dict[str, bool] | None" = None) -> int:
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

    `usage_workspace` / `usage_problem` / `usage_pipeline_id`: explicit
    spawn_usage attribution for callers whose dirs break the standard
    layout (`attempts_dir = <ws>/.attempts/<pid>`, `problem_dir` under
    Problems/). The Adversary spawns into a projection dir nested
    inside another pipeline's attempts dir — the derived workspace
    pointed at `.attempts/<pid>/` and every judge row was silently
    dropped (b6: ~0.5h of judge cost invisible, 2026-07-18).
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
    import time as _time
    _t0 = _time.monotonic()
    rc = llm.get_provider(kind=kind).spawn(llm.LLMRequest(
        kind=kind,
        prompt_path=prompt_path,
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
        timeout_sec=timeout_sec,
        trap_check_sec=trap_check_sec_override,
        session_id=session_id,
        is_retry=is_retry,
        retry_context=retry_context,
        retry_reason=retry_reason,
        is_postmortem=is_postmortem,
        mcp_config_path=mcp_config_path,
        inline_prompt=inline_prompt,
        prompt_flags=prompt_flags,
    ))
    _record_spawn_usage(kind=kind, attempts_dir=attempts_dir,
                        problem_dir=problem_dir,
                        wall_sec=_time.monotonic() - _t0,
                        workspace=usage_workspace, problem=usage_problem,
                        pipeline_id=usage_pipeline_id)
    return rc


def _record_spawn_usage(*, kind: str, attempts_dir: Path,
                        problem_dir: Path, wall_sec: float,
                        workspace: Path | None = None,
                        problem: str | None = None,
                        pipeline_id: str | None = None) -> None:
    """Persist the spawn's token/turn accounting into `spawn_usage`
    (frontend charter §5-2). Source = the provider's
    `_parser_state.json` usage block (claude provider writes it; other
    providers simply have no file → no row). Best-effort throughout:
    telemetry must never fail a spawn. Own short-lived WAL connection —
    spawn_llm has no caller conn, and a per-spawn single INSERT is
    negligible contention."""
    import json as _json
    try:
        raw = (attempts_dir / "_parser_state.json").read_text(
            encoding="utf-8")
        usage = (_json.loads(raw).get("usage") or {})
        if not (usage.get("turns") or usage.get("output_tokens")):
            return
        # Defaults assume the standard layout (explicit params override:
        # attempts_dir = <workspace>/.attempts/<pipeline_id>;
        # problem name = problem_dir relative to <workspace>/Problems
        # with / → . (matches db.problem_dir's inverse)).
        if workspace is None:
            workspace = attempts_dir.parent.parent
        if problem is None:
            try:
                rel = problem_dir.resolve().relative_to(
                    (workspace / "Problems").resolve())
                problem = ".".join(rel.parts)
            except ValueError:
                problem = problem_dir.name
        if pipeline_id is None:
            pipeline_id = attempts_dir.name
        from ..state import db as _db
        db_path = workspace / "asterism.db"
        if not db_path.exists():
            # A miscomputed workspace must fail silent-and-clean, not
            # mint a junk sqlite file wherever it happened to point.
            return
        conn = _db.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO spawn_usage (pipeline_id, kind, problem,"
                " input_tokens, output_tokens, cache_read_tokens,"
                " cache_new_tokens, turns, wall_sec, ts)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pipeline_id, kind, problem,
                 int(usage.get("input_tokens") or 0),
                 int(usage.get("output_tokens") or 0),
                 int(usage.get("cache_read_input_tokens") or 0),
                 int(usage.get("cache_creation_input_tokens") or 0),
                 int(usage.get("turns") or 0),
                 float(wall_sec), _db.now()))
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — telemetry never fails a spawn
        pass


def new_pipeline_id() -> str:
    return str(uuid.uuid4())


def attempts_dir_for(workspace: Path, pipeline_id: str) -> Path:
    d = workspace / ".attempts" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d
