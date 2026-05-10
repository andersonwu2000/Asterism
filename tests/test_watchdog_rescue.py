"""Watchdog + fresh-rescue spawn — replaces MAX_THINKING_TOKENS strategy.

Verifies retry-helper routing of rc=128 (SpawnRC.STUCK_THINKING) to a
fresh-rescue cold spawn: a freshly-minted session id with
`is_fresh_rescue=True` set on SpawnCtx. The broken session is abandoned
(its thinking is dumped to attempts_dir/_prior_analysis.md by the
helper); the fresh spawn cold-starts with a Read directive injecting
`_prior_analysis.md` into the agent's first action.

The end-to-end behavior (real watchdog thread killing real claude.exe
on real session jsonl, fresh session reading the dumped analysis) lives
in integration runs, not here.
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
# retry helper fresh-rescue routing
# ---------------------------------------------------------------------

def test_stuck_thinking_triggers_fresh_rescue_then_ships(
    conn: sqlite3.Connection,
) -> None:
    """rc=128 → fresh-rescue cold spawn. Helper invokes spawn_fn TWICE
    total: main (stuck), then fresh-rescue (cold + is_fresh_rescue +
    fresh sid). Verifies the rescue spawn has a different sid from the
    main, runs cold (cold=True), and signals is_fresh_rescue=True."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0 main: stuck. Fresh-rescue: ships.
        if ctx.is_fresh_rescue:
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
        f"expected 2 spawns (main + fresh-rescue), got {len(spawn_calls)}")
    # Spawn 0: cold main.
    assert spawn_calls[0].is_fresh_rescue is False
    assert spawn_calls[0].cold is True
    # Spawn 1: fresh-rescue — cold, is_fresh_rescue, FRESH sid.
    assert spawn_calls[1].is_fresh_rescue is True
    assert spawn_calls[1].cold is True
    assert spawn_calls[1].sid != spawn_calls[0].sid, (
        "fresh-rescue must use a new sid, not reuse the broken one")


def test_stuck_thinking_fresh_rescue_failure_falls_through_to_retry(
    conn: sqlite3.Connection,
) -> None:
    """If the fresh-rescue spawn fails (rc != 0), helper records
    `agent_stuck_thinking` as a buffered failure and continues the
    normal retry loop. Subsequent warm retries use the FRESH sid (the
    broken one is abandoned permanently)."""
    gid = _seed_open_goal(conn)
    spawn_calls: list[SpawnCtx] = []

    def spawn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        # Iter 0 main: stuck. Fresh-rescue: fails. Iter 1 warm: proved.
        if ctx.is_fresh_rescue:
            return 1  # fresh-rescue failure
        if len([c for c in spawn_calls if not c.is_fresh_rescue]) == 1:
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
    # 3 invocations: stuck main, fresh-rescue (failed), warm retry (proved).
    assert len(spawn_calls) == 3
    assert spawn_calls[0].is_fresh_rescue is False
    assert spawn_calls[1].is_fresh_rescue is True
    # Subsequent warm retry uses the FRESH sid, not the original broken one.
    assert spawn_calls[2].sid == spawn_calls[1].sid
    assert spawn_calls[2].sid != spawn_calls[0].sid
    assert spawn_calls[2].is_fresh_rescue is False
    # pending_failures stores dicts (events.py shape); look for the
    # buffered stuck-thinking marker.
    reasons = [f["reason"] for f in r.pending_failures]
    assert "agent_stuck_thinking" in reasons


def test_fresh_rescue_dumps_prior_analysis_when_jsonl_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The helper's `_dump_prior_thinking` extracts thinking blocks
    from the broken session's jsonl and writes them to
    attempts_dir/_prior_analysis.md. This unit-tests the dump helper
    against a synthetic jsonl."""
    import json
    from Tooling.pipeline._retry import _dump_prior_thinking
    from Tooling.llm import claude_cli
    sid = "abc12345-test-sid"
    fake_jsonl = tmp_path / f"{sid}.jsonl"
    events = [
        {"type": "user", "message": {"content": "task"}},
        {"type": "assistant", "timestamp": "2026-05-10T00:00:01Z",
         "message": {"content": [
             {"type": "thinking", "thinking": "first thought block"},
             {"type": "tool_use", "name": "Read"},
         ]}},
        {"type": "assistant", "timestamp": "2026-05-10T00:01:00Z",
         "message": {"content": [
             {"type": "thinking",
              "thinking": "deep reasoning about Kelly minimiser"},
         ]}},
    ]
    with open(fake_jsonl, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    monkeypatch.setattr(claude_cli, "_find_session_jsonl",
                        lambda s: fake_jsonl if s == sid else None)
    out = tmp_path / "_prior_analysis.md"
    ok = _dump_prior_thinking(sid, out)
    assert ok is True
    body = out.read_text(encoding="utf-8")
    assert "first thought block" in body
    assert "deep reasoning about Kelly minimiser" in body
    assert "2026-05-10T00:00:01Z" in body
    assert "2026-05-10T00:01:00Z" in body


def test_fresh_rescue_dump_returns_false_when_jsonl_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dump helper returns False (graceful) when session jsonl can't
    be located. Caller's fresh-rescue still proceeds; agent just
    doesn't see prior analysis."""
    from Tooling.pipeline._retry import _dump_prior_thinking
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli, "_find_session_jsonl", lambda _: None)
    ok = _dump_prior_thinking("missing-sid", tmp_path / "_prior_analysis.md")
    assert ok is False
    assert not (tmp_path / "_prior_analysis.md").exists()
