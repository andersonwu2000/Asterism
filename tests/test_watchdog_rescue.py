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

def test_stuck_thinking_triggers_rescue_then_ships(
    conn: sqlite3.Connection,
) -> None:
    """First spawn returns rc=128 (watchdog stuck-kill). Helper sends
    a rescue spawn (one extra invocation of spawn_fn with
    ctx.rescue_prompt set) — that one returns rc=0 and parse_fn yields
    'proved'. Helper attaches the rescue result and exits without
    counting the stuck spawn against shelve_threshold."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0: stuck. Iter 0-rescue: success.
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
    assert len(spawn_calls) == 2
    assert spawn_calls[0].rescue_prompt is None  # normal spawn
    assert spawn_calls[1].rescue_prompt == "ship now no analysis"


def test_stuck_thinking_rescue_failure_falls_through_to_retry(
    conn: sqlite3.Connection,
) -> None:
    """If the rescue spawn itself fails (rc!=0), helper records
    `agent_stuck_thinking` as a buffered failure and continues the
    normal retry loop. The next iteration's spawn is a regular warm
    retry (not another rescue) — rescue gets at most one shot per
    stuck-kill, so the helper makes progress instead of looping."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0: stuck. Iter 0-rescue: also fails. Iter 1: proved.
        if ctx.rescue_prompt is not None:
            return 1  # rescue failure
        if len(spawn_calls) == 1:
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
    # 3 invocations: stuck spawn, rescue (failed), warm retry (proved)
    assert len(spawn_calls) == 3
    assert spawn_calls[0].rescue_prompt is None
    assert spawn_calls[1].rescue_prompt is not None
    assert spawn_calls[2].rescue_prompt is None
    # pending_failures stores dicts (events.py shape); look for the
    # buffered stuck-thinking marker.
    reasons = [f["reason"] for f in r.pending_failures]
    assert "agent_stuck_thinking" in reasons


def test_rescue_spawn_uses_caller_supplied_prompt(
    conn: sqlite3.Connection,
) -> None:
    """The kind-specific rescue text (Builder vs Backward) is passed
    via the helper's `rescue_prompt` parameter and surfaces verbatim
    on SpawnCtx.rescue_prompt — kind-specific spawn callbacks can
    branch on `ctx.rescue_prompt` to honour the tight budget + force-
    ship semantics."""
    gid = _seed_open_goal(conn)
    captured_rescue_prompts: list[str] = []

    def spawn(ctx: SpawnCtx) -> int:
        if ctx.rescue_prompt is not None:
            captured_rescue_prompts.append(ctx.rescue_prompt)
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
