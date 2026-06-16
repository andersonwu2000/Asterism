"""In-pipeline retry helper (Phase 7).

Replaces cross-pipeline session passing (former same-session retry
that flowed through DB) with an in-pipeline retry loop sharing one
claude session. Builder / Backward
inner functions delegate retry control flow here and supply kind-
specific spawn + parse callbacks.

Design decisions resolved 2026-05-06 — see
`docs/dev/pipeline_session_unification.md`:
  1. Budget is dynamic (`threshold - goal.attempts`); no separate config knob.
  2. moot outcome is uniform no-op (no attempts++, no dead_attempt write).
  3. timeout (rc=124) → postmortem + forced exhaust.
  4. stale_session (rc=125) on warm spawn → in-place cold re-mint, no
     budget consumed.
  5. goals.attempts increments per failed spawn (1:1 with dead_attempts).
  6. dead_attempts row per failed retry, artifacts JSON snapshot per row.

Forensic write protocol: dead_attempts.pipeline_id is FK to pipelines.id;
the pipelines row is INSERTed by `dispatcher._run_pipeline` AFTER this
helper returns. The helper therefore CANNOT write dead_attempts inline
(FK violation). Per-retry records are buffered into
`PipelineResult.pending_failures`; `_run_pipeline` flushes them after
the pipelines INSERT.

`goals.attempts` is incremented EAGERLY (per retry, in-helper) for
live operator visibility — `TREE.md` + `asterism status` show retry
progress mid-pipeline rather than waiting for cascade. The paired
dead_attempts row is still buffered for FK reasons. Crash semantics:
daemon kill mid-pipeline leaves attempts inflated by N relative to
dead_attempts (no rows for the in-flight pipeline); this drift is
cosmetic — `bfs_refill` and threshold checks treat attempts as
authoritative either way, and on the next dispatch the goal simply
appears to have N more failures than dead_attempts records (operator-
visible drift, no functional bug).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..state import db, tree
from ..llm import claude_cli
from ..llm.base import SpawnRC
from . import PipelineResult, _spawn_failure, collect_artifacts


# Outcomes that terminate the retry loop without further attempts.
# `proved` (Builder success), `success` (Backward strategy commit).
_TERMINAL_SUCCESS_OUTCOMES = frozenset({"proved", "success"})

# Failure reasons that must NOT be retried inside the loop:
#   * `agent_declined` (Builder) — agent intentionally declined; cascade
#     routes to Backward.
#   * `agent_infeasible` (Builder/Backward) — agent supplied a counter-
#     example; cascade shelves the goal and propagates upward.
#   * `goal_no_longer_open` (Backward) — race-detected mid-parse moot
#     (sibling proved or shelve propagated while this pipeline was
#     building). Retrying the same session against a terminated goal
#     accomplishes nothing.
_TERMINAL_DECLINE_REASONS = frozenset({
    # Decline directives that the in-pipeline retry helper must NOT
    # silently retry — the agent has emitted a structured signal that
    # this goal is done at this level. cascade_one routes each by
    # failure_reason; helper just stops the loop.
    "agent_declined",       # needs_decomposition → entry_kind switch to Backward
    "agent_infeasible",     # unprovable → shelve + cascade up
    "parent_needs_fix",     # return_to_parent → shelve + cascade up + fix hint
    "agent_shelved",        # shelve → shelve + cascade up
    # Backward rescue option (d) — agent wrote `_progress.md` instead
    # of committing a split when not confident. Terminal in this
    # pipeline so the loop exits and `run_backward` outer wrapper
    # persists the note into .drafts/ for the next cold dispatch.
    "agent_bailed",
    # Race-detected mid-parse: a sibling already terminated this goal.
    "goal_no_longer_open",
    # #112(a) — agent's decomposition recapitulates a previously-disproved
    # statement (agent counterexample, status='disproved'). Same-sid retry
    # would re-emit the same split; only a fresh dispatch (and ideally a
    # fresh-rescue prompt mentioning the disproved collision) has any
    # chance of a different proposal. Phase 2 — renamed from
    # `same_as_shelved` after status enum split (see
    # `docs/phase2/pipelines.md` §4.1).
    "same_as_disproved",
})


def goal_still_active(conn: sqlite3.Connection, goal_id: int,
                      shelve_threshold: int,
                      *, decision_id: int | None = None) -> bool:
    """Cascade re-check before each retry-loop spawn. Returns False
    when a parallel cascade has already terminated the goal:
      * goal row missing (race / DB drift)
      * status no longer 'open' / 'attempting' (sibling proved /
        explicit shelve / propagated shelve)
      * attempts already at SHELVE_THRESHOLD (a parallel
        `_propagate_shelve` may have bumped past it).

    `shelve_threshold` must be the goals-level shelve cap (typically
    `dispatcher.SHELVE_THRESHOLD`), NOT the per-kind budget threshold;
    those two coincide for Backward but differ for Builder, so the
    helper takes them as separate parameters.

    When `decision_id` is set, the pipeline was dispatched by a
    Strategist Inject decision. Strategist authored the routing with
    full knowledge of the attempts history (visible in its context's
    failure_replay), so the attempts cap is skipped — only the status
    check still applies (a parallel cascade that flipped the goal to
    proved/disproved/dead still moots, so Inject can't infinite-loop
    on a terminated goal). See `docs/data-flow.md` §3 for the design
    rationale.

    The loop returns `outcome="moot"` on False — no state mutation,
    no attempts++, no dead_attempt write.
    """
    g = db.get_goal(conn, goal_id)
    if g is None:
        return False
    if g["status"] not in ("open", "attempting"):
        return False
    if decision_id is None and int(g["attempts"]) >= shelve_threshold:
        return False
    return True


# Fresh-rescue (revised 2026-05-10, second iteration): when watchdog
# kills a spawn for stuck-thinking, the broken session is unrecoverable
# (--resume re-enters the deep-thinking pattern; production observed
# 0 events for full rescue budget). The original session's stages
# (rescue at -3min wall_cap, postmortem on subprocess timeout) cannot
# fire on the broken session. Replacement: spawn fresh sessions to
# take over those stages, preserving original budget structure.
#
# Workflow per stuck-thinking event:
#
#   Stage 2 (rescue, ~3min budget = `dispatch.rescue_timeout_sec`):
#     Mint fresh sid #2, copy broken session's jsonl to
#     `attempts_dir/_broken_session.jsonl`, spawn cold with a stage-2
#     prompt that tells the agent to Read the broken jsonl then
#     ship-or-bail. Replaces the original `--resume + rescue prompt`
#     stage that the broken session can't run.
#
#   Stage 3 (postmortem, ~3min budget = `dispatch.postmortem_timeout_sec`):
#     If stage 2 fails / parse non-terminal, mint fresh sid #3, spawn
#     with a stage-3 prompt asking for `_progress.md` based on the
#     broken jsonl. Replaces the original postmortem stage. The
#     resulting `_progress.md` is detected by parse's bail discriminator
#     → `agent_bailed` terminal decline → outer wrapper persists to
#     `.drafts/` for the next cold dispatch.
#
# Subsequent warm retries within the same pipeline use sid #2 / sid #3
# (the most recent fresh sid), not the abandoned broken sid.
#
# Worst-case cost per stuck-thinking event: 2 fresh spawns × ~3min
# = ~6min wall (vs. the prior design's full spawn budgets per fresh
# spawn = 15-30+ min, with recursive fresh-rescues observed).
def _copy_broken_session_jsonl(broken_sid: str, dest: Path) -> bool:
    """Copy the broken session's jsonl to `dest` so a fresh-rescue
    agent can Read it from inside the sandbox without needing
    add-dir access to ~/.claude/projects/. Returns True on success;
    best-effort, any error returns False (the fresh agent then has
    no prior context but the spawn still proceeds)."""
    import shutil as _shutil
    from ..llm.claude_cli import _find_session_jsonl
    src = _find_session_jsonl(broken_sid)
    if src is None:
        return False
    try:
        _shutil.copyfile(src, dest)
    except OSError:
        return False
    return True


@dataclass
class SpawnCtx:
    """Per-attempt context handed to the kind-specific spawn callback.

    `cold=True` means the agent has no prior session to resume — either
    attempt 0 of a fresh pipeline, a stale_session in-place re-mint,
    or a fresh-rescue stage 2 / stage 3 (see `inline_prompt`).

    `inline_prompt` (fresh-rescue): when set, the spawn function should
    skip the normal cold-prompt template loading and pass this string
    directly as the inline `-p` payload to claude. Used for fresh-
    rescue stage 2 (ship-or-bail) and stage 3 (postmortem). The
    framework also pre-writes `attempts_dir/_broken_session.jsonl` so
    the agent can Read the broken session's history without needing
    add-dir access to `~/.claude/projects/`. The spawn still does
    cold-prep (Context.md compile, strategy skeleton) so the standard
    workspace artifacts exist.

    `budget_override`: per-spawn timeout override (seconds). Set
    alongside `inline_prompt` so stage 2 / stage 3 each get the tight
    rescue / postmortem budget instead of the default 900s spawn
    budget. None means use the kind's default (spawn_timeout_sec).
    """
    sid: str
    cold: bool
    retry_context: str | None
    attempts_dir: Path
    inline_prompt: str | None = None
    budget_override: int | None = None
    # Prior attempt's failure_reason (e.g. `agent_stuck_thinking`) so the
    # spawn callback can frame the retry honestly — a thinking-trap death
    # is rc=0, not a lake error. None on attempt 0 / non-retry spawns.
    retry_reason: str | None = None


def _build_fresh_rescue_stage2_prompt(
    attempts_dir: Path, jsonl_copied: bool, rescue_min: int,
) -> str:
    """Stage-2 prompt: agent Reads broken jsonl, ships-or-bails.

    Path discipline (2026-05-10 fix): includes `attempts_dir` as the
    explicit output location. The `_build_cold_prompt` wrapper
    (`claude_cli.py`) only fires for `inline_prompt is None` spawns;
    fresh-sid takeovers use `inline_prompt`, so the wrapper's
    "write outputs into {attempts_dir}/" hint never applies. Without
    this explicit path, agent's cwd-relative Write goes to the
    sandbox root (problem_dir) and the framework's parse_fn (which
    reads from attempts_dir) sees no files. SG run #10 evidence:
    fresh-sid stage 2 wrote patch.lean + new_*.lean to
    Problems/sylvester_gallai/ root instead of attempts_dir, parse
    silently failed, takeover counted as no-deliverable."""
    if jsonl_copied:
        log_note = (
            f"The previous session's full conversation log is at "
            f"`{attempts_dir}/_broken_session.jsonl`. Read it (use "
            f"offset/limit for large files) to see what was attempted "
            f"and where it got stuck."
        )
    else:
        log_note = (
            "The previous session's log was not recoverable. Work "
            f"from `{attempts_dir}/Context.md` alone."
        )
    return (
        f"The previous session was killed mid-think after exceeding the "
        f"wall-clock budget. {log_note}\n\n"
        f"All output files must be written into `{attempts_dir}/` — "
        f"use absolute paths in your Write calls. The framework only "
        f"reads files from there.\n\n"
        f"Then ship ONE of the following — use what's already in the "
        f"log:\n"
        f"(a) `{attempts_dir}/patch.lean` + "
        f"`{attempts_dir}/new_<slug>.lean` stubs (`:= by sorry` ok)\n"
        f"(b) `{attempts_dir}/patch.lean` alone with a sorry-free "
        f"direct proof (leaf-bypass)\n"
        f"(c) `{attempts_dir}/patch.lean` with `-- decline: unprovable` "
        f"+ counterexample\n"
        f"(d) bail — write `{attempts_dir}/_progress.md` only, exit. "
        f"No `patch.lean`. Capture in ≤200 words: shape converging to, "
        f"sub-pieces with clear name+statement, the specific blocker, "
        f"alternative direction (≤60 words).\n\n"
        f"Act now. {rescue_min} minutes left."
    )


SpawnFn = Callable[[SpawnCtx], int]
ParseFn = Callable[[], PipelineResult]
PostmortemFn = Callable[[str], None]
ReflectionFn = Callable[[str, "PipelineResult"], None]
# Death-cause feedback hook: called for an infra death (no resumable
# session) so the framework can write the cause the agent can't self-report.
DeathFn = Callable[["PipelineResult"], None]


@dataclass
class _TakeoverOutcome:
    """Result of a combined fresh-sid takeover.

    `terminal_result`: the PipelineResult to attach when the takeover
        reached a terminal outcome (success / decline). None when the
        single fresh spawn failed to converge — caller buffers
        `agent_stuck_thinking` and continues the retry loop.
    `last_sid`: the fresh sid used. Subsequent warm retries within the
        same pipeline use this sid; the broken sid is permanently
        abandoned.
    `detail_parts`: forensic strings describing trigger, rc, duration,
        and parse outcome; the caller joins these into `failure_detail`
        when buffering `agent_stuck_thinking`.
    `stage2_rc`: subprocess rc of the takeover spawn. `stage3_rc` is
        retained for back-compat (legacy 2-stage path); always None
        now that the combined path is the only caller.
    """
    terminal_result: PipelineResult | None
    last_sid: str
    detail_parts: list
    stage2_rc: int
    stage3_rc: int | None


def _derive_stage2_budget(workspace: Path | None) -> int:
    """Stage 2 budget = spawn_timeout - trap_check_sec. Replaces the
    retired `dispatch.rescue_timeout_sec` config (2026-05-10 v4)."""
    from ..core import config as _cfg
    from ..agent import WORKER_TIMEOUT_SEC
    spawn_timeout = _cfg.get(
        "dispatch.spawn_timeout_sec",
        default=WORKER_TIMEOUT_SEC,
        env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int,
        workspace=workspace,
    )
    trap_check_sec = _cfg.get(
        "dispatch.trap_check_sec",
        default=660,
        env_var="ASTERISM_TRAP_CHECK_SEC", cast=int,
        workspace=workspace,
    )
    # Mirror watchdog's floor; never let stage 2 go negative.
    return max(60, spawn_timeout - trap_check_sec)


def _build_force_progress_prompt(attempts_dir: Path,
                                 trapped_jsonl: Path,
                                 jsonl_copied: bool) -> str:
    """Cold-prompt for the trap-aware forced progress spawn. Tells the
    fresh agent it is NOT in the trapped conversation, points at the
    trapped session's jsonl as read-only input, and constrains the
    deliverable to a single `_progress.md` write — no tool use beyond
    Read of the jsonl and Write of `_progress.md`."""
    if jsonl_copied:
        log_note = (
            f"The previous takeover session deadlocked in thinking "
            f"mode and produced no usable output. Its full conversation "
            f"log is at `{trapped_jsonl}`. Read it (use offset/limit "
            f"for large files) to recover whatever concrete reasoning "
            f"the trapped agent reached before getting stuck."
        )
    else:
        log_note = (
            "The previous takeover session deadlocked in thinking mode "
            f"and its conversation log could not be recovered. Work "
            f"from `{attempts_dir}/Context.md` alone."
        )
    return (
        f"You are a fresh session brought in only to write a "
        f"checkpoint note. {log_note}\n\n"
        f"Constraints:\n"
        f"  - Do NOT modify `{attempts_dir}/patch.lean`.\n"
        f"  - Do NOT call MCP / Bash / Edit / Write on any file other "
        f"than `{attempts_dir}/_progress.md`.\n"
        f"  - Single Write: `{attempts_dir}/_progress.md` then exit.\n\n"
        f"In ≤200 words capture: (1) the shape of decomposition / "
        f"proof the trapped agent was converging to, (2) the specific "
        f"blocker that prevented shipping, (3) the most promising "
        f"alternative direction (≤60 words). This file is the only "
        f"thing the next dispatch on this goal will see from the "
        f"current attempt — make it concrete, name the Mathlib "
        f"lemmas or sub-shapes you'd try next."
    )


def _force_progress_fresh_cold(
    *, trapped_sid: str, attempts_dir: Path,
    spawn_fn: SpawnFn, workspace: Path | None,
) -> None:
    """Mint another fresh sid and cold-spawn a progress-only agent
    that reads the trapped session's jsonl and ships `_progress.md`.

    Mirrors the 722472d fresh-rescue mechanism, applied one level
    deeper: the *combined takeover's* fresh sid itself got stuck in
    a thinking trap, so `--resume`-style postmortem cannot reach it.
    A second fresh sid resumes nothing — it just reads the trapped
    jsonl as input data and writes the checkpoint note.

    Best-effort throughout: any failure is swallowed; the caller's
    existing detail_parts record the outcome via the progress file's
    existence check.
    """
    from ..core import config as _cfg

    trapped_jsonl_dest = attempts_dir / "_broken_session_combined.jsonl"
    jsonl_copied = _copy_broken_session_jsonl(trapped_sid, trapped_jsonl_dest)

    # Short budget for a markdown-write-only spawn. 180s mirrors the
    # legacy postmortem budget; cap from
    # `dispatch.postmortem_timeout_sec` so operators can shorten via
    # config if desired.
    from ..agent import POSTMORTEM_TIMEOUT_SEC
    budget = _cfg.get(
        "dispatch.postmortem_timeout_sec",
        default=POSTMORTEM_TIMEOUT_SEC,
        env_var="ASTERISM_POSTMORTEM_TIMEOUT_SEC", cast=int,
        workspace=workspace,
    )
    prompt = _build_force_progress_prompt(
        attempts_dir, trapped_jsonl_dest, jsonl_copied)
    fresh_sid = str(uuid.uuid4())
    print(f"[force-progress fresh-cold] trapped_sid={trapped_sid[:8]} → "
          f"fresh_sid={fresh_sid[:8]} budget={budget}s "
          f"jsonl_copied={jsonl_copied}", flush=True)
    try:
        rc = spawn_fn(SpawnCtx(
            sid=fresh_sid, cold=True, retry_context=None,
            attempts_dir=attempts_dir,
            inline_prompt=prompt,
            budget_override=budget,
        ))
    except Exception as exc:  # noqa: BLE001 — best-effort
        print(f"[force-progress fresh-cold] fresh_sid={fresh_sid[:8]} "
              f"spawn raised {type(exc).__name__}: {exc}", flush=True)
        return
    print(f"[force-progress fresh-cold] fresh_sid={fresh_sid[:8]} "
          f"rc={rc}", flush=True)


def _run_fresh_sid_combined_takeover(
    *, broken_sid: str, broken_sid_label: str,
    attempts_dir: Path, workspace: Path | None,
    spawn_fn: SpawnFn, parse_fn: ParseFn,
    postmortem_fn: "PostmortemFn | None" = None,
) -> _TakeoverOutcome:
    """Single-stage fresh-sid takeover used by both thinking-trap
    paths (watchdog STUCK_THINKING and subprocess timeout-trap).
    Combined budget = stage2 + stage3 (postmortem); one spawn handles
    ship-or-bail in a single window.

    Why one stage instead of two:
      When parser flags `is_thinking_trap`, the broken jsonl carries
      only thinking text — no concrete decomposition. Stage 3 (which
      asks the agent to extract a `_progress.md` from the jsonl) adds
      little value over stage 2's option (d) bail in this case. The
      previous 2-stage path (`_run_fresh_sid_takeover`, removed
      2026-05-18) was based on a since-falsified assumption that the
      timeout-trap broken jsonl might carry salvageable concrete
      reasoning the agent didn't get to ship — in practice
      `is_thinking_trap=True` means it doesn't.

    Returns _TakeoverOutcome with `stage3_rc=None` always (no stage 3
    fired). Forensic detail says `combined sid=... rc=... dur=...`.
    """
    broken_jsonl_dest = attempts_dir / "_broken_session.jsonl"
    jsonl_copied = _copy_broken_session_jsonl(
        broken_sid, broken_jsonl_dest)

    # Budget = stage 2 alone (= spawn_timeout - trap_check_sec, default
    # 240s / 4min). The legacy 2-stage path totalled stage2+postmortem
    # = ~7min, but in practice the agent either bails fast (<1min,
    # write _progress.md and exit) or ships fast (a couple of
    # validate_file cycles); past 4 min the spawn isn't producing new
    # information. Tighter cap = faster failure → next retry iteration
    # sooner overall.
    combined_budget = _derive_stage2_budget(workspace)
    combined_min = max(1, combined_budget // 60)
    # Reuse stage 2 prompt — it already covers ship (a/b/c) AND bail
    # (option d: write `_progress.md` only). The agent gets ~7 min
    # to either ship or write progress note.
    combined_prompt = _build_fresh_rescue_stage2_prompt(
        attempts_dir, jsonl_copied, combined_min)
    sid_combined = str(uuid.uuid4())
    print(f"[fresh-rescue combined] broken_sid={broken_sid[:8]} → "
          f"fresh_sid={sid_combined[:8]} budget={combined_budget}s "
          f"jsonl_copied={jsonl_copied}", flush=True)
    t0 = time.monotonic()
    rc = spawn_fn(SpawnCtx(
        sid=sid_combined, cold=True, retry_context=None,
        attempts_dir=attempts_dir,
        inline_prompt=combined_prompt,
        budget_override=combined_budget,
    ))
    dur = time.monotonic() - t0
    print(f"[fresh-rescue combined] sid={sid_combined[:8]} "
          f"rc={rc} dur={dur:.0f}s", flush=True)

    result: PipelineResult | None = None
    try:
        result = parse_fn()
    except Exception as exc:  # noqa: BLE001
        print(f"[fresh-rescue combined] sid={sid_combined[:8]} "
              f"parse raised {type(exc).__name__}: {exc}", flush=True)

    detail_parts = [
        broken_sid_label,
        f"combined sid={sid_combined[:8]} rc={rc} dur={dur:.0f}s",
    ]
    if result is not None:
        detail_parts.append(
            f"combined parse: reason={result.failure_reason} "
            f"detail={(result.failure_detail or '')[:120]}")

    if result is not None and (
        result.outcome in _TERMINAL_SUCCESS_OUTCOMES
        or result.failure_reason in _TERMINAL_DECLINE_REASONS
    ):
        print(f"[fresh-rescue combined] sid={sid_combined[:8]} "
              f"attached outcome={result.outcome} "
              f"reason={result.failure_reason}", flush=True)
        return _TakeoverOutcome(
            terminal_result=result,
            last_sid=sid_combined,
            detail_parts=detail_parts,
            stage2_rc=int(rc),
            stage3_rc=None,
        )

    # Forced-progress fallback (residue_thm 2026-05-21 observation):
    # combined takeover frequently ends without shipping AND without
    # writing `_progress.md` — agent picked the ship path (options
    # a/b/c), produced patch.lean that fails downstream parse / verify
    # (e.g. agent_no_annotation, signature mismatch, sorry-stub) within
    # budget, so no timeout fires and the bail-and-write-progress path
    # (option d) is never taken. The next attempt on the same goal
    # then starts blind without any carry-over hint about what just
    # failed.
    #
    # Two branches depending on whether the combined fresh sid itself
    # got stuck in a thinking trap:
    #
    #   * NOT-trap (combined sid finalized / mid-tool, just no result
    #     of interest) → `--resume sid_combined` postmortem is safe.
    #     Same mechanism as the active-timeout `postmortem_fn(sid)`
    #     path in the main retry loop. The agent receives a new user
    #     message instructing it to write `_progress.md`; for an active
    #     session, that prompt elicits a response.
    #
    #   * THINKING-TRAP (combined sid itself dead-locked in thinking
    #     after spawn timeout — residue_thm 2026-05-21 g2601/g2603/
    #     g2604 pattern) → `--resume` re-enters the trap and produces
    #     0 events, the very failure mode that motivated commit
    #     722472d (fresh-rescue: abandon broken session, dump thinking,
    #     fresh cold spawn). We mirror that design: copy the combined
    #     sid's jsonl into the sandbox, mint another fresh sid, and
    #     cold-spawn a short progress-only prompt. The new agent reads
    #     the broken jsonl and ships a `_progress.md` without ever
    #     being part of the trapped conversation.
    #
    # Fire only when combined didn't reach a terminal outcome AND
    # `_progress.md` is missing (option-d note absent).
    progress_path = attempts_dir / "_progress.md"
    if not progress_path.exists():
        combined_state = _read_parser_state(attempts_dir)
        combined_trap = bool(
            combined_state and combined_state.get("is_thinking_trap"))
        if combined_trap:
            _force_progress_fresh_cold(
                trapped_sid=sid_combined,
                attempts_dir=attempts_dir,
                spawn_fn=spawn_fn,
                workspace=workspace,
            )
            wrote = progress_path.exists()
            detail_parts.append(
                f"forced-progress: trap-fresh wrote={wrote}")
        elif postmortem_fn is not None:
            print(f"[fresh-rescue combined] sid={sid_combined[:8]} no "
                  f"terminal result and no _progress.md — forcing "
                  f"--resume postmortem (combined sid not trapped)",
                  flush=True)
            try:
                postmortem_fn(sid_combined)
            except Exception as exc:  # noqa: BLE001 — best-effort
                print(f"[fresh-rescue forced-progress] sid="
                      f"{sid_combined[:8]} postmortem raised "
                      f"{type(exc).__name__}: {exc}", flush=True)
            wrote = progress_path.exists()
            detail_parts.append(
                f"forced-progress: resume wrote={wrote}")

    return _TakeoverOutcome(
        terminal_result=None,
        last_sid=sid_combined,
        detail_parts=detail_parts,
        stage2_rc=int(rc),
        stage3_rc=None,
    )


def _read_parser_state(attempts_dir: Path) -> dict | None:
    """Load the stream parser's final snapshot written by
    `Tooling/llm/claude_cli._persist_parser_state`. Returns None when
    the file is absent (non-stream-json spawn) or unparseable. Caller
    treats None as 'no detector data — assume active' (i.e. fall back
    to the legacy `--resume` postmortem path)."""
    try:
        text = (attempts_dir / "_parser_state.json").read_text(
            encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def run_with_session_retries(
    *,
    conn: sqlite3.Connection,
    goal_id: int | None,
    pipeline_id: str,
    budget_threshold: int,
    shelve_threshold: int,
    attempts_dir: Path,
    spawn_fn: SpawnFn,
    parse_fn: ParseFn,
    postmortem_fn: PostmortemFn,
    workspace: Path | None = None,
    reflection_fn: ReflectionFn | None = None,
    feedback_fn: "ReflectionFn | None" = None,
    death_fn: "DeathFn | None" = None,
    decision_id: int | None = None,
) -> PipelineResult:
    """Run a kind-agnostic in-pipeline retry loop.

    Flow per iteration:
      1. cascade re-check (against `shelve_threshold`); bail with
         outcome='moot' if goal terminated.
      2. spawn (cold on first iteration, warm on subsequent).
      3. classify rc:
         * STALE_SESSION on warm → in-place cold re-mint, retry once
           inside the same iteration (no budget consumed, no
           attempts++).
         * TIMEOUT → run postmortem, write dead_attempt, attempts++,
           return outcome='exhausted'.
         * spawn_fast_fail / quota_exhausted / missing_dep → return
           outcome='failed' immediately with the matching reason
           (infra noise; dispatcher applies cooldown). Prior-iteration
           pending_failures still flush; this iteration's failure is
           NOT recorded against the goal's budget.
         * other rc!=0 → write dead_attempt, attempts++, fall through
           to next iteration with the failure detail as retry_context.
      4. rc==0 → invoke `parse_fn`. Terminal outcomes (proved /
         success / agent_declined / agent_infeasible /
         goal_no_longer_open) return verbatim. Other failures
         (lake_build_error, forbidden_lemma, agent_no_annotation,
         ...) write dead_attempt, attempts++, continue.

    `budget_threshold` is the per-kind retry cap
    (`BUILDER_THRESHOLD` for Builder, `SHELVE_THRESHOLD` for Backward,
    `FORWARD_RETRY_BUDGET` for Forward).
    `shelve_threshold` is always the goals-level shelve cap; used in
    `goal_still_active` to detect external `_propagate_shelve` increments.

    `goal_id` is None for goal-less pipelines (Phase 2 Forward, which
    targets a problem name rather than a goal row). When None:
      - budget = budget_threshold directly (no goal.attempts decrement —
        each Forward Inject is independent of prior dispatches).
      - cascade re-check via `goal_still_active` is skipped (no goal to
        check; the originating Strategist Inject already authorised
        this pipeline; Strategist self-feedback handles convergence).
      - `buffer_failure` skips `increment_goal_attempts` + TREE refresh
        (no goal counters to bump, no tree edge to redraw).
      Forensic dead_attempts still buffer through `pending_failures`;
      the dispatcher flushes them with target_kind='Problem'.

    On budget exhaustion without a terminal outcome, returns
    outcome='exhausted' carrying the most recent failure reason/detail
    for forensic visibility.
    """
    if goal_id is not None:
        goal = db.get_goal(conn, goal_id)
        if goal is None:
            return PipelineResult(outcome="failed",
                                  failure_reason="goal_not_found")
        if decision_id is not None:
            # Strategist Inject authored this dispatch with full knowledge
            # of the goal's attempts history (failure_replay section in
            # the Strategist context). Honour that with a fresh budget
            # instead of subtracting prior attempts — otherwise Inject
            # on a goal at/above budget_threshold moots immediately and
            # silently no-ops the Strategist decision (LU lu_step_assembly
            # 2026-05-28). The absolute upper bound is now Strategist's
            # own ConfirmShelve discipline, not a framework attempts cap.
            budget = budget_threshold
        else:
            budget = budget_threshold - int(goal["attempts"])
        if budget <= 0:
            # Defensive — bfs_refill should already filter goals at/over
            # threshold. Reach here only on dispatch races.
            print(f"[retry-moot] g{goal_id} pre-loop: budget={budget} "
                  f"(budget_threshold={budget_threshold} - "
                  f"attempts={int(goal['attempts'])}); status="
                  f"{goal['status']}", flush=True)
            return PipelineResult(outcome="moot")
    else:
        # Goal-less pipeline (Forward): budget is the per-Inject cap;
        # no prior attempts to subtract from.
        budget = budget_threshold

    sid = str(uuid.uuid4())
    last_reason: str = ""
    last_detail: str = ""
    pending_failures: list[dict] = []

    def buffer_failure(reason: str, detail: str, proposal_md: str = "") -> None:
        # Snapshot agent output BEFORE next iteration's framework-side
        # mutations (Builder backup restore / Backward proofs unlink)
        # so each record captures the agent state at failure time.
        pending_failures.append({
            "reason": reason,
            "detail": detail,
            "proposal_md": proposal_md,
            "artifacts": collect_artifacts(attempts_dir),
        })
        # Eager attempts++ for live operator visibility (TREE.md +
        # `asterism status` show retry progress mid-pipeline). The
        # paired dead_attempts row is still buffered for FK ordering
        # (pipelines.id FK target written by dispatcher post-return);
        # crash mid-pipeline leaves attempts inflated by N relative to
        # dead_attempts, but the drift is cosmetic — bfs_refill /
        # threshold checks treat attempts as authoritative either way.
        #
        # Goal-less pipelines (Forward, goal_id=None) skip both: no
        # goal.attempts to increment and no goal-rooted tree edge to
        # redraw. The Forward dispatch path also writes its own
        # `## Forward` subtree on cascade (tree.py:render).
        if goal_id is not None:
            db.increment_goal_attempts(conn, goal_id)
            if workspace is not None:
                tree.write_for_target(conn, workspace, str(goal_id), "Goal")

    def attach(result: PipelineResult) -> PipelineResult:
        # Always thread the buffered failures through the return value.
        # Caller (`dispatcher._run_pipeline`) flushes them after the
        # pipelines row INSERT.
        result.pending_failures = pending_failures
        _maybe_reflect(result)
        return result

    def _maybe_reflect(result: PipelineResult) -> None:
        # Reflection trigger gate (decision 5 from agent_brief_lessons
        # design): proved / success / exhausted plus all decline
        # directives that signal real agent learning. Skip moot (no
        # agent ran), goal_no_longer_open (race-detected, no learning),
        # and infra rcs (spawn_fast_fail / quota_exhausted / missing_dep).
        if result.outcome == "moot":
            return  # no agent ran — neither feedback nor reflection
        # Death-cause feedback: an infra death (no resumable session) can't
        # self-report, so the framework writes its cause. Independent of
        # reflection (fires even when reflection_fn is None). goal_no_longer_
        # open is a race, not a death — neither.
        if result.failure_reason in (
            "spawn_fast_fail", "quota_exhausted", "missing_dep",
        ):
            if death_fn is not None:
                try:
                    death_fn(result)
                except Exception as exc:  # noqa: BLE001 — best-effort
                    print(f"[feedback] death callback raised, swallowed — "
                          f"{exc}", flush=True)
            return
        if result.failure_reason == "goal_no_longer_open":
            return
        triggered = (
            result.outcome in ("proved", "success", "exhausted")
            or result.failure_reason in (
                "agent_declined",       # needs_decomposition directive
                "agent_infeasible",     # unprovable directive
                "parent_needs_fix",     # return_to_parent directive
                "agent_shelved",        # shelve directive
            )
        )
        if not triggered:
            return
        # Framework feedback runs as its OWN tail step, INDEPENDENT of reflection
        # — it fires for every pipeline that ran to a real terminal (incl.
        # Forward, which passes no reflection_fn). Same `--resume <sid>` session.
        if feedback_fn is not None:
            try:
                feedback_fn(sid, result)
            except Exception as exc:  # noqa: BLE001 — best-effort
                print(f"[feedback] callback raised, swallowed: {exc}",
                      flush=True)
        if reflection_fn is not None:
            try:
                reflection_fn(sid, result)
            except Exception as exc:  # noqa: BLE001 — best-effort
                print(f"[reflection] callback raised, swallowed: {exc}",
                      flush=True)

    for attempt in range(budget):
        # Dispatcher abort (budget exceeded / gateway permadown):
        # `claude_cli.request_shutdown` killed any in-flight subprocess
        # so we're back at the loop top. Bail before launching a fresh
        # claude invocation so the worker thread exits in seconds and
        # ThreadPoolExecutor join completes promptly. No dead_attempt
        # write — this is daemon teardown, not a real agent failure.
        if claude_cli.is_shutdown_requested():
            return attach(PipelineResult(
                outcome="failed",
                failure_reason="daemon_shutdown",
                failure_detail="dispatcher exiting; retry loop bailed",
            ))
        # Cascade re-check only applies to goal-bound pipelines (the
        # check looks at goals.status / attempts). Goal-less pipelines
        # (Forward) skip — the Strategist Inject already authorised
        # this dispatch and there's no goal cascade to race against.
        if goal_id is not None and not goal_still_active(
            conn, goal_id, shelve_threshold, decision_id=decision_id,
        ):
            g_now = db.get_goal(conn, goal_id)
            if g_now is None:
                print(f"[retry-moot] g{goal_id} iter={attempt}: "
                      f"goal row vanished", flush=True)
            else:
                print(f"[retry-moot] g{goal_id} iter={attempt}: "
                      f"status={g_now['status']} attempts={g_now['attempts']} "
                      f"shelve_threshold={shelve_threshold} "
                      f"decision_id={decision_id}", flush=True)
            return attach(PipelineResult(outcome="moot"))

        cold = (attempt == 0)
        spawn_t0 = time.monotonic()
        rc = spawn_fn(SpawnCtx(sid=sid, cold=cold,
                               retry_context=last_detail or None,
                               retry_reason=last_reason or None,
                               attempts_dir=attempts_dir))
        spawn_dur = time.monotonic() - spawn_t0

        # Stale session fallback (decision 4): only meaningful on warm
        # attempts where --resume looks at an on-disk session that
        # might have been GC'd. Cold attempts mint fresh ids and use
        # --session-id, so rc=125 there is a genuine error and falls
        # through to the generic rc!=0 branch.
        if rc == SpawnRC.STALE_SESSION and not cold:
            sid = str(uuid.uuid4())
            spawn_t0 = time.monotonic()
            rc = spawn_fn(SpawnCtx(sid=sid, cold=True,
                                   retry_context=last_detail or None,
                                   retry_reason=last_reason or None,
                                   attempts_dir=attempts_dir))
            spawn_dur = time.monotonic() - spawn_t0

        # Shutdown short-circuit: spawn_llm saw the dispatcher abort
        # flag and returned without invoking the CLI. Treat as terminal
        # no-retry. No dead_attempt write (no real failure happened).
        if rc == SpawnRC.SHUTDOWN:
            return attach(PipelineResult(
                outcome="failed",
                failure_reason="daemon_shutdown",
                failure_detail="spawn aborted; dispatcher exiting",
            ))

        # Provider-level infrastructure failures: bail without
        # consuming budget. Dispatcher applies cooldown (and, for
        # spawn_fast_fail only, CONSEC tracking).
        #   * 126 / QUOTA_EXHAUSTED — provider rate limit / quota cap.
        #   * 127 / MISSING_DEP    — CLI binary missing / not installed.
        # Treated symmetrically to spawn_fast_fail (wall<10s + rc!=0)
        # but classified by rc rather than wall time so a long quota
        # check still routes here.
        if rc == SpawnRC.QUOTA_EXHAUSTED:
            return attach(PipelineResult(
                outcome="failed", failure_reason="quota_exhausted",
                failure_detail=f"agent rc={rc} (quota / rate limit)"))
        if rc == SpawnRC.MISSING_DEP:
            return attach(PipelineResult(
                outcome="failed", failure_reason="missing_dep",
                failure_detail=f"agent rc={rc} (CLI missing / not installed)"))

        if rc == SpawnRC.TIMEOUT:
            # Decision 3 (revised 2026-05-10 v3): salvage parse first,
            # then check parser final state. The salvage path captures
            # active-but-cargo-cult agents (s220-class: patch + subs
            # already on disk, agent ran extra `ls` past natural exit
            # → subprocess.TimeoutExpired). Salvage failure means the
            # on-disk output is genuinely malformed/incomplete, OR the
            # agent never reached the writing phase because it was
            # stuck in thinking.
            #
            # The parser-state check (added 2026-05-10) discriminates
            # the salvage-fail population:
            #   * thinking trap (state=mid-thinking OR finalized +
            #     stop_reason=max_tokens) → fresh-sid takeover, same
            #     mechanism as the watchdog STUCK_THINKING branch.
            #     `--resume` postmortem on a thinking-trapped session
            #     re-enters the same trap (s219 cb7e1cde evidence:
            #     180s postmortem produced 0 events).
            #   * active (anything else) → keep `--resume` postmortem.
            #     Active agents at subprocess timeout were emitting
            #     tool_use right up to the kill; --resume picks up
            #     where they left off and a 180s budget is enough for
            #     a recap-style _progress.md.
            #
            # Pre-existing risk note: parse_fn can mutate DB / disk
            # mid-execution and raise without rollback. This risk
            # exists on the rc=0 path too; salvage doesn't introduce
            # new risk, only exposes it to one more rc.
            salvage_note = ""
            timeout_result: PipelineResult | None = None
            try:
                timeout_result = parse_fn()
            except Exception as exc:  # noqa: BLE001 — best-effort
                salvage_note = (f"salvage parse raised "
                                f"{type(exc).__name__}: {exc}")
                print(f"[timeout-salvage] sid={sid[:8]} {salvage_note}; "
                      f"falling back to postmortem", flush=True)
            if timeout_result is not None and (
                timeout_result.outcome in _TERMINAL_SUCCESS_OUTCOMES
                or timeout_result.failure_reason
                in _TERMINAL_DECLINE_REASONS
            ):
                print(f"[timeout-salvage] sid={sid[:8]} salvaged "
                      f"outcome={timeout_result.outcome} "
                      f"reason={timeout_result.failure_reason} despite "
                      f"subprocess timeout", flush=True)
                return attach(timeout_result)

            # Salvage failed. Check parser final state for trap.
            parser_state = _read_parser_state(attempts_dir)
            state_label = (parser_state.get("state", "—")
                           if parser_state else "—")
            stop_label = (parser_state.get("last_stop_reason", "—")
                          if parser_state else "—")
            is_trap = (parser_state.get("is_thinking_trap", False)
                       if parser_state else False)

            if is_trap:
                broken_sid = sid
                print(f"[timeout-trap] sid={broken_sid[:8]} parser "
                      f"detected trap (state={state_label} "
                      f"last_stop_reason={stop_label}); running "
                      f"combined fresh-sid takeover instead of "
                      f"--resume postmortem", flush=True)
                # Same as the watchdog STUCK_THINKING path below — when
                # parser sees a thinking trap, the broken jsonl carries
                # only mid-thinking text regardless of whether the kill
                # came from watchdog (mid-spawn) or subprocess timeout
                # (end-of-spawn). The legacy 2-stage path here was
                # carryover from when timeout-trap was assumed to have
                # salvageable concrete reasoning; in practice
                # `is_thinking_trap=True` means there isn't any.
                outcome = _run_fresh_sid_combined_takeover(
                    broken_sid=broken_sid,
                    broken_sid_label=(
                        f"subprocess timeout + thinking trap "
                        f"(state={state_label} "
                        f"last_stop_reason={stop_label}) "
                        f"broken_sid={broken_sid[:8]}"),
                    attempts_dir=attempts_dir, workspace=workspace,
                    spawn_fn=spawn_fn, parse_fn=parse_fn,
                    postmortem_fn=postmortem_fn,
                )
                sid = outcome.last_sid
                if outcome.terminal_result is not None:
                    return attach(outcome.terminal_result)
                buffer_failure("agent_stuck_thinking",
                               "; ".join(outcome.detail_parts))
                last_reason = "agent_stuck_thinking"
                last_detail = f"combined rc={outcome.stage2_rc}"
                continue

            # Active spawn at subprocess timeout — keep legacy
            # `--resume` postmortem. Capture failure detail FROM THE
            # MAIN SPAWN's _spawn.stderr BEFORE calling postmortem,
            # otherwise the postmortem spawn's own stderr (e.g. its
            # own 180s timeout) overwrites the main's "after 900s" and
            # operators reading dead_attempts.failure_detail get the
            # wrong wall budget. Fold the salvage parse outcome and
            # detector verdict into failure_detail so forensics can
            # distinguish: "agent wrote nothing usable"
            # (parse_proposal_fail) vs "agent wrote a broken patch"
            # (lake_build_error / patch_signature_mismatch / ...) vs
            # "salvage parse itself raised". Reason stays
            # `agent_timeout` so the operator-level "this is a
            # timeout" signal is not lost.
            reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
            postmortem_fn(sid)
            if timeout_result is not None:
                salvage_note = (
                    f"salvage parse: outcome={timeout_result.outcome} "
                    f"reason={timeout_result.failure_reason} detail="
                    f"{(timeout_result.failure_detail or '')[:200]}")
            if salvage_note:
                detail = f"{detail}; {salvage_note}"
            # Detector verdict: only assert "active" when the parser
            # state file actually exists. Missing file (non-stream-json
            # spawn, write IO error, future code path) → record
            # `unavailable` so operators don't misread "active" as a
            # detector observation when in reality nothing was sampled.
            if parser_state is not None:
                detail = (f"{detail}; [detector verdict: active "
                          f"state={state_label} "
                          f"last_stop_reason={stop_label}]")
            else:
                detail = f"{detail}; [detector verdict: unavailable]"
            buffer_failure(reason, detail)
            return attach(PipelineResult(outcome="exhausted",
                                         failure_reason=reason,
                                         failure_detail=detail))

        if rc == SpawnRC.STUCK_THINKING:
            # Watchdog detected thinking trap at trap_check_sec
            # (parser is_thinking_trap AND silence > threshold).
            # Same combined takeover as the timeout-trap branch above —
            # whichever signal flagged the thinking trap, the broken
            # jsonl carries only mid-thinking text, so stage 3's
            # extract-_progress.md task adds little value over stage
            # 2's bail option. Single fresh spawn handles ship-or-bail.
            broken_sid = sid
            outcome = _run_fresh_sid_combined_takeover(
                broken_sid=broken_sid,
                broken_sid_label=(
                    f"watchdog killed broken_sid={broken_sid[:8]}"),
                attempts_dir=attempts_dir, workspace=workspace,
                spawn_fn=spawn_fn, parse_fn=parse_fn,
                postmortem_fn=postmortem_fn,
            )
            sid = outcome.last_sid
            if outcome.terminal_result is not None:
                return attach(outcome.terminal_result)
            buffer_failure("agent_stuck_thinking",
                           "; ".join(outcome.detail_parts))
            last_reason = "agent_stuck_thinking"
            last_detail = f"combined rc={outcome.stage2_rc}"
            continue

        if rc != SpawnRC.OK:
            reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
            if reason == "spawn_fast_fail":
                # Infra noise (claude.exe crash / cwd). No dead_attempt
                # write, no attempts++ — dispatcher's cascade_one
                # applies cooldown + CONSEC tracking. Prior-iteration
                # buffered failures still flush; this iteration's
                # fast-fail itself is dropped.
                return attach(PipelineResult(outcome="failed",
                                             failure_reason=reason,
                                             failure_detail=detail))
            buffer_failure(reason, detail)
            last_reason, last_detail = reason, detail
            continue

        # rc == 0: kind-specific parse + commit
        result = parse_fn()
        if (result.outcome in _TERMINAL_SUCCESS_OUTCOMES
                or result.failure_reason in _TERMINAL_DECLINE_REASONS):
            return attach(result)

        # Non-terminal parse failure — buffer + retry
        buffer_failure(result.failure_reason, result.failure_detail,
                       result.proposal_md)
        last_reason, last_detail = result.failure_reason, result.failure_detail

    return attach(PipelineResult(outcome="exhausted",
                                 failure_reason=last_reason,
                                 failure_detail=last_detail))
