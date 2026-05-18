"""Watchdog + fresh-sid takeover — STUCK_THINKING uses combined
single-stage takeover (2026-05-10 v4); TIMEOUT-with-trap uses the
two-stage variant (kept for the case where broken jsonl has more
salvageable content than a watchdog-killed mid-thinking session).

  * STUCK_THINKING (rc=128 from watchdog AND-condition kill): single
    fresh-sid spawn with combined budget (stage2 + postmortem) and
    the ship-or-bail prompt.
  * TIMEOUT (rc=124) + parser final state == trap: two-stage fresh-
    sid spawns (ship-or-bail then postmortem-only) — broken jsonl
    may have completed turns the agent didn't get to ship.

Both copy the broken session's jsonl to
`attempts_dir/_broken_session.jsonl` so the agent can Read it. The
end-to-end behavior (real watchdog killing real claude.exe) lives in
integration runs, not here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
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

def test_stuck_thinking_combined_takeover_ships_attaches(
    conn: sqlite3.Connection,
) -> None:
    """rc=128 → single combined fresh-sid takeover (no stage 3).
    Combined spawn ships terminal → helper attaches. Total spawns:
    main (stuck) + combined = 2."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
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
        f"expected 2 spawns (main + combined), got {len(spawn_calls)}")
    # Combined spawn: cold + inline_prompt + budget_override.
    assert spawn_calls[1].cold is True
    assert spawn_calls[1].inline_prompt is not None
    assert "ship ONE of" in spawn_calls[1].inline_prompt
    assert spawn_calls[1].budget_override is not None
    assert spawn_calls[1].sid != spawn_calls[0].sid


def test_stuck_thinking_combined_fails_buffers_and_continues(
    conn: sqlite3.Connection,
) -> None:
    """Combined takeover spawn fails to ship terminal. Helper buffers
    `agent_stuck_thinking` and continues retry loop with the combined
    fresh sid for the warm retry. NO stage 3 fires (that's the
    TIMEOUT-trap path's job, not STUCK_THINKING)."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # main: stuck. combined takeover: rc=124. Iter 1 warm: proved.
        if ctx.inline_prompt is not None:
            return SpawnRC.TIMEOUT
        non_inline = [c for c in spawn_calls if c.inline_prompt is None]
        if len(non_inline) == 1:
            return SpawnRC.STUCK_THINKING
        return SpawnRC.OK

    parse_calls = [0]

    def parse() -> PipelineResult:
        parse_calls[0] += 1
        # combined parse: non-terminal. iter 1 warm: proved.
        if parse_calls[0] <= 1:
            return PipelineResult(outcome="failed",
                                  failure_reason="parse_proposal_fail",
                                  failure_detail="no usable output")
        return PipelineResult(outcome="proved")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-combined-fail",
        budget_threshold=5, shelve_threshold=8,
        attempts_dir=Path("/tmp/x"),
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
    )
    assert r.outcome == "proved"
    # main + combined + iter1 warm = 3 spawns. No stage 3.
    assert len(spawn_calls) == 3, (
        f"STUCK_THINKING must NOT spawn stage 3 — expected 3 spawns "
        f"(main + combined + warm), got {len(spawn_calls)}")
    # Iter 1 warm uses the combined fresh sid (not the broken main sid).
    assert spawn_calls[2].sid == spawn_calls[1].sid
    assert spawn_calls[2].sid != spawn_calls[0].sid
    assert spawn_calls[2].inline_prompt is None
    # Buffered failure says combined (not stage2/stage3).
    reasons = [f["reason"] for f in r.pending_failures]
    assert "agent_stuck_thinking" in reasons
    stuck = [f for f in r.pending_failures
             if f["reason"] == "agent_stuck_thinking"][0]
    assert "combined" in stuck["detail"]
    assert "stage2" not in stuck["detail"]
    assert "stage3" not in stuck["detail"]


def test_timeout_trap_uses_combined_takeover(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """rc=124 + salvage parse fail + parser_state.json shows trap →
    single-stage combined fresh-sid takeover (same shape as the
    watchdog STUCK_THINKING path). The legacy 2-stage path
    (_run_fresh_sid_takeover, removed 2026-05-18) assumed broken jsonl
    might carry salvageable completed turns; in practice
    `is_thinking_trap=True` means it doesn't, so the postmortem-only
    stage 3 spawn added no value over stage 2's combined ship/bail."""
    import json
    gid = _seed_open_goal(conn)
    attempts_dir = tmp_path / ".attempts" / "pid-timeout"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "_parser_state.json").write_text(json.dumps({
        "state": "mid-thinking",
        "last_stop_reason": None,
        "messages_seen": 5,
        "is_thinking_trap": True,
    }), encoding="utf-8")

    spawn_calls: list[SpawnCtx] = []
    parse_calls = [0]

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        if ctx.inline_prompt is None:
            return SpawnRC.TIMEOUT  # main: subprocess timeout
        return SpawnRC.OK  # combined takeover returns clean

    def parse() -> PipelineResult:
        parse_calls[0] += 1
        # parse 1: salvage on main TIMEOUT — non-terminal.
        # parse 2: combined takeover — terminal agent_bailed.
        if parse_calls[0] == 1:
            return PipelineResult(outcome="failed",
                                  failure_reason="parse_proposal_fail",
                                  failure_detail="no usable output")
        return PipelineResult(outcome="failed",
                              failure_reason="agent_bailed",
                              failure_detail="bail via _progress.md")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-timeout",
        budget_threshold=5, shelve_threshold=8,
        attempts_dir=attempts_dir,
        spawn_fn=spawn, parse_fn=parse,
        postmortem_fn=lambda _sid: None,
    )
    assert r.failure_reason == "agent_bailed"
    # main + combined = 2 spawns (no stage 3).
    assert len(spawn_calls) == 2, (
        f"timeout-trap must NOT spawn stage 3 — expected 2 spawns "
        f"(main + combined), got {len(spawn_calls)}")
    # Combined uses the stage-2 ship-or-bail prompt (handles both paths).
    assert "ship ONE of" in spawn_calls[1].inline_prompt
    # Buffered failure detail should describe a single combined spawn,
    # not stage2/stage3 split. (Only if a buffered failure exists —
    # terminal agent_bailed returns immediately without buffering.)


# ---------------------------------------------------------------------
# _copy_broken_session_jsonl helper
# ---------------------------------------------------------------------

def test_fresh_rescue_prompts_use_explicit_attempts_dir(
    tmp_path: Path,
) -> None:
    """Regression for SG run #10 file-leak BUG: fresh-sid prompts
    must include `attempts_dir/` explicitly in every output file
    reference. Without this, agent's cwd-relative Write goes to
    sandbox root (problem_dir) and framework's parse_fn never sees
    the files. SG run #10 evidence: stage 2 wrote patch.lean +
    new_*.lean to Problems/sylvester_gallai/ root; takeover counted
    as no-deliverable despite agent having shipped valid content."""
    from Tooling.pipeline._retry import _build_fresh_rescue_stage2_prompt
    attempts_dir = tmp_path / ".attempts" / "pid-test"
    attempts_dir.mkdir(parents=True)
    expected_prefix = str(attempts_dir)

    s2 = _build_fresh_rescue_stage2_prompt(attempts_dir, True, 4)
    # Every output file must be qualified with attempts_dir. The
    # combined takeover (used by both trap paths post-2026-05-18)
    # reuses this prompt; the legacy stage-3 prompt was removed
    # together with `_run_fresh_sid_takeover`.
    assert f"{expected_prefix}\\patch.lean" in s2 or \
           f"{expected_prefix}/patch.lean" in s2, \
        "must qualify patch.lean with attempts_dir path"
    assert f"{expected_prefix}\\new_<slug>.lean" in s2 or \
           f"{expected_prefix}/new_<slug>.lean" in s2, \
        "must qualify new_<slug>.lean with attempts_dir path"
    assert f"{expected_prefix}\\_progress.md" in s2 or \
           f"{expected_prefix}/_progress.md" in s2, \
        "bail option must qualify _progress.md with attempts_dir path"


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
