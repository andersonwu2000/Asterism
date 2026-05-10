"""In-pipeline retry helper (Phase 7).

Replaces cross-pipeline session passing (former F33 / F53) with an
in-pipeline retry loop sharing one claude session. Builder / Backward
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

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import db, tree
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
})


def goal_still_active(conn: sqlite3.Connection, goal_id: int,
                      shelve_threshold: int) -> bool:
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

    The loop returns `outcome="moot"` on False — no state mutation,
    no attempts++, no dead_attempt write.
    """
    g = db.get_goal(conn, goal_id)
    if g is None:
        return False
    if g["status"] not in ("open", "attempting"):
        return False
    if int(g["attempts"]) >= shelve_threshold:
        return False
    return True


# Fresh-rescue (2026-05-10, replaces prior STOP-then-rescue 2-phase
# design): when watchdog kills a spawn for stuck-thinking, abandon the
# broken session entirely. The session has typically hit
# `stop_reason=max_tokens` and any subsequent prompt re-enters the same
# deep-thinking pattern (probe + production evidence: --resume rescue
# spawns produce 0 events for full budget). Instead:
#
#   1. Extract all thinking blocks from the broken session's jsonl
#      and write them to `attempts_dir/_prior_analysis.md`.
#   2. Mint a fresh session id, abandoning the broken one.
#   3. Cold-spawn into the fresh session with a Read directive
#      requiring `_prior_analysis.md` first; agent picks up reasoning
#      from prior thinking and ships per the standard Backward task.
#
# Probe evidence (16176de5 → fresh sid 236ced1d, 2026-05-10): fresh
# session shipped patch.lean + sub-lemma stub in ~4 min, directly
# referencing the prior analysis (Kelly minimiser geometric argument).
# Compare to --resume rescue: 180s, 0 events. Fresh-rescue cost is
# higher (cold-start overhead + full spawn budget) but actually
# produces output, which the resume path didn't.
def _dump_prior_thinking(sid: str, out_path: Path) -> bool:
    """Extract all assistant thinking blocks from session `sid`'s jsonl
    and write them to `out_path`, in chronological order with
    timestamps. Returns True on success, False if jsonl missing /
    no thinking blocks. Best-effort — any error returns False so the
    caller can fall through gracefully."""
    import json as _json
    from ..llm.claude_cli import _find_session_jsonl
    log_path = _find_session_jsonl(sid)
    if log_path is None:
        return False
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    blocks: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            d = _json.loads(line)
        except (_json.JSONDecodeError, ValueError):
            continue
        if d.get("type") != "assistant":
            continue
        ts = d.get("timestamp", "")
        msg = d.get("message", {}) or {}
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for c in content:
            if isinstance(c, dict) and c.get("type") == "thinking":
                t = c.get("thinking", "")
                if t.strip():
                    blocks.append((ts, t))
    if not blocks:
        return False
    body = [
        f"# Prior in-flight analysis from killed session sid={sid[:8]}",
        "",
        f"This is the unfinished thinking from the previous spawn that "
        f"was killed for exceeding the wall-clock budget. The session "
        f"is abandoned; you are a fresh session resuming the work. "
        f"Use this to skip re-doing analysis from scratch.",
        "",
        f"{len(blocks)} thinking block(s) follow, in chronological order:",
        "",
    ]
    for ts, t in blocks:
        body.append(f"## Thinking block at {ts} ({len(t)} chars)")
        body.append("")
        body.append("```")
        body.append(t)
        body.append("```")
        body.append("")
    try:
        out_path.write_text("\n".join(body), encoding="utf-8")
    except OSError:
        return False
    return True


@dataclass
class SpawnCtx:
    """Per-attempt context handed to the kind-specific spawn callback.

    `cold=True` means the agent has no prior session to resume — either
    attempt 0 of a fresh pipeline, or a stale_session in-place re-mint,
    or a fresh-rescue (see `is_fresh_rescue`).

    `is_fresh_rescue=True` signals: the prior in-pipeline spawn was
    watchdog-killed for stuck-thinking; this spawn is a fresh-cold
    session (sid is freshly minted, broken session abandoned) with a
    `_prior_analysis.md` already written to attempts_dir. The spawn
    function should run normal cold-prep (Context.md compile, F52
    skeleton) AND signal the LLM provider to inject a Read directive
    requiring the agent to consume `_prior_analysis.md` before any
    other action. Mutually exclusive with normal cold (`cold=True`,
    `is_fresh_rescue=False`).
    """
    sid: str
    cold: bool
    retry_context: str | None
    attempts_dir: Path
    is_fresh_rescue: bool = False


SpawnFn = Callable[[SpawnCtx], int]
ParseFn = Callable[[], PipelineResult]
PostmortemFn = Callable[[str], None]
ReflectionFn = Callable[[str, "PipelineResult"], None]


def run_with_session_retries(
    *,
    conn: sqlite3.Connection,
    goal_id: int,
    pipeline_id: str,
    budget_threshold: int,
    shelve_threshold: int,
    attempts_dir: Path,
    spawn_fn: SpawnFn,
    parse_fn: ParseFn,
    postmortem_fn: PostmortemFn,
    workspace: Path | None = None,
    reflection_fn: ReflectionFn | None = None,
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
    (`BUILDER_THRESHOLD` for Builder, `SHELVE_THRESHOLD` for Backward).
    `shelve_threshold` is always the goals-level shelve cap; used in
    `goal_still_active` to detect external `_propagate_shelve` increments.

    On budget exhaustion without a terminal outcome, returns
    outcome='exhausted' carrying the most recent failure reason/detail
    for forensic visibility.
    """
    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed",
                              failure_reason="goal_not_found")

    budget = budget_threshold - int(goal["attempts"])
    if budget <= 0:
        # Defensive — bfs_refill should already filter goals at/over
        # threshold. Reach here only on dispatch races.
        return PipelineResult(outcome="moot")

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
        if reflection_fn is None:
            return
        if result.outcome == "moot":
            return
        if result.failure_reason in (
            "spawn_fast_fail", "quota_exhausted", "missing_dep",
            "goal_no_longer_open",
        ):
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
        try:
            reflection_fn(sid, result)
        except Exception as exc:  # noqa: BLE001 — best-effort
            print(f"[reflection] callback raised, swallowed: {exc}",
                  flush=True)

    for attempt in range(budget):
        if not goal_still_active(conn, goal_id, shelve_threshold):
            return attach(PipelineResult(outcome="moot"))

        cold = (attempt == 0)
        spawn_t0 = time.monotonic()
        rc = spawn_fn(SpawnCtx(sid=sid, cold=cold,
                               retry_context=last_detail or None,
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
                                   attempts_dir=attempts_dir))
            spawn_dur = time.monotonic() - spawn_t0

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
            # Decision 3 (revised 2026-05-10): salvage parse before
            # postmortem. The watchdog's idle-window guard
            # (Tooling/llm/claude_cli.py) defers wall_cap kills for
            # agents that are still emitting tool_use, leaving them
            # only `rescue_timeout_sec` seconds to wrap up before
            # subprocess timeout. Sonnet's empirical pattern is to
            # finish writing patch.lean + new_*.lean and then keep
            # running tool_use (extra `ls` self-checks, optional
            # `_progress.md` notes) past the natural exit point —
            # subprocess.TimeoutExpired fires, rc=124, files are valid
            # on disk but the old code path discarded them.
            #
            # Salvage: try parse_fn(); if it returns a terminal-
            # success outcome OR a terminal-decline directive (agent
            # explicitly signaled via patch.lean even mid-think), honor
            # it. Only fall through to postmortem + forced exhaust when
            # the on-disk output is genuinely incomplete / malformed.
            #
            # Pre-existing risk note: parse_fn can mutate DB / disk
            # mid-execution and raise without rollback. This risk
            # exists on the rc=0 path too (every successful spawn
            # invokes parse_fn the same way); salvage doesn't introduce
            # new risk, only exposes the same risk to one more rc.
            # Adding transactional wrapping is a separate refactor.
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
            # No salvage — capture failure detail FROM THE MAIN SPAWN's
            # _spawn.stderr BEFORE calling postmortem, otherwise the
            # postmortem spawn's own stderr (e.g. its own timeout
            # "TimeoutExpired after 180s") overwrites the main's
            # "TimeoutExpired after 900s" and operators reading
            # dead_attempts.failure_detail get the wrong wall budget.
            # Fold the salvage parse outcome into failure_detail so
            # forensics can distinguish "agent wrote nothing usable"
            # (parse_proposal_fail) from "agent wrote a broken patch"
            # (lake_build_error / patch_signature_mismatch / ...) from
            # "salvage parse itself raised". Reason stays `agent_timeout`
            # so the operator-level "this is a timeout" signal is not
            # lost — TIMEOUT remains the primary classification.
            reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
            postmortem_fn(sid)
            if timeout_result is not None:
                salvage_note = (
                    f"salvage parse: outcome={timeout_result.outcome} "
                    f"reason={timeout_result.failure_reason} detail="
                    f"{(timeout_result.failure_detail or '')[:200]}")
            if salvage_note:
                detail = f"{detail}; {salvage_note}"
            buffer_failure(reason, detail)
            return attach(PipelineResult(outcome="exhausted",
                                         failure_reason=reason,
                                         failure_detail=detail))

        if rc == SpawnRC.STUCK_THINKING:
            # Watchdog killed the spawn for >idle_window_sec without any
            # tool_use event in the session jsonl — Sonnet's runaway-
            # thinking trap. Fresh-rescue (2026-05-10, replaces prior
            # 2-phase STOP-then-rescue):
            #
            # Probe + production evidence: a session that has hit
            # `stop_reason=max_tokens` cannot be rescued via --resume —
            # any subsequent prompt re-enters the deep-thinking pattern
            # (production: 0 events for full 180s rescue budget). The
            # session is effectively dead. Trying to interrupt-and-
            # resume doesn't work; abandon and reuse only the thinking.
            #
            # Steps:
            #   1. Dump all thinking blocks from the broken session jsonl
            #      to attempts_dir/_prior_analysis.md. The agent's prior
            #      reasoning is preserved as a file, not lost with the
            #      session.
            #   2. Mint a fresh session id; replace `sid` permanently
            #      so subsequent warm retries within this pipeline use
            #      the fresh session, not the broken one.
            #   3. Cold-spawn into the fresh session with
            #      `is_fresh_rescue=True`; the spawn function injects
            #      a Read directive so the agent consumes
            #      `_prior_analysis.md` before any other action.
            #
            # Probe (16176de5 → fresh sid 236ced1d, 2026-05-10): fresh
            # session shipped patch.lean + sub-lemma stub in ~4 min,
            # directly referencing the prior reasoning. Compare to
            # --resume rescue: 180s, 0 events.
            #
            # Rescue success → attach. Rescue failure → record as a
            # buffered `agent_stuck_thinking` and continue the retry
            # loop (which now uses the fresh sid for any warm retries).
            broken_sid = sid
            prior_path = attempts_dir / "_prior_analysis.md"
            dumped = _dump_prior_thinking(broken_sid, prior_path)
            sid = str(uuid.uuid4())
            print(f"[fresh-rescue] broken_sid={broken_sid[:8]} → "
                  f"fresh_sid={sid[:8]}; prior_analysis_dumped={dumped}",
                  flush=True)
            rescue_t0 = time.monotonic()
            rescue_rc = spawn_fn(SpawnCtx(
                sid=sid, cold=True, retry_context=None,
                attempts_dir=attempts_dir,
                is_fresh_rescue=True,
            ))
            rescue_dur = time.monotonic() - rescue_t0
            print(f"[fresh-rescue] sid={sid[:8]} rc={rescue_rc} "
                  f"dur={rescue_dur:.0f}s", flush=True)
            if rescue_rc == SpawnRC.OK:
                rescue_result = parse_fn()
                if (rescue_result.outcome in _TERMINAL_SUCCESS_OUTCOMES
                        or rescue_result.failure_reason
                        in _TERMINAL_DECLINE_REASONS):
                    return attach(rescue_result)
                # Rescue ran but parse didn't reach terminal — fall
                # through and let the next iteration retry normally
                # (subsequent warm retries use the fresh sid).
                buffer_failure(rescue_result.failure_reason,
                               rescue_result.failure_detail,
                               rescue_result.proposal_md)
                last_reason = rescue_result.failure_reason
                last_detail = rescue_result.failure_detail
                continue
            # Rescue itself failed — record stuck-thinking and continue.
            buffer_failure("agent_stuck_thinking",
                           f"watchdog killed broken_sid={broken_sid[:8]}; "
                           f"fresh-rescue sid={sid[:8]} rc={rescue_rc} "
                           f"dur={rescue_dur:.0f}s")
            last_reason = "agent_stuck_thinking"
            last_detail = f"fresh-rescue rc={rescue_rc}"
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
