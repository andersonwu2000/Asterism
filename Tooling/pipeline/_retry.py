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

Phase 7-A scaffolding only — no caller wired yet. Phase 7-B/7-C wires
this into builder.py / backward.py and removes cascade_one's redundant
attempts++ / record_dead_attempt for Builder/Backward failures.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import db
from ..llm.base import SpawnRC
from . import PipelineResult, _spawn_failure, collect_artifacts


# Outcomes that terminate the retry loop without further attempts.
# `proved` (Builder success), `success` (Backward strategy commit).
_TERMINAL_SUCCESS_OUTCOMES = frozenset({"proved", "success"})

# Failure reasons that the agent *intentionally* signaled and that the
# retry loop must not paper over with another spawn. `agent_declined`
# burns Builder budget through cascade routing; `agent_infeasible`
# escapes the goal upward via _propagate_shelve. Either way the loop
# stops here and returns to dispatcher cascade.
_TERMINAL_DECLINE_REASONS = frozenset({"agent_declined", "agent_infeasible"})


def goal_still_active(conn: sqlite3.Connection, goal_id: int,
                      shelve_threshold: int) -> bool:
    """Cascade re-check before each retry-loop spawn. Returns False
    when a parallel cascade has already terminated the goal:
      * goal row missing (race / DB drift)
      * status no longer 'open' / 'attempting' (sibling proved /
        explicit shelve / propagated shelve)
      * attempts already at threshold (next cascade tick will shelve)

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
    threshold: int,
    attempts_dir: Path,
    spawn_fn: SpawnFn,
    parse_fn: ParseFn,
    postmortem_fn: PostmortemFn,
) -> PipelineResult:
    """Run a kind-agnostic in-pipeline retry loop.

    Flow per iteration:
      1. cascade re-check; bail with outcome='moot' if goal terminated.
      2. spawn (cold on first iteration, warm on subsequent).
      3. classify rc:
         * STALE_SESSION on warm → in-place cold re-mint, retry once
           inside the same iteration (no budget consumed, no
           attempts++).
         * TIMEOUT → run postmortem, write dead_attempt, attempts++,
           return outcome='exhausted'.
         * spawn_fast_fail → return outcome='failed' immediately (infra
           noise; dispatcher's CONSEC tracking + cooldown handle it).
         * other rc!=0 → write dead_attempt, attempts++, fall through
           to next iteration with the failure detail as retry_context.
      4. rc==0 → invoke `parse_fn`. Terminal outcomes (proved /
         success / agent_declined / agent_infeasible) return verbatim.
         Other failures (lake_build_error, forbidden_lemma,
         agent_no_annotation, ...) write dead_attempt, attempts++,
         continue.

    On budget exhaustion without a terminal outcome, returns
    outcome='exhausted' carrying the most recent failure reason/detail
    for forensic visibility.
    """
    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed",
                              failure_reason="goal_not_found")

    budget = threshold - int(goal["attempts"])
    if budget <= 0:
        # Defensive — bfs_refill should already filter goals at/over
        # threshold. Reach here only on dispatch races.
        return PipelineResult(outcome="moot")

    sid = str(uuid.uuid4())
    last_reason: str = ""
    last_detail: str = ""

    for attempt in range(budget):
        if not goal_still_active(conn, goal_id, threshold):
            return PipelineResult(outcome="moot")

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

        if rc == SpawnRC.TIMEOUT:
            # Decision 3: timeout → postmortem on the killed session,
            # then forced exhaust. Postmortem writes _progress.md
            # which the outer wrapper persists into .drafts/ for the
            # next cold pipeline to read.
            postmortem_fn(sid)
            reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
            _record_failure(conn, goal_id=goal_id,
                            pipeline_id=pipeline_id,
                            attempts_dir=attempts_dir,
                            reason=reason, detail=detail,
                            proposal_md="")
            return PipelineResult(outcome="exhausted",
                                  failure_reason=reason,
                                  failure_detail=detail)

        if rc != SpawnRC.OK:
            reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
            if reason == "spawn_fast_fail":
                # Infra noise (claude.exe crash / cwd / quota). No
                # dead_attempt write, no attempts++ — dispatcher's
                # cascade_one applies the 30s per-target cooldown and
                # CONSEC tracking instead.
                return PipelineResult(outcome="failed",
                                      failure_reason=reason,
                                      failure_detail=detail)
            _record_failure(conn, goal_id=goal_id,
                            pipeline_id=pipeline_id,
                            attempts_dir=attempts_dir,
                            reason=reason, detail=detail,
                            proposal_md="")
            last_reason, last_detail = reason, detail
            continue

        # rc == 0: kind-specific parse + commit
        result = parse_fn()
        if (result.outcome in _TERMINAL_SUCCESS_OUTCOMES
                or result.failure_reason in _TERMINAL_DECLINE_REASONS):
            return result

        # Non-terminal parse failure — record + retry
        _record_failure(conn, goal_id=goal_id,
                        pipeline_id=pipeline_id,
                        attempts_dir=attempts_dir,
                        reason=result.failure_reason,
                        detail=result.failure_detail,
                        proposal_md=result.proposal_md)
        last_reason, last_detail = result.failure_reason, result.failure_detail

    return PipelineResult(outcome="exhausted",
                          failure_reason=last_reason,
                          failure_detail=last_detail)


def _record_failure(conn: sqlite3.Connection, *,
                    goal_id: int, pipeline_id: str,
                    attempts_dir: Path,
                    reason: str, detail: str,
                    proposal_md: str) -> None:
    """Per-retry forensic + attempts counter. attempts ↔ dead_attempts
    1:1 (decision 6) so events.py projection sees every retry.
    artifacts JSON snapshots `.attempts/<pid>/` at this exact moment;
    next iteration's framework-side mutations (Builder backup restore,
    Backward proofs/ unlink) happen *after* this snapshot, so each row
    captures the agent state at failure time."""
    artifacts_json = json.dumps(collect_artifacts(attempts_dir))
    db.record_dead_attempt(
        conn,
        target_id=goal_id, target_kind="Goal",
        pipeline_id=pipeline_id,
        failure_reason=reason, failure_detail=detail,
        proposal_md=proposal_md, artifacts=artifacts_json,
    )
    db.increment_goal_attempts(conn, goal_id)
