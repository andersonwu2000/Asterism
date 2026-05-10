"""Watchdog + two-stage fresh-rescue spawn — replaces MAX_THINKING_TOKENS strategy.

Verifies retry-helper routing of rc=128 (SpawnRC.STUCK_THINKING) to a
two-stage takeover: when the original session is unrecoverable, fresh
sessions take over its remaining workflow stages (rescue + postmortem).

  * Stage 2: fresh sid #2 cold-spawned with stage-2 prompt
    (`inline_prompt`, ship-or-bail) and rescue_timeout_sec budget.
  * Stage 3 (if stage 2 doesn't reach terminal): fresh sid #3 cold-
    spawned with stage-3 prompt (postmortem-style) and
    postmortem_timeout_sec budget.

Both stages copy the broken session's jsonl to
`attempts_dir/_broken_session.jsonl` so the agent can Read it. The
end-to-end behavior (real watchdog killing real claude.exe) lives in
integration runs, not here.
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
# retry helper two-stage fresh-rescue
# ---------------------------------------------------------------------

def test_stuck_thinking_stage2_ships_attaches_immediately(
    conn: sqlite3.Connection,
) -> None:
    """rc=128 → stage 2 fresh-rescue (cold + inline_prompt + 180s
    budget). If stage 2 ships valid output (parse returns terminal),
    helper attaches and exits without spawning stage 3. Total spawns:
    main (stuck) + stage2 = 2."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0 main: stuck. Stage 2: ships.
        if ctx.inline_prompt is not None:
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
    )
    assert r.outcome == "proved"
    assert len(spawn_calls) == 2, (
        f"expected 2 spawns (main + stage2), got {len(spawn_calls)}")
    # Spawn 0: main cold, no inline prompt.
    assert spawn_calls[0].inline_prompt is None
    assert spawn_calls[0].cold is True
    # Spawn 1: stage 2 — cold, inline_prompt set, budget_override set.
    assert spawn_calls[1].cold is True
    assert spawn_calls[1].inline_prompt is not None
    assert "ship ONE of" in spawn_calls[1].inline_prompt
    assert spawn_calls[1].budget_override is not None
    assert spawn_calls[1].sid != spawn_calls[0].sid


def test_stuck_thinking_stage2_fails_stage3_ships_postmortem(
    conn: sqlite3.Connection,
) -> None:
    """Stage 2 fails (parse non-terminal), stage 3 fires with
    postmortem prompt + postmortem_timeout_sec budget. Stage 3 writes
    `_progress.md` → parse detects bail → terminal → attach. Total
    spawns: main + stage2 + stage3 = 3."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []
    parse_calls = [0]

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # main: stuck. stage2: rc=124 timeout. stage3: rc=0 (writes
        # _progress.md, simulated by parse returning agent_bailed).
        if ctx.inline_prompt is None:
            return SpawnRC.STUCK_THINKING
        # stage 2 (first inline) → timeout; stage 3 (second) → ok
        inline_count = sum(1 for c in spawn_calls if c.inline_prompt)
        if inline_count == 1:
            return SpawnRC.TIMEOUT
        return SpawnRC.OK

    def parse() -> PipelineResult:
        parse_calls[0] += 1
        # parse called after stage 2 (no salvageable output, non-
        # terminal failure) and after stage 3 (agent_bailed).
        if parse_calls[0] == 1:
            return PipelineResult(outcome="failed",
                                  failure_reason="parse_proposal_fail",
                                  failure_detail="no patch on disk")
        return PipelineResult(outcome="failed",
                              failure_reason="agent_bailed",
                              failure_detail="bail via _progress.md")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-stage23",
        budget_threshold=5, shelve_threshold=8,
        attempts_dir=Path("/tmp/x"),
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
    )
    assert r.failure_reason == "agent_bailed"
    assert len(spawn_calls) == 3
    # Spawn 1: stage 2 — ship-or-bail prompt
    assert "ship ONE of" in spawn_calls[1].inline_prompt
    # Spawn 2: stage 3 — postmortem prompt
    assert "_progress.md" in spawn_calls[2].inline_prompt
    assert "decomposition shape" in spawn_calls[2].inline_prompt.lower()
    # Stage 3 sid is fresh (different from stage 2's fresh sid).
    assert spawn_calls[2].sid != spawn_calls[1].sid


def test_stuck_thinking_both_stages_fail_buffers_and_continues(
    conn: sqlite3.Connection,
) -> None:
    """Both fresh-rescue stages fail (no terminal parse outcome).
    Helper buffers `agent_stuck_thinking` and continues retry loop.
    Subsequent warm retries use the LAST fresh sid (stage 3)."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # main: stuck. stage2 + stage3 both rc=124. Iter 1 warm: proved.
        if ctx.inline_prompt is not None:
            return SpawnRC.TIMEOUT
        # cold or warm main spawns
        non_inline = [c for c in spawn_calls if c.inline_prompt is None]
        if len(non_inline) == 1:
            return SpawnRC.STUCK_THINKING
        return SpawnRC.OK

    parse_calls = [0]

    def parse() -> PipelineResult:
        parse_calls[0] += 1
        # stage2 + stage3 parses both non-terminal; iter 1 warm: proved.
        if parse_calls[0] <= 2:
            return PipelineResult(outcome="failed",
                                  failure_reason="parse_proposal_fail",
                                  failure_detail="no usable output")
        return PipelineResult(outcome="proved")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-both-fail",
        budget_threshold=5, shelve_threshold=8,
        attempts_dir=Path("/tmp/x"),
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
    )
    assert r.outcome == "proved"
    # main + stage2 + stage3 + iter1 warm = 4 spawns
    assert len(spawn_calls) == 4
    # Iter 1 warm uses the LAST fresh sid (stage 3), not the
    # original broken main sid.
    assert spawn_calls[3].sid == spawn_calls[2].sid
    assert spawn_calls[3].sid != spawn_calls[0].sid
    assert spawn_calls[3].inline_prompt is None
    # Buffered failure has agent_stuck_thinking with both stage rcs.
    reasons = [f["reason"] for f in r.pending_failures]
    assert "agent_stuck_thinking" in reasons
    stuck = [f for f in r.pending_failures
             if f["reason"] == "agent_stuck_thinking"][0]
    assert "stage2" in stuck["detail"]
    assert "stage3" in stuck["detail"]


# ---------------------------------------------------------------------
# _copy_broken_session_jsonl helper
# ---------------------------------------------------------------------

def test_copy_broken_session_jsonl_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helper copies the broken session's jsonl to the destination
    path so the fresh-rescue agent can Read it from inside its
    sandbox."""
    from Tooling.pipeline._retry import _copy_broken_session_jsonl
    from Tooling.llm import claude_cli
    src = tmp_path / "broken.jsonl"
    src.write_text('{"event": "fake"}\n', encoding="utf-8")
    monkeypatch.setattr(claude_cli, "_find_session_jsonl",
                        lambda sid: src if sid == "abc" else None)
    dest = tmp_path / "_broken_session.jsonl"
    ok = _copy_broken_session_jsonl("abc", dest)
    assert ok is True
    assert dest.read_text(encoding="utf-8") == '{"event": "fake"}\n'


def test_copy_broken_session_jsonl_returns_false_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helper returns False (graceful) when source jsonl can't be
    located. Caller's fresh-rescue still proceeds; agent works from
    Context.md alone."""
    from Tooling.pipeline._retry import _copy_broken_session_jsonl
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli, "_find_session_jsonl", lambda _: None)
    dest = tmp_path / "_broken_session.jsonl"
    ok = _copy_broken_session_jsonl("missing-sid", dest)
    assert ok is False
    assert not dest.exists()
