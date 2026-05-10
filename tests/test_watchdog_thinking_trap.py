"""Watchdog thinking-trap detection — replaces the prior
idle_window_sec silence test (retired 2026-05-10 with the stream-json
switch).

The watchdog now samples the StreamParser at a single trigger point
(spawn_start + (timeout - rescue_budget)). At that moment it asks
`parser.is_thinking_trap()` — True iff state == mid-thinking OR
finalized + last_stop_reason == max_tokens. The watchdog kills the
proc only on True; otherwise it exits and lets subprocess timeout +
TIMEOUT-path postmortem handle the eventual deadline.

These tests drive the real `_watchdog` thread with a fake Popen and
a real StreamParser pre-populated to simulate each end state.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from Tooling.llm import claude_cli
from Tooling.llm.stream_parser import StreamParser


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

class _FakeProc:
    """Quack-like-Popen: poll() returns None until terminated, then 0.
    terminate() / kill() set the done flag (mirrors real Popen behavior
    after watchdog stuck-kill)."""

    def __init__(self) -> None:
        self._done = False
        self.term_calls = 0
        self.kill_calls = 0

    def poll(self):
        return None if not self._done else 0

    def terminate(self) -> None:
        self.term_calls += 1
        self._done = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.kill_calls += 1
        self._done = True


def _stream_event(event: dict) -> str:
    """Wrap an Anthropic SSE event in claude CLI's stream-json envelope."""
    return json.dumps({"type": "stream_event", "event": event,
                       "session_id": "test", "uuid": "u"})


def _seed_mid_thinking(parser: StreamParser) -> None:
    """Drive the parser to MID_THINKING state."""
    parser.feed_line(_stream_event({"type": "message_start",
                                    "message": {"id": "m"}}))
    parser.feed_line(_stream_event({
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "thinking", "thinking": ""}}))


def _seed_finalized_max_tokens(parser: StreamParser) -> None:
    """Drive the parser to FINALIZED with last_stop_reason=max_tokens."""
    parser.feed_line(_stream_event({"type": "message_start",
                                    "message": {"id": "m"}}))
    parser.feed_line(_stream_event({
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "thinking", "thinking": ""}}))
    parser.feed_line(_stream_event({
        "type": "content_block_stop", "index": 0}))
    parser.feed_line(_stream_event({
        "type": "message_delta",
        "delta": {"stop_reason": "max_tokens"}}))
    parser.feed_line(_stream_event({"type": "message_stop"}))


def _seed_active_tool_use(parser: StreamParser) -> None:
    """Drive the parser to MID_TOOL state (active, not trap)."""
    parser.feed_line(_stream_event({"type": "message_start",
                                    "message": {"id": "m"}}))
    parser.feed_line(_stream_event({
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "tool_use", "id": "t",
                          "name": "Read", "input": {}}}))


def _run_watchdog(proc, sid: str, parser: StreamParser, *,
                  timeout_sec: int,
                  monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Run `_watchdog` in a thread with the wall_cap floor lowered
    so trigger fires fast. Returns the stuck_flag once thread exits."""
    monkeypatch.setattr(claude_cli, "_MIN_WALL_CAP_SEC", 0)
    flag: list[bool] = [False]
    th = threading.Thread(
        target=claude_cli._watchdog,
        args=(proc, sid),
        kwargs={"stuck_flag": flag, "timeout_sec": timeout_sec,
                "parser": parser},
        daemon=True,
    )
    th.start()
    th.join(timeout=5.0)
    return flag


# ---------------------------------------------------------------------
# Trap detection at wall_cap → kill
# ---------------------------------------------------------------------

def test_watchdog_kills_when_mid_thinking_at_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser state == MID_THINKING at wall_cap → trap → kill,
    stuck_flag set, proc terminated. Routes to STUCK_THINKING →
    fresh-sid stage 2/3."""
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    parser = StreamParser()
    _seed_mid_thinking(parser)
    proc = _FakeProc()
    flag = _run_watchdog(proc, "abc12345", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is True
    assert proc.term_calls + proc.kill_calls >= 1


def test_watchdog_kills_when_finalized_max_tokens_at_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser state == FINALIZED + last_stop_reason == max_tokens →
    trap → kill. Mirrors the s219 case 2 evidence: agent finalized a
    thinking-only message at max_tokens, never recovered, would have
    been silently dropped by silence-only detection."""
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    parser = StreamParser()
    _seed_finalized_max_tokens(parser)
    proc = _FakeProc()
    flag = _run_watchdog(proc, "abc23456", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is True
    assert proc.term_calls + proc.kill_calls >= 1


# ---------------------------------------------------------------------
# Active state at wall_cap → defer
# ---------------------------------------------------------------------

def test_watchdog_defers_when_mid_tool_at_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser state == MID_TOOL at wall_cap → not trap → defer
    quietly. Subprocess timeout + TIMEOUT-path postmortem handle
    eventual deadline."""
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    parser = StreamParser()
    _seed_active_tool_use(parser)
    proc = _FakeProc()
    flag = _run_watchdog(proc, "abc34567", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0
    assert proc.kill_calls == 0


def test_watchdog_defers_when_idle_at_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser state == IDLE at wall_cap (no message activity yet) →
    not trap. Cold spawn that hasn't started its first message is
    pre-trap, not in-trap."""
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    parser = StreamParser()  # initial state: IDLE, no events fed
    proc = _FakeProc()
    flag = _run_watchdog(proc, "abc45678", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0


def test_watchdog_defers_when_finalized_clean_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FINALIZED + last_stop_reason == 'tool_use' / 'end_turn' is a
    clean turn end, NOT a trap. Watchdog must not kill here — agent
    is between turns."""
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    parser = StreamParser()
    parser.feed_line(_stream_event({"type": "message_start",
                                    "message": {"id": "m"}}))
    parser.feed_line(_stream_event({
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "tool_use", "id": "t",
                          "name": "Read", "input": {}}}))
    parser.feed_line(_stream_event({
        "type": "content_block_stop", "index": 0}))
    parser.feed_line(_stream_event({
        "type": "message_delta", "delta": {"stop_reason": "tool_use"}}))
    parser.feed_line(_stream_event({"type": "message_stop"}))
    proc = _FakeProc()
    flag = _run_watchdog(proc, "abc56789", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0


# ---------------------------------------------------------------------
# Proc dies before trigger → no decision
# ---------------------------------------------------------------------

def test_watchdog_exits_when_proc_finishes_before_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proc finishes naturally before wall_cap → watchdog exits
    without sampling parser. No kill, stuck_flag stays False even if
    parser state happens to be MID_THINKING (race).

    Strategy: pre-finished proc — `poll()` returns 0 immediately, so
    the watchdog's wait loop exits at the first check without
    consulting parser state.
    """
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    parser = StreamParser()
    _seed_mid_thinking(parser)  # would trigger trap if sampled
    proc = _FakeProc()
    proc._done = True  # already finished
    flag = _run_watchdog(proc, "abc67890", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0
    assert proc.kill_calls == 0


# ---------------------------------------------------------------------
# Race regression: proc dies between wait-loop exit and trap sampling
# ---------------------------------------------------------------------

class _RacingProc:
    """Like _FakeProc but `poll()` returns None on the first N calls
    then transitions to 0 — simulates a proc that finishes between the
    watchdog's wait-loop exit (line: `if proc.poll() is not None`) and
    the trap-branch's re-poll. Without the re-poll guard, the watchdog
    would set stuck_flag=True on a finished spawn → SpawnRC.STUCK_THINKING
    → unnecessary ~6-minute fresh-sid takeover."""

    def __init__(self, poll_returns_none_count: int = 2) -> None:
        self._poll_count = 0
        self._poll_threshold = poll_returns_none_count
        self.term_calls = 0
        self.kill_calls = 0

    def poll(self):
        self._poll_count += 1
        return None if self._poll_count <= self._poll_threshold else 0

    def terminate(self) -> None:
        self.term_calls += 1

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.kill_calls += 1


def test_watchdog_skips_kill_when_proc_dies_during_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Race regression: at the trigger moment, parser state is trap
    (mid-thinking) but proc finished microseconds before sample. The
    watchdog must re-poll inside the trap branch and skip kill +
    stuck_flag if proc is already dead. Otherwise a legitimately-
    completed spawn would route into the fresh-sid takeover.

    Strategy: _RacingProc returns None on poll calls 1+2 (wait-loop
    exit + first trap-branch re-check sees alive at exit), then 0 on
    poll 3 (re-poll inside trap branch sees dead).
    """
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    parser = StreamParser()
    _seed_mid_thinking(parser)
    # Polls: (1) wait-loop iteration, (2) wait-loop exit re-check
    # (returns None → continues to sample), (3) trap-branch re-poll
    # (returns 0 → skip kill).
    proc = _RacingProc(poll_returns_none_count=2)
    flag = _run_watchdog(proc, "raceabcd", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False, (
        "stuck_flag must NOT be set when proc finishes during the "
        "trap-sample race window — otherwise a completed spawn gets "
        "routed into the fresh-sid takeover unnecessarily")
    assert proc.term_calls == 0
    assert proc.kill_calls == 0


# ---------------------------------------------------------------------
# _find_session_jsonl regression — kept since _retry.py uses it
# ---------------------------------------------------------------------

def test_find_session_jsonl_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_find_session_jsonl` is still used by `_retry.py`'s
    `_copy_broken_session_jsonl` to locate the broken session's
    history for fresh-sid takeover. Regression guard: missing
    `~/.claude/projects` returns None (no crash)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert claude_cli._find_session_jsonl("nonexistent-sid") is None
