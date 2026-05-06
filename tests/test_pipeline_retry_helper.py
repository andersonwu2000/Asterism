"""Direct unit tests for `Tooling.pipeline._retry`.

Exercises the helper's public contract independently of Builder /
Backward integration. Each test stubs `spawn_fn`, `parse_fn`,
`postmortem_fn` so no claude / lake invocation happens; the helper's
DB writes are limited to `goals.attempts` (incremented by
dispatcher's flush, NOT by the helper itself in Phase 7-C.1).

Invariants exercised:
  * dynamic budget = budget_threshold - goal.attempts (decision 1)
  * in-pipeline retries share one sid; first attempt is cold
  * stale_session on warm → in-place cold re-mint, no budget consumed
  * timeout → postmortem called once on the killed sid, then exhaust
  * spawn_fast_fail / quota_exhausted / missing_dep → early bail with
    no buffered failure for that iter (prior iters still attached)
  * terminal decline reasons (agent_declined / agent_infeasible /
    goal_no_longer_open) exit without buffering
  * pending_failures is always attached to the returned PipelineResult
  * moot detection (budget≤0 entry, mid-loop goal_still_active=False)
    returns outcome='moot' with empty pending_failures (mid-loop)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import db
from Tooling.llm.base import SpawnRC
from Tooling.pipeline import PipelineResult
from Tooling.pipeline._retry import (
    SpawnCtx, goal_still_active, run_with_session_retries,
)


# ---------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection, *, attempts: int = 0,
               status: str = "open") -> int:
    """Insert a fresh goal row and bump attempts to the requested value."""
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    conn.commit()
    gid = db.insert_goal(
        conn, problem="p", slug="g", lean_path="Problems/p/Root.lean",
        statement="True", origin="root",
    )
    for _ in range(attempts):
        db.increment_goal_attempts(conn, gid)
    if status != "open":
        db.update_goal_status(conn, gid, status)
    return gid


def _seed_pipeline_row(conn: sqlite3.Connection, pipeline_id: str,
                       gid: int) -> None:
    """Pre-INSERT a pipelines row so dead_attempts FK is satisfiable.
    Mirrors what `dispatcher._run_pipeline` does before flushing the
    helper's pending_failures (the helper itself does no INSERTs)."""
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, "
        "status, outcome, started_at, finished_at) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?)",
        (pipeline_id, "Builder", str(gid), "Goal",
         "failed", "failed", db.now(), db.now()),
    )
    conn.commit()


def _make_postmortem_recorder() -> tuple[list[str], callable]:
    """Returns (call_log, callback) — callback appends sid to log."""
    log: list[str] = []
    def fn(sid: str) -> None:
        log.append(sid)
    return log, fn


def _spawn_returning(rcs: list[int]) -> tuple[list[SpawnCtx], callable]:
    """Spawn callback that returns rcs in order; records each call."""
    seen: list[SpawnCtx] = []
    iter_rcs = iter(rcs)
    def fn(ctx: SpawnCtx) -> int:
        seen.append(ctx)
        return next(iter_rcs)
    return seen, fn


def _parse_returning(results: list[PipelineResult]) -> tuple[list[int], callable]:
    """Parse callback returning results in order."""
    call_count = [0]
    iter_r = iter(results)
    def fn() -> PipelineResult:
        call_count[0] += 1
        return next(iter_r)
    return call_count, fn


# ---------------------------------------------------------------------
# goal_still_active
# ---------------------------------------------------------------------

def test_goal_still_active_open_under_threshold(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn, attempts=2)
    assert goal_still_active(conn, gid, shelve_threshold=8) is True


def test_goal_still_active_attempting_under_threshold(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn, attempts=3, status="attempting")
    assert goal_still_active(conn, gid, shelve_threshold=8) is True


def test_goal_still_active_proved(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn, status="open")
    db.update_goal_status(conn, gid, "proved")
    assert goal_still_active(conn, gid, shelve_threshold=8) is False


def test_goal_still_active_shelved(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn, status="shelved")
    assert goal_still_active(conn, gid, shelve_threshold=8) is False


def test_goal_still_active_at_threshold(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn, attempts=8)
    assert goal_still_active(conn, gid, shelve_threshold=8) is False


def test_goal_still_active_missing_row(conn: sqlite3.Connection) -> None:
    assert goal_still_active(conn, 9999, shelve_threshold=8) is False


# ---------------------------------------------------------------------
# run_with_session_retries — basic flow
# ---------------------------------------------------------------------

def test_budget_zero_at_entry_returns_moot(conn: sqlite3.Connection,
                                            tmp_path: Path) -> None:
    """attempts already == budget_threshold → no iterations, moot."""
    gid = _seed_goal(conn, attempts=3)
    seen, spawn_fn = _spawn_returning([])
    parse_count, parse_fn = _parse_returning([])
    pm_log, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-budget0",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "moot"
    assert r.pending_failures == []
    assert seen == []  # no spawn
    assert parse_count[0] == 0


def test_first_iter_proved_returns_proved_with_empty_pending(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([0])
    _, parse_fn = _parse_returning([PipelineResult(outcome="proved")])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-proved",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "proved"
    assert r.pending_failures == []
    assert len(seen) == 1
    assert seen[0].cold is True
    assert seen[0].retry_context is None


def test_first_iter_fails_second_iter_proved(conn: sqlite3.Connection,
                                              tmp_path: Path) -> None:
    """iter 0 lake_build_error (buffered), iter 1 proved (terminal).
    Final pending_failures has the 1 prior failure; iter 0 was cold,
    iter 1 was warm with retry_context = iter 0's detail."""
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([0, 0])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed", failure_reason="lake_build_error",
                       failure_detail="error: foo"),
        PipelineResult(outcome="proved"),
    ])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-mix",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "proved"
    assert len(r.pending_failures) == 1
    assert r.pending_failures[0]["reason"] == "lake_build_error"
    assert seen[0].cold is True and seen[0].retry_context is None
    assert seen[1].cold is False
    assert seen[1].retry_context == "error: foo"
    # Same sid across iterations.
    assert seen[0].sid == seen[1].sid


def test_all_iters_fail_returns_exhausted(conn: sqlite3.Connection,
                                           tmp_path: Path) -> None:
    """3 retries, all fail with lake_build_error → exhausted with last
    failure as failure_reason and 3 pending_failures buffered."""
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([0, 0, 0])
    fail = lambda detail: PipelineResult(
        outcome="failed", failure_reason="lake_build_error",
        failure_detail=detail)
    _, parse_fn = _parse_returning([fail("e1"), fail("e2"), fail("e3")])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-exh",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "exhausted"
    assert r.failure_reason == "lake_build_error"
    assert r.failure_detail == "e3"
    assert len(r.pending_failures) == 3
    assert [pf["detail"] for pf in r.pending_failures] == ["e1", "e2", "e3"]


# ---------------------------------------------------------------------
# Terminal decline reasons exit without buffering current iter
# ---------------------------------------------------------------------

@pytest.mark.parametrize("reason", [
    "agent_declined", "agent_infeasible", "goal_no_longer_open",
])
def test_terminal_decline_reasons_exit_without_buffering(
    conn: sqlite3.Connection, tmp_path: Path, reason: str,
) -> None:
    """Terminal decline at iter 1: prior iter 0 buffered, iter 1
    returns terminal without being buffered (1:1 governs only at
    cascade level for declines)."""
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([0, 0])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed", failure_reason="lake_build_error",
                       failure_detail="prior"),
        PipelineResult(outcome="failed", failure_reason=reason,
                       failure_detail=f"agent says {reason}"),
    ])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-decline",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == reason
    # Only the prior iter is buffered; the terminal iter itself is not.
    assert len(r.pending_failures) == 1
    assert r.pending_failures[0]["reason"] == "lake_build_error"


# ---------------------------------------------------------------------
# rc-classified outcomes
# ---------------------------------------------------------------------

def test_timeout_calls_postmortem_then_returns_exhausted(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """rc=124 on iter 0: postmortem called once with the killed sid,
    timeout buffered, return outcome='exhausted'."""
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([SpawnRC.TIMEOUT])
    _, parse_fn = _parse_returning([])  # never called
    pm_log, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-timeout",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "exhausted"
    assert r.failure_reason == "agent_timeout"
    assert len(pm_log) == 1
    assert pm_log[0] == seen[0].sid  # postmortem on the killed session
    assert len(r.pending_failures) == 1
    assert r.pending_failures[0]["reason"] == "agent_timeout"


def test_stale_session_on_warm_remints_in_place_no_budget_consumed(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """iter 0 cold lake_build_error (buffered). iter 1 warm STALE_SESSION
    → in-place cold re-mint, parse runs once. Budget is 3, this consumed
    only 2 (iter 0 + iter 1), iter 1's stale fallback didn't consume an
    extra slot. Verify the spawn_fn was called 3 times total: cold,
    warm-stale, in-place-cold."""
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([0, SpawnRC.STALE_SESSION, 0])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed", failure_reason="lake_build_error",
                       failure_detail="iter0"),
        PipelineResult(outcome="proved"),
    ])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-stale",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "proved"
    # Three spawn calls: cold(iter0), warm(iter1 stale), cold-remint(iter1)
    assert len(seen) == 3
    assert seen[0].cold is True   # iter 0 cold
    assert seen[1].cold is False  # iter 1 warm (stale fallback trigger)
    assert seen[2].cold is True   # in-place re-mint
    # Re-mint changed the sid for the third call.
    assert seen[2].sid != seen[1].sid
    # Only iter 0's failure is buffered; the stale-then-success iter
    # doesn't add another row.
    assert len(r.pending_failures) == 1


@pytest.mark.parametrize("rc, reason", [
    (SpawnRC.QUOTA_EXHAUSTED, "quota_exhausted"),
    (SpawnRC.MISSING_DEP, "missing_dep"),
])
def test_provider_infra_rc_returns_failed_without_consuming_budget(
    conn: sqlite3.Connection, tmp_path: Path, rc: int, reason: str,
) -> None:
    """rc=126 / 127 → return outcome='failed' with that reason. Prior-
    iteration pending_failures still attach; this iteration's failure
    is NOT buffered (no agent budget burn)."""
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([0, rc])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed", failure_reason="lake_build_error",
                       failure_detail="prior"),
    ])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-infra",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == reason
    # Prior iter's failure attached, current iter's infra rc dropped.
    assert len(r.pending_failures) == 1
    assert r.pending_failures[0]["reason"] == "lake_build_error"


# ---------------------------------------------------------------------
# Mid-loop moot detection
# ---------------------------------------------------------------------

def test_mid_loop_goal_proved_externally_returns_moot(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """iter 0 fails (buffered). Before iter 1's spawn, the goal status
    flips to 'proved' (sibling won the OR race). cascade re-check
    triggers, helper returns 'moot' with the prior pending_failures
    still attached. Dispatcher's flush will skip them on moot
    (decision 2)."""
    gid = _seed_goal(conn, attempts=0)
    seen: list[SpawnCtx] = []
    parse_calls = [0]

    def spawn_fn(ctx: SpawnCtx) -> int:
        seen.append(ctx)
        return 0

    def parse_fn() -> PipelineResult:
        parse_calls[0] += 1
        if parse_calls[0] == 1:
            # Simulate sibling proving the goal between iter 0 and iter 1.
            db.update_goal_status(conn, gid, "proved")
            return PipelineResult(outcome="failed",
                                  failure_reason="lake_build_error",
                                  failure_detail="iter 0 fails")
        # Should not be reached
        raise AssertionError("iter 1 should be skipped via moot")

    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-midmoot",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "moot"
    # Helper still attaches prior buffered failures (decision 2's flush
    # skip is enforced by dispatcher, not the helper).
    assert len(r.pending_failures) == 1
    assert r.pending_failures[0]["reason"] == "lake_build_error"
    # Only iter 0's spawn ran.
    assert len(seen) == 1


# ---------------------------------------------------------------------
# Goal not found
# ---------------------------------------------------------------------

def test_goal_not_found_returns_failed(conn: sqlite3.Connection,
                                        tmp_path: Path) -> None:
    seen, spawn_fn = _spawn_returning([])
    _, parse_fn = _parse_returning([])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=9999, pipeline_id="pid-notfound",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "goal_not_found"
    assert seen == []


# ---------------------------------------------------------------------
# 1:1 attempts ↔ dead_attempts invariant when dispatcher flushes
# ---------------------------------------------------------------------

def test_dispatcher_flush_preserves_1to1_invariant(conn: sqlite3.Connection,
                                                    tmp_path: Path) -> None:
    """Mimic dispatcher's flush of pending_failures: insert pipelines
    row, then for each pending failure insert a dead_attempt + ++
    attempts. Verify final goal.attempts equals dead_attempts row
    count for this goal — decision 5/6's 1:1 invariant.
    """
    import json as _json
    gid = _seed_goal(conn, attempts=0)
    pid = "pid-1to1"
    _seed_pipeline_row(conn, pid, gid)

    # Helper run produces 3 buffered failures.
    seen, spawn_fn = _spawn_returning([0, 0, 0])
    fail = lambda d: PipelineResult(outcome="failed",
                                    failure_reason="lake_build_error",
                                    failure_detail=d)
    _, parse_fn = _parse_returning([fail("e1"), fail("e2"), fail("e3")])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id=pid,
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "exhausted"

    # Dispatcher flush emulation
    for pf in r.pending_failures:
        db.record_dead_attempt(
            conn, target_id=gid, target_kind="Goal",
            pipeline_id=pid, failure_reason=pf["reason"],
            failure_detail=pf["detail"],
            artifacts=_json.dumps(pf["artifacts"]) if pf["artifacts"] else "",
        )
        db.increment_goal_attempts(conn, gid)

    # 1:1 invariant
    final_attempts = db.get_goal(conn, gid)["attempts"]
    da_count = conn.execute(
        "SELECT COUNT(*) AS n FROM dead_attempts WHERE target_id=?",
        (gid,),
    ).fetchone()["n"]
    assert final_attempts == da_count == 3
