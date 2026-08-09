"""Direct unit tests for `Tooling.pipeline._retry`.

Exercises the helper's public contract independently of Builder /
Backward integration. Each test stubs `spawn_fn`, `parse_fn`,
`postmortem_fn` so no claude / lake invocation happens; the helper's
DB writes are the EAGER per-retry failure records (v38): one
dead_attempts row + one goals.attempts++ per failed retry, written
in-loop against the dispatch-time pipelines row (`_seed_pipeline_row`
plays the dispatcher's `record_pipeline_start`).

Invariants exercised:
  * dynamic budget = budget_threshold - goal.attempts (decision 1)
  * in-pipeline retries share one sid; first attempt is cold
  * stale_session on warm → in-place cold re-mint, no budget consumed
  * timeout → postmortem called once on the killed sid, then exhaust
  * spawn_fast_fail / quota_exhausted / missing_dep → early bail with
    no failure record for that iter (prior iters' rows persist)
  * terminal decline reasons (agent_declined / agent_infeasible /
    goal_no_longer_open) exit without recording the terminal iter
  * every failed retry leaves attempts == dead_attempts (eager 1:1),
    including when the loop later dies by an unhandled exception —
    the goal-7486 (2026-08-08) drift class
  * moot detection (budget≤0 entry, mid-loop goal_still_active=False)
    returns outcome='moot'; the moot iteration itself records nothing
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
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
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
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
    """Play the dispatcher's dispatch-time INSERT (v38
    `db.record_pipeline_start`): the row exists status='running' for the
    whole pipeline lifetime, which is what lets the helper write its
    dead_attempts rows eagerly (FK target present mid-loop)."""
    db.record_pipeline_start(conn, pipeline_id=pipeline_id,
                             kind="Formalizer", target_id=str(gid),
                             target_kind="Goal")


def _dead_rows(conn: sqlite3.Connection, pipeline_id: str) -> list:
    """The helper's eagerly-written forensic rows for one pipeline."""
    return list(conn.execute(
        "SELECT * FROM dead_attempts WHERE pipeline_id = ? ORDER BY id",
        (pipeline_id,)))


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
    assert _dead_rows(conn, "pid-budget0") == []
    assert seen == []  # no spawn
    assert parse_count[0] == 0


def test_inject_dispatch_gets_fresh_budget(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Strategist Inject (decision_id set) bypasses the pre-loop budget
    gate. Without this, Inject(Builder) on a goal at/above
    BUILDER_THRESHOLD silently no-ops — Strategist's explicit re-dispatch
    is ignored (LU lu_step_assembly 2026-05-28)."""
    gid = _seed_goal(conn, attempts=3)
    seen, spawn_fn = _spawn_returning([0])
    _, parse_fn = _parse_returning([PipelineResult(outcome="proved")])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-inject",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        decision_id=42,
    )
    # Without the fresh-budget path, this would moot (budget=3-3=0).
    assert r.outcome == "proved"
    assert len(seen) == 1


def test_inject_dispatch_bypasses_attempts_shelve_cap(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Strategist Inject also bypasses the per-iteration attempts >=
    shelve_threshold cap in goal_still_active. attempts becomes a
    forensic counter; Strategist's ConfirmShelve discipline is the only
    convergence signal."""
    gid = _seed_goal(conn, attempts=10)  # way above shelve_threshold
    seen, spawn_fn = _spawn_returning([0])
    _, parse_fn = _parse_returning([PipelineResult(outcome="proved")])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-inject-shelve",
        budget_threshold=3, shelve_threshold=5,  # 10 >> 5
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        decision_id=43,
    )
    # Without bypass, goal_still_active(attempts=10, shelve_threshold=5)
    # would return False → moot. With bypass, Inject runs.
    assert r.outcome == "proved"


def test_inject_dispatch_still_moots_on_terminal_status(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Inject bypasses attempts cap but NOT the status check. If a
    parallel cascade flipped the goal to a terminal status mid-Inject,
    the loop still moots — prevents Inject from infinite-looping on a
    goal that's already proved/disproved/dead elsewhere."""
    gid = _seed_goal(conn, attempts=2, status="shelved")
    seen, spawn_fn = _spawn_returning([])
    _, parse_fn = _parse_returning([])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-inject-terminal",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        decision_id=44,
    )
    # status='shelved' → goal_still_active returns False even with
    # decision_id (status check is unconditional).
    assert r.outcome == "moot"
    assert seen == []


def test_first_iter_proved_records_no_failure(
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
    assert _dead_rows(conn, "pid-proved") == []
    assert len(seen) == 1
    assert seen[0].cold is True
    assert seen[0].retry_context is None


def test_first_iter_fails_second_iter_proved(conn: sqlite3.Connection,
                                              tmp_path: Path) -> None:
    """iter 0 lake_build_error (recorded eagerly), iter 1 proved
    (terminal). One dead_attempts row for the prior failure; iter 0 was
    cold, iter 1 was warm with retry_context = iter 0's detail."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-mix", gid)
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
    rows = _dead_rows(conn, "pid-mix")
    assert len(rows) == 1
    assert rows[0]["failure_reason"] == "lake_build_error"
    assert seen[0].cold is True and seen[0].retry_context is None
    assert seen[1].cold is False
    assert seen[1].retry_context == "error: foo"
    # Same sid across iterations.
    assert seen[0].sid == seen[1].sid


def test_all_iters_fail_returns_exhausted(conn: sqlite3.Connection,
                                           tmp_path: Path) -> None:
    """3 retries, all fail with lake_build_error → exhausted with last
    failure as failure_reason and 3 dead_attempts rows written eagerly."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-exh", gid)
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
    rows = _dead_rows(conn, "pid-exh")
    assert [row["failure_detail"] for row in rows] == ["e1", "e2", "e3"]
    # Eager 1:1 — attempts marched with the rows.
    assert db.get_goal(conn, gid)["attempts"] == 3


# ---------------------------------------------------------------------
# Terminal decline reasons exit without buffering current iter
# ---------------------------------------------------------------------

@pytest.mark.parametrize("reason", [
    "agent_declined", "agent_infeasible", "goal_no_longer_open",
    "parent_needs_fix", "agent_shelved", "agent_bailed",
])
def test_terminal_decline_reasons_exit_without_buffering(
    conn: sqlite3.Connection, tmp_path: Path, reason: str,
) -> None:
    """Terminal decline at iter 1: prior iter 0 recorded, iter 1
    returns terminal without being recorded (1:1 governs only at
    cascade level for declines)."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-decline", gid)
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
    # Only the prior iter is recorded; the terminal iter itself is not.
    rows = _dead_rows(conn, "pid-decline")
    assert len(rows) == 1
    assert rows[0]["failure_reason"] == "lake_build_error"


# ---------------------------------------------------------------------
# rc-classified outcomes
# ---------------------------------------------------------------------

def test_timeout_no_salvage_calls_postmortem_then_returns_exhausted(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """rc=124 on iter 0: helper attempts a salvage parse first; when
    parse returns a non-terminal failure (incomplete output on disk),
    falls through to postmortem + forced exhaust. This preserves the
    pre-`b6ece82` behavior for genuinely timed-out spawns with no
    usable output."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-timeout", gid)
    seen, spawn_fn = _spawn_returning([SpawnRC.TIMEOUT])
    # Parse returns a non-terminal failure → salvage skipped, postmortem
    # path engages.
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed",
                       failure_reason="parse_proposal_fail",
                       failure_detail="no usable patch on disk"),
    ])
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
    rows = _dead_rows(conn, "pid-timeout")
    assert len(rows) == 1
    assert rows[0]["failure_reason"] == "agent_timeout"


def test_timeout_salvages_when_parse_returns_success(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """rc=124 but the agent left valid output on disk before the
    subprocess was killed (typical Sonnet pattern under the idle-window
    guard: writes complete by ~+880s, kept doing tool_use, killed at
    +900s). Helper's salvage parse returns 'proved'/'success'; helper
    honors it without postmortem + without buffering a timeout failure."""
    gid = _seed_goal(conn, attempts=0)
    _, spawn_fn = _spawn_returning([SpawnRC.TIMEOUT])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="proved"),
    ])
    pm_log, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-timeout-salvage",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "proved"
    # Postmortem must NOT run when salvage succeeds.
    assert pm_log == []
    # No failure record for the timeout itself — salvage replaces it.
    assert _dead_rows(conn, "pid-timeout-salvage") == []


def test_timeout_no_salvage_folds_parse_reason_into_detail(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When TIMEOUT salvage parse returns a non-terminal failure (e.g.
    lake_build_error from a partially-written patch), we still fall
    through to postmortem + forced exhaust with reason=agent_timeout
    (preserving the operator-level "this was a timeout" signal). But
    the parse outcome is folded into failure_detail so forensics can
    distinguish "agent wrote nothing" vs "agent wrote a broken patch"."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-timeout-fold", gid)
    _, spawn_fn = _spawn_returning([SpawnRC.TIMEOUT])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed",
                       failure_reason="lake_build_error",
                       failure_detail="unknown identifier `foo`"),
    ])
    pm_log, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-timeout-fold",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    # Reason stays agent_timeout — TIMEOUT classification preserved.
    assert r.outcome == "exhausted"
    assert r.failure_reason == "agent_timeout"
    # Parse outcome folded into detail for forensic transparency.
    assert "lake_build_error" in (r.failure_detail or "")
    assert "unknown identifier" in (r.failure_detail or "")
    # Postmortem still ran (no salvage success).
    assert len(pm_log) == 1


def test_timeout_detail_is_main_spawn_stderr_not_postmortem(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Regression — `_spawn_failure` must read attempts_dir/_spawn.stderr
    BEFORE postmortem_fn runs. Otherwise postmortem's own spawn writes
    its own stderr (e.g. its 180s budget timeout) over the main spawn's
    900s stderr, and operators reading dead_attempts.failure_detail get
    the wrong wall budget — looks like "180s" when the main spawn
    actually ran the full 900s. Observed in SG run #6 g266 retry
    pipeline 0187e8d1 (dead_attempt 128)."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-stderr-overwrite", gid)
    _, spawn_fn = _spawn_returning([SpawnRC.TIMEOUT])
    # Salvage parse returns non-terminal failure → falls through to
    # postmortem path (the one with the bug).
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed",
                       failure_reason="parse_proposal_fail",
                       failure_detail="no patch on disk"),
    ])
    # Pre-seed the _spawn.stderr file as the MAIN spawn would: claude
    # CLI writes this on rc=124 with the actual req.timeout_sec value.
    (tmp_path / "_spawn.stderr").write_text(
        "rc=124\n(subprocess.TimeoutExpired after 900s)",
        encoding="utf-8")

    # Postmortem callback simulates its own spawn timing out and
    # OVERWRITING _spawn.stderr (this is what the real provider does).
    def postmortem_overwrites(sid: str) -> None:
        (tmp_path / "_spawn.stderr").write_text(
            "rc=124\n(subprocess.TimeoutExpired after 180s)",
            encoding="utf-8")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-stderr-overwrite",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn,
        postmortem_fn=postmortem_overwrites,
    )
    assert r.outcome == "exhausted"
    assert r.failure_reason == "agent_timeout"
    # Critical: detail captures the MAIN spawn's 900s, not the
    # postmortem's 180s.
    assert "900s" in (r.failure_detail or ""), (
        f"failure_detail should mention main spawn's 900s timeout; "
        f"got: {r.failure_detail}")
    assert "180s" not in (r.failure_detail or ""), (
        f"failure_detail leaked postmortem's 180s; got: "
        f"{r.failure_detail}")


def test_timeout_no_salvage_records_parse_exception_in_detail(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When salvage parse itself raises (DB / FS error mid-commit),
    the exception type+message lands in failure_detail so forensics
    can see it. Reason stays agent_timeout, postmortem still runs."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-timeout-raise", gid)
    _, spawn_fn = _spawn_returning([SpawnRC.TIMEOUT])

    def raising_parse() -> PipelineResult:
        raise OSError("disk read failed mid-parse")
    pm_log, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-timeout-raise",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=raising_parse, postmortem_fn=pm_fn,
    )
    assert r.outcome == "exhausted"
    assert r.failure_reason == "agent_timeout"
    assert "OSError" in (r.failure_detail or "")
    assert "disk read failed" in (r.failure_detail or "")
    assert len(pm_log) == 1


def test_timeout_salvage_honors_terminal_decline_directive(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """If the agent already shipped a `decline:` directive in patch.lean
    before subprocess timeout, salvage parse returns the decline reason
    (in `_TERMINAL_DECLINE_REASONS`); helper exits without postmortem."""
    gid = _seed_goal(conn, attempts=0)
    _, spawn_fn = _spawn_returning([SpawnRC.TIMEOUT])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed",
                       failure_reason="agent_infeasible",
                       failure_detail="counterexample on patch.lean"),
    ])
    pm_log, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-timeout-decline",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "agent_infeasible"
    assert pm_log == []


def test_stale_session_on_warm_remints_in_place_no_budget_consumed(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """iter 0 cold lake_build_error (buffered). iter 1 warm STALE_SESSION
    → in-place cold re-mint, parse runs once. Budget is 3, this consumed
    only 2 (iter 0 + iter 1), iter 1's stale fallback didn't consume an
    extra slot. Verify the spawn_fn was called 3 times total: cold,
    warm-stale, in-place-cold."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-stale", gid)
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
    # Only iter 0's failure is recorded; the stale-then-success iter
    # doesn't add another row.
    assert len(_dead_rows(conn, "pid-stale")) == 1


@pytest.mark.parametrize("rc, reason", [
    (SpawnRC.QUOTA_EXHAUSTED, "quota_exhausted"),
    (SpawnRC.MISSING_DEP, "missing_dep"),
])
def test_provider_infra_rc_returns_failed_without_consuming_budget(
    conn: sqlite3.Connection, tmp_path: Path, rc: int, reason: str,
) -> None:
    """rc=126 / 127 → return outcome='failed' with that reason. Prior-
    iteration failures are already in DB (eager); this iteration's
    infra death is NOT recorded (no agent budget burn)."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-infra", gid)
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
    # Prior iter's failure recorded, current iter's infra rc dropped.
    rows = _dead_rows(conn, "pid-infra")
    assert len(rows) == 1
    assert rows[0]["failure_reason"] == "lake_build_error"


# ---------------------------------------------------------------------
# Mid-loop moot detection
# ---------------------------------------------------------------------

def test_mid_loop_goal_proved_externally_returns_moot(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """iter 0 fails (recorded eagerly). Before iter 1's spawn, the goal
    status flips to 'proved' (sibling won the OR race). cascade
    re-check triggers, helper returns 'moot'. The prior iteration's
    forensic row PERSISTS (v38 — it was a real LLM call and its
    attempts++ was always kept); decision 2's "moot writes nothing"
    applies to the moot detection itself."""
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-midmoot", gid)
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
    # Prior iteration's eager record persists; the moot itself added
    # nothing — attempts and rows stay 1:1.
    rows = _dead_rows(conn, "pid-midmoot")
    assert len(rows) == 1
    assert rows[0]["failure_reason"] == "lake_build_error"
    assert db.get_goal(conn, gid)["attempts"] == 1
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
# 1:1 attempts ↔ dead_attempts invariant (eager, v38)
# ---------------------------------------------------------------------

def test_eager_recording_preserves_1to1_invariant(conn: sqlite3.Connection,
                                                  tmp_path: Path) -> None:
    """v38 — the helper writes each failed retry's dead_attempts row
    IN-LOOP, immediately paired with the attempts++ (no dispatcher
    flush step exists any more). Verify final goal.attempts equals the
    dead_attempts row count with no post-processing at all.
    """
    gid = _seed_goal(conn, attempts=0)
    pid = "pid-1to1"
    _seed_pipeline_row(conn, pid, gid)

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
    final_attempts = db.get_goal(conn, gid)["attempts"]
    da_count = conn.execute(
        "SELECT COUNT(*) AS n FROM dead_attempts WHERE target_id=?",
        (gid,),
    ).fetchone()["n"]
    assert final_attempts == da_count == 3


def test_unhandled_exception_mid_retry_keeps_attempts_and_rows_1to1(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """THE goal-7486 scenario (2026-08-08): iter 0 fails (attempts++ +
    row), then iter 1's spawn raises an unhandled exception — the
    worker thread dies, `PipelineResult` never returns. Pre-v38 the
    buffered forensic rows died with the stack frame while the eager
    increments stayed banked (goal 7486: attempts=10 vs 7 rows, three
    pipelines with no trace at all). With eager recording the DB is
    already consistent at the moment of death, and startup recovery
    finalizes the orphaned 'running' pipelines row."""
    gid = _seed_goal(conn, attempts=0)
    pid = "pid-worker-dies"
    _seed_pipeline_row(conn, pid, gid)

    calls = [0]

    def spawn_fn(ctx: SpawnCtx) -> int:
        calls[0] += 1
        if calls[0] == 2:
            # e.g. a gateway HTTP 500 escaping the loop
            raise OSError("gateway HTTP 500")
        return 0

    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed", failure_reason="lake_build_error",
                       failure_detail="iter0 err"),
    ])
    _, pm_fn = _make_postmortem_recorder()

    with pytest.raises(OSError):
        run_with_session_retries(
            conn=conn, goal_id=gid, pipeline_id=pid,
            budget_threshold=3, shelve_threshold=8,
            attempts_dir=tmp_path,
            spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        )

    # The invariant holds at the moment of death: every banked
    # increment has its forensic row.
    attempts = db.get_goal(conn, gid)["attempts"]
    rows = _dead_rows(conn, pid)
    assert attempts == len(rows) == 1
    assert rows[0]["failure_reason"] == "lake_build_error"

    # The dispatch-time pipelines row is still 'running' (worker died
    # before finalize) — exactly what startup recovery resolves.
    st = conn.execute("SELECT status, outcome FROM pipelines WHERE id=?",
                      (pid,)).fetchone()
    assert st["status"] == "running" and st["outcome"] is None

    from Tooling.state import recovery
    recovery.recover_at_startup(conn, workspace=None)
    st = conn.execute(
        "SELECT status, outcome, finished_at FROM pipelines WHERE id=?",
        (pid,)).fetchone()
    assert st["status"] == "failed"
    assert st["outcome"] == "daemon_crashed"
    assert st["finished_at"] is not None
    # Recovery adds no forensic rows and no increments — 1:1 untouched.
    assert db.get_goal(conn, gid)["attempts"] == len(_dead_rows(conn, pid))


# ---------------------------------------------------------------------
# Dispatcher abort short-circuit (2026-05-27 budget-shutdown bug)
# ---------------------------------------------------------------------

@pytest.fixture
def _shutdown_state():
    """Clear claude_cli's module-level shutdown event before AND after
    each test so order doesn't leak shutdown state."""
    from Tooling.llm import claude_cli
    claude_cli._reset_shutdown_for_tests()
    yield
    claude_cli._reset_shutdown_for_tests()


def test_retry_loop_bails_when_shutdown_requested_at_entry(
    conn: sqlite3.Connection, tmp_path: Path, _shutdown_state,
) -> None:
    """`request_shutdown()` called before retry loop runs → first
    iteration sees the flag, returns daemon_shutdown without spawning.
    Regression: 2026-05-27 Banach-Tarski budget-exit hung ~30min while
    workers each waited subprocess_timeout=960s on their claude proc."""
    from Tooling.llm import claude_cli
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([])  # would raise StopIteration if called
    _, parse_fn = _parse_returning([])
    _, pm_fn = _make_postmortem_recorder()

    claude_cli.request_shutdown()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-sd-entry",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "daemon_shutdown"
    assert seen == []  # spawn never invoked
    assert _dead_rows(conn, "pid-sd-entry") == []  # teardown ≠ failure


def test_retry_loop_bails_when_shutdown_requested_mid_loop(
    conn: sqlite3.Connection, tmp_path: Path, _shutdown_state,
) -> None:
    """Iter 0 runs normally and fails; before iter 1, dispatcher calls
    request_shutdown(); retry loop's iter-1 entry sees the flag and
    bails. Iter 0's dead_attempt is preserved (real failure happened);
    iter 1's spawn is never invoked."""
    from Tooling.llm import claude_cli
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-sd-mid", gid)
    # spawn_fn for iter 0 returns 0 (success rc); iter 1 spawn must NOT
    # be invoked, so the rcs list has only one entry.
    def spawn_iter(_ctx: SpawnCtx) -> int:
        # On first call, set shutdown before parse_fn runs. Effect: parse
        # returns failure, retry loop continues, next iter sees event.
        claude_cli.request_shutdown()
        return 0
    parse_count, parse_fn = _parse_returning([
        PipelineResult(outcome="failed", failure_reason="lake_build_error",
                       failure_detail="iter0 err"),
    ])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-sd-mid",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_iter, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "daemon_shutdown"
    # iter 0's failure is preserved (recorded eagerly)
    rows = _dead_rows(conn, "pid-sd-mid")
    assert len(rows) == 1
    assert rows[0]["failure_reason"] == "lake_build_error"
    assert parse_count[0] == 1  # parse ran once, iter-1 never reached spawn


def test_retry_loop_handles_SpawnRC_SHUTDOWN(
    conn: sqlite3.Connection, tmp_path: Path, _shutdown_state,
) -> None:
    """spawn_fn returns SpawnRC.SHUTDOWN (the rc spawn_llm short-
    circuits with when shutdown is already requested). Retry loop
    treats as terminal-no-retry, no dead_attempt recorded."""
    gid = _seed_goal(conn, attempts=0)
    seen, spawn_fn = _spawn_returning([int(SpawnRC.SHUTDOWN)])
    parse_count, parse_fn = _parse_returning([])
    _, pm_fn = _make_postmortem_recorder()

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-sd-rc",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "daemon_shutdown"
    assert len(seen) == 1  # one spawn happened, returned SHUTDOWN
    assert parse_count[0] == 0  # parse never invoked
    assert _dead_rows(conn, "pid-sd-rc") == []


# ---------------------------------------------------------------------
# initial_sid / continuation shape (Formalizer staged pipeline)
# ---------------------------------------------------------------------

def test_initial_sid_first_spawn_is_continuation(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """With initial_sid, the first spawn resumes the intake session as a
    continuation (cold=False, continuation=True) — never a cold seed."""
    gid = _seed_goal(conn)
    seen, spawn_fn = _spawn_returning([0])
    _, parse_fn = _parse_returning([PipelineResult(outcome="proved")])
    _, pm_fn = _make_postmortem_recorder()
    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-cont",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        initial_sid="intake-sid",
    )
    assert r.outcome == "proved"
    assert (seen[0].sid, seen[0].cold, seen[0].continuation) == (
        "intake-sid", False, True)


def test_initial_sid_stale_session_remints_cold(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """STALE_SESSION on the continuation spawn re-mints a fresh sid and
    goes COLD (cold_prep runs; continuation off)."""
    from Tooling.llm.base import SpawnRC
    gid = _seed_goal(conn)
    seen, spawn_fn = _spawn_returning([SpawnRC.STALE_SESSION, 0])
    _, parse_fn = _parse_returning([PipelineResult(outcome="proved")])
    _, pm_fn = _make_postmortem_recorder()
    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-cont-stale",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        initial_sid="intake-sid",
    )
    assert r.outcome == "proved"
    assert (seen[0].cold, seen[0].continuation) == (False, True)
    assert (seen[1].cold, seen[1].continuation) == (True, False)
    assert seen[1].sid != "intake-sid"


def test_initial_sid_warm_retry_is_plain_retry(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """After the continuation first attempt fails a parse, the next
    iteration is a plain warm retry on the SAME sid (is_retry framing:
    cold=False, continuation=False)."""
    gid = _seed_goal(conn)
    _seed_pipeline_row(conn, "pid-cont-retry", gid)
    seen, spawn_fn = _spawn_returning([0, 0])
    _, parse_fn = _parse_returning([
        PipelineResult(outcome="failed", failure_reason="lake_build_error",
                       failure_detail="boom"),
        PipelineResult(outcome="proved"),
    ])
    _, pm_fn = _make_postmortem_recorder()
    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-cont-retry",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        initial_sid="intake-sid",
    )
    assert r.outcome == "proved"
    assert (seen[1].sid, seen[1].cold, seen[1].continuation) == (
        "intake-sid", False, False)
