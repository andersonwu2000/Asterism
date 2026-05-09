"""Watchdog + rescue spawn — replaces MAX_THINKING_TOKENS strategy.

Verifies retry-helper routing of rc=128 (SpawnRC.STUCK_THINKING) to
a single rescue spawn with the rescue_prompt set on SpawnCtx; rescue
success ships, rescue failure buffers + continues normal retry.

The end-to-end behavior (real watchdog thread killing real claude.exe
on real session jsonl) lives in integration runs, not here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import db
from Tooling.llm.base import SpawnRC
from Tooling.pipeline._retry import (
    SpawnCtx, run_with_session_retries,
)
from Tooling.pipeline import PipelineResult


def _seed_open_goal(conn: sqlite3.Connection, *, attempts: int = 0) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    conn.commit()
    gid = db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/proofs/L_main.lean",
        statement="True", origin="root", depth=0,
    )
    if attempts:
        for _ in range(attempts):
            db.increment_goal_attempts(conn, gid)
    return gid


# ---------------------------------------------------------------------
# retry helper rescue routing
# ---------------------------------------------------------------------

def test_stuck_thinking_triggers_two_phase_rescue_then_ships(
    conn: sqlite3.Connection,
) -> None:
    """Two-phase rescue (2026-05-10): rc=128 → STOP spawn (~30s) →
    actual rescue spawn (~180s). Helper invokes spawn_fn THREE times
    total: main(stuck), STOP(short-budget), rescue(actual prompt).
    Verifies STOP_PROMPT is sent first with rescue_budget_override
    set, then the caller-supplied rescue_prompt with no override
    (default budget)."""
    from Tooling.pipeline._retry import STOP_PROMPT
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0 main: stuck. STOP spawn: ack ok. Rescue spawn: ship.
        if ctx.rescue_prompt is not None:
            return SpawnRC.OK
        return SpawnRC.STUCK_THINKING

    def parse() -> PipelineResult:
        return PipelineResult(outcome="proved")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-rescue",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=Path("/tmp/x"),
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
        rescue_prompt="ship now no analysis",
    )
    assert r.outcome == "proved"
    assert len(spawn_calls) == 3, f"expected 3 spawns, got {len(spawn_calls)}"
    # Spawn 0: cold main (no rescue prompt)
    assert spawn_calls[0].rescue_prompt is None
    # Spawn 1: STOP injection — short budget override, STOP_PROMPT
    assert spawn_calls[1].rescue_prompt == STOP_PROMPT
    assert spawn_calls[1].rescue_budget_override is not None
    assert spawn_calls[1].rescue_budget_override <= 60  # short
    # Spawn 2: actual rescue — caller's prompt, no budget override
    assert spawn_calls[2].rescue_prompt == "ship now no analysis"
    assert spawn_calls[2].rescue_budget_override is None


def test_stop_failure_does_not_block_rescue(
    conn: sqlite3.Connection,
) -> None:
    """If the STOP spawn itself fails (rc != 0), the helper STILL
    proceeds to the actual rescue spawn — STOP rc is informational
    only, the goal is to clear the thinking pattern, not produce
    useful output. The actual rescue spawn is what matters."""
    from Tooling.pipeline._retry import STOP_PROMPT
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0: stuck. STOP: also fails (rc=1). Rescue: ships.
        if ctx.rescue_prompt == STOP_PROMPT:
            return 1  # STOP failed
        if ctx.rescue_prompt is not None:
            return SpawnRC.OK  # actual rescue ships
        return SpawnRC.STUCK_THINKING

    def parse() -> PipelineResult:
        return PipelineResult(outcome="proved")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-stop-fail",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=Path("/tmp/x"),
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
        rescue_prompt="ship now no analysis",
    )
    assert r.outcome == "proved"
    # 3 spawns even though STOP failed.
    assert len(spawn_calls) == 3
    assert spawn_calls[1].rescue_prompt == STOP_PROMPT
    assert spawn_calls[2].rescue_prompt == "ship now no analysis"


def test_stuck_thinking_rescue_failure_falls_through_to_retry(
    conn: sqlite3.Connection,
) -> None:
    """If the actual rescue spawn fails (rc != 0), helper records
    `agent_stuck_thinking` as a buffered failure and continues the
    normal retry loop. STOP-then-rescue counts as two extra spawns;
    the next iteration is a regular warm retry."""
    from Tooling.pipeline._retry import STOP_PROMPT
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0 main: stuck. STOP: ack ok. Rescue: fails.
        # Iter 1 warm: proved.
        if ctx.rescue_prompt == STOP_PROMPT:
            return SpawnRC.OK
        if ctx.rescue_prompt is not None:
            return 1  # rescue failure
        if len([c for c in spawn_calls if c.rescue_prompt is None]) == 1:
            return SpawnRC.STUCK_THINKING
        return SpawnRC.OK

    def parse() -> PipelineResult:
        return PipelineResult(outcome="proved")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-rescue-fail",
        budget_threshold=5, shelve_threshold=8,
        attempts_dir=Path("/tmp/x"),
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
    )
    assert r.outcome == "proved"
    # 4 invocations: stuck main, STOP, rescue (failed), warm retry (proved)
    assert len(spawn_calls) == 4
    assert spawn_calls[0].rescue_prompt is None
    assert spawn_calls[1].rescue_prompt == STOP_PROMPT
    assert spawn_calls[2].rescue_prompt is not None
    assert spawn_calls[2].rescue_prompt != STOP_PROMPT
    assert spawn_calls[3].rescue_prompt is None
    # pending_failures stores dicts (events.py shape); look for the
    # buffered stuck-thinking marker.
    reasons = [f["reason"] for f in r.pending_failures]
    assert "agent_stuck_thinking" in reasons


def test_rescue_spawn_uses_caller_supplied_prompt(
    conn: sqlite3.Connection,
) -> None:
    """The kind-specific rescue text (Builder vs Backward) is passed
    via the helper's `rescue_prompt` parameter and surfaces verbatim
    on the second rescue-phase SpawnCtx.rescue_prompt (the first is
    the framework-level STOP_PROMPT)."""
    from Tooling.pipeline._retry import STOP_PROMPT
    gid = _seed_open_goal(conn)
    captured_rescue_prompts: list[str] = []

    def spawn(ctx: SpawnCtx) -> int:
        if ctx.rescue_prompt is not None and ctx.rescue_prompt != STOP_PROMPT:
            captured_rescue_prompts.append(ctx.rescue_prompt)
            return SpawnRC.OK
        if ctx.rescue_prompt == STOP_PROMPT:
            return SpawnRC.OK
        return SpawnRC.STUCK_THINKING

    def parse() -> PipelineResult:
        return PipelineResult(outcome="proved")

    custom = "BWRESCUE: ship now + new_<slug>.lean stubs."
    run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-rescue-prompt",
        budget_threshold=3, shelve_threshold=8,
        attempts_dir=Path("/tmp/x"),
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
        rescue_prompt=custom,
    )
    assert captured_rescue_prompts == [custom]
