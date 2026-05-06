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
    "agent_declined", "agent_infeasible", "goal_no_longer_open",
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


@dataclass
class SpawnCtx:
    """Per-attempt context handed to the kind-specific spawn callback.

    `cold=True` means the agent has no prior session to resume — either
    attempt 0 of a fresh pipeline, or a stale_session in-place re-mint.
    Callers that need to write framework-side scratch (Builder
    compile_context, Backward F52 skeleton) gate that work on `cold`.
    """
    sid: str
    cold: bool
    retry_context: str | None
    attempts_dir: Path


SpawnFn = Callable[[SpawnCtx], int]
ParseFn = Callable[[], PipelineResult]
PostmortemFn = Callable[[str], None]


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
        return result

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
            # Decision 3: timeout → postmortem on the killed session,
            # then forced exhaust. Postmortem writes _progress.md
            # which the outer wrapper persists into .drafts/ for the
            # next cold pipeline to read.
            postmortem_fn(sid)
            reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
            buffer_failure(reason, detail)
            return attach(PipelineResult(outcome="exhausted",
                                         failure_reason=reason,
                                         failure_detail=detail))

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
