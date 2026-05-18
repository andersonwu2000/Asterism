"""Unit tests for `Tooling/pipeline/_reflection.py` pure helpers.

The agent-spawning side of reflection is best-effort (any exception is
swallowed; the dispatcher must never block on a failed reflection)
and is exercised end-to-end by the PN run rather than mocked here.
This file pins the deterministic helpers: lesson-line counting,
prompt template substitution, before/after delta classification.
"""
from __future__ import annotations

from Tooling.pipeline._reflection import (
    _classify_delta,
    _count_lesson_lines,
    _render_prompt,
)


def test_count_lesson_lines_only_counts_bullets() -> None:
    content = (
        "## Lessons learned on this problem\n"
        "_Cross-spawn observations recorded by past agents..._\n"
        "\n"
        "- first lesson sentence\n"
        "- second lesson sentence\n"
    )
    assert _count_lesson_lines(content) == 2


def test_count_lesson_lines_handles_empty() -> None:
    assert _count_lesson_lines("") == 0
    assert _count_lesson_lines("\n\n") == 0
    # A header-only file (no bullets) is empty for cap purposes.
    assert _count_lesson_lines("## Lessons\n_blurb_\n") == 0


def test_count_lesson_lines_indented_bullet() -> None:
    # Allow some leading whitespace before the bullet (operator may
    # hand-edit with indentation).
    assert _count_lesson_lines("  - foo\n- bar\n") == 2


def test_render_prompt_substitutes_braced_fields() -> None:
    template = "Hello {name}, you are {role}."
    out = _render_prompt(template, name="alice", role="agent")
    assert out == "Hello alice, you are agent."


def test_render_prompt_does_not_format_lessons_content_with_braces() -> None:
    """LESSONS content can contain literal `{` (e.g. set-builder
    notation, Lean tactic blocks). Plain str.replace dodges
    str.format's brace-as-spec behavior."""
    template = "Existing: {lessons_content}"
    lessons = "- ‖a‖ ≤ ‖b‖ goal: try real_inner_le_norm\n- {x : ℕ // x > 0} doesn't reduce"
    out = _render_prompt(template, lessons_content=lessons)
    assert "{x : ℕ // x > 0}" in out


def test_classify_delta_skip_when_unchanged() -> None:
    same = "- existing lesson\n"
    assert _classify_delta(same, same) == "skip"


def test_classify_delta_wrote_when_appended() -> None:
    before = "- a\n"
    after = "- a\n- b\n"
    delta = _classify_delta(before, after)
    assert "wrote" in delta and "+1 line" in delta


def test_classify_delta_replaced_when_count_unchanged_but_content_differs() -> None:
    before = "- a\n- b\n- c\n"
    after = "- a\n- b\n- c-updated\n"
    delta = _classify_delta(before, after)
    assert "replaced" in delta


def test_classify_delta_unexpected_when_shrank() -> None:
    before = "- a\n- b\n"
    after = "- a\n"
    delta = _classify_delta(before, after)
    assert "unexpected" in delta


# ---------------------------------------------------------------------
# Trigger gate (T2 — exercises `_retry._maybe_reflect`)
# ---------------------------------------------------------------------

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.pipeline import PipelineResult
from Tooling.pipeline._retry import (
    SpawnCtx, run_with_session_retries,
)


def _seed_min_goal(conn: sqlite3.Connection) -> int:
    """Minimal problem + goal so run_with_session_retries can read DB."""
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    conn.commit()
    return db.insert_goal(
        conn, problem="p", slug="g", lean_path="Problems/p/Root.lean",
        statement="True", origin="root",
    )


def _make_run(*, parse_outcome: PipelineResult | None = None,
              spawn_rc: int = 0,
              extra_iters: int = 0):
    """Helper: build spawn_fn / parse_fn / postmortem_fn closures that
    return controlled outcomes."""
    spawn_calls: list[SpawnCtx] = []
    parse_calls: list[int] = []
    pm_calls: list[str] = []

    def spawn_fn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        return spawn_rc

    def parse_fn() -> PipelineResult:
        parse_calls.append(1)
        if parse_outcome is None:
            # Force a non-terminal failure so loop continues
            return PipelineResult(
                outcome="failed", failure_reason="lake_build_error",
                failure_detail="(stub)",
            )
        return parse_outcome

    def postmortem_fn(sid: str) -> None:
        pm_calls.append(sid)

    return spawn_fn, parse_fn, postmortem_fn, spawn_calls, parse_calls, pm_calls


@pytest.mark.parametrize("outcome,reason,should_fire", [
    ("proved",     "",                       True),
    ("success",    "",                       True),
    ("exhausted",  "lake_build_error",       True),
    ("failed",     "agent_declined",         True),
    ("failed",     "agent_infeasible",       True),
    ("failed",     "goal_no_longer_open",    False),
    ("failed",     "spawn_fast_fail",        False),
    ("failed",     "quota_exhausted",        False),
    ("failed",     "missing_dep",            False),
    ("moot",       "",                       False),
])
def test_reflection_trigger_gate(
    conn: sqlite3.Connection, tmp_path: Path,
    outcome: str, reason: str, should_fire: bool,
) -> None:
    """`_maybe_reflect` filters by outcome + failure_reason. The user-
    locked decision (5) is: trigger on proved / success / exhausted /
    agent_declined / agent_infeasible; skip moot, race-detected
    `goal_no_longer_open`, and infra rcs (spawn_fast_fail /
    quota_exhausted / missing_dep)."""
    gid = _seed_min_goal(conn)
    fired: list[tuple[str, PipelineResult]] = []

    def reflect(sid: str, result: PipelineResult) -> None:
        fired.append((sid, result))

    # parse_fn returns the parametrized terminal directly so the loop
    # exits on the first iteration via attach().
    spawn_fn, parse_fn, pm_fn, *_ = _make_run(
        parse_outcome=PipelineResult(outcome=outcome,
                                     failure_reason=reason),
    )

    # `attach` filters via `_maybe_reflect`. For `moot`, we need a
    # different path: budget=0 entry returns moot before any spawn.
    # We construct that case by setting goal.attempts to threshold.
    if outcome == "moot":
        for _ in range(3):
            db.increment_goal_attempts(conn, gid)

    run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-gate",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        reflection_fn=reflect,
    )

    assert bool(fired) == should_fire, (
        f"outcome={outcome} reason={reason} expected fire={should_fire}, "
        f"got {len(fired)} call(s)"
    )
