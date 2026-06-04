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
                  monkeypatch: pytest.MonkeyPatch) -> tuple[list[bool], list[bool]]:
    """Run `_watchdog` in a thread with the trap-check floor lowered so
    the trigger fires fast. Returns (stuck_flag, done_flag) once the
    thread exits."""
    monkeypatch.setattr(claude_cli, "_MIN_TRAP_CHECK_SEC", 0)
    stuck: list[bool] = [False]
    done: list[bool] = [False]
    th = threading.Thread(
        target=claude_cli._watchdog,
        args=(proc, sid),
        kwargs={"stuck_flag": stuck, "done_flag": done,
                "timeout_sec": timeout_sec, "parser": parser},
        daemon=True,
    )
    th.start()
    th.join(timeout=8.0)
    return stuck, done


# ---------------------------------------------------------------------
# Trap detection at wall_cap → kill
# ---------------------------------------------------------------------

def test_watchdog_kills_when_mid_thinking_at_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser state == MID_THINKING at wall_cap → trap → kill,
    stuck_flag set, proc terminated. Routes to STUCK_THINKING →
    fresh-sid stage 2/3."""
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
    parser = StreamParser()
    _seed_mid_thinking(parser)
    proc = _FakeProc()
    flag, _done = _run_watchdog(proc, "abc12345", parser, timeout_sec=2,
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
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
    parser = StreamParser()
    _seed_finalized_max_tokens(parser)
    proc = _FakeProc()
    flag, _done = _run_watchdog(proc, "abc23456", parser, timeout_sec=2,
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
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
    parser = StreamParser()
    _seed_active_tool_use(parser)
    proc = _FakeProc()
    flag, _done = _run_watchdog(proc, "abc34567", parser, timeout_sec=2,
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
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
    parser = StreamParser()  # initial state: IDLE, no events fed
    proc = _FakeProc()
    flag, _done = _run_watchdog(proc, "abc45678", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0


def test_watchdog_defers_when_finalized_clean_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FINALIZED + last_stop_reason == 'tool_use' / 'end_turn' is a
    clean turn end, NOT a trap. Watchdog must not kill here — agent
    is between turns."""
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
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
    flag, _done = _run_watchdog(proc, "abc56789", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0


# ---------------------------------------------------------------------
# Completion reclaim — clean end_turn that persists while proc hangs
# ---------------------------------------------------------------------

def _seed_finalized_end_turn(parser: StreamParser) -> None:
    """Drive the parser to FINALIZED with last_stop_reason=end_turn
    (a clean terminal finish — the agent chose to stop, no tool call)."""
    parser.feed_line(_stream_event({"type": "message_start",
                                    "message": {"id": "m"}}))
    parser.feed_line(_stream_event({
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "text", "text": ""}}))
    parser.feed_line(_stream_event({
        "type": "content_block_stop", "index": 0}))
    parser.feed_line(_stream_event({
        "type": "message_delta", "delta": {"stop_reason": "end_turn"}}))
    parser.feed_line(_stream_event({"type": "message_stop"}))


def test_watchdog_reclaims_when_finalized_end_turn_and_proc_hangs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent finalized (end_turn) but the process stays alive past the
    grace window → watchdog terminates and sets done_flag (NOT
    stuck_flag), routing the spawn through the parse/salvage path. This
    is the primary_decomposition sid 77403824 hang (a stranded
    background shell kept `claude -p` alive ~535s past completion)."""
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "30")  # far; completion fires first
    monkeypatch.setenv("ASTERISM_COMPLETION_GRACE_SEC", "0")
    parser = StreamParser()
    _seed_finalized_end_turn(parser)
    proc = _FakeProc()  # stays alive (poll None) until terminated
    stuck, done = _run_watchdog(proc, "donehang", parser, timeout_sec=40,
                                monkeypatch=monkeypatch)
    assert done[0] is True, (
        "clean end_turn persisting while the process hangs must trigger "
        "completion-reclaim")
    assert stuck[0] is False, "reclaim is not a stuck-thinking kill"
    assert proc.term_calls + proc.kill_calls >= 1


def test_watchdog_no_reclaim_when_proc_exits_within_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent finalized (end_turn) and the process exits promptly (the
    normal case) → watchdog must NOT reclaim; the natural-exit return
    fires, no terminate, done_flag stays False."""
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "30")
    monkeypatch.setenv("ASTERISM_COMPLETION_GRACE_SEC", "60")  # never reached
    parser = StreamParser()
    _seed_finalized_end_turn(parser)
    # poll() returns None once (loop entry) then 0 — proc exits right after.
    proc = _RacingProc(poll_returns_none_count=1)
    stuck, done = _run_watchdog(proc, "exitfast", parser, timeout_sec=40,
                                monkeypatch=monkeypatch)
    assert done[0] is False, "a normally-exiting spawn must not be reclaimed"
    assert stuck[0] is False
    assert proc.term_calls == 0
    assert proc.kill_calls == 0


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
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
    parser = StreamParser()
    _seed_mid_thinking(parser)  # would trigger trap if sampled
    proc = _FakeProc()
    proc._done = True  # already finished
    flag, _done = _run_watchdog(proc, "abc67890", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0
    assert proc.kill_calls == 0


# ---------------------------------------------------------------------
# AND condition tests — both signals required to kill
# ---------------------------------------------------------------------

def test_watchdog_defers_when_trap_but_not_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser is mid-thinking AT trigger but silence is BELOW
    threshold (agent emitted tool_use recently before slipping into
    thinking) → AND fails → defer. The TIMEOUT path's parser-only
    check is the safety net — caught ~5 min later via two-stage
    takeover."""
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    # Threshold high enough that silence (≈ trigger time = 1s) doesn't trip.
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "60")
    parser = StreamParser()
    # Stamp a tool_use FIRST so silence stays low, then go into thinking.
    parser.feed_line(_stream_event({"type": "message_start",
                                    "message": {"id": "m"}}))
    parser.feed_line(_stream_event({
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "tool_use", "id": "t",
                          "name": "Read", "input": {}}}))
    parser.feed_line(_stream_event({
        "type": "content_block_stop", "index": 0}))
    parser.feed_line(_stream_event({
        "type": "content_block_start", "index": 1,
        "content_block": {"type": "thinking", "thinking": ""}}))
    proc = _FakeProc()
    flag, _done = _run_watchdog(proc, "trapnsil", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False, (
        "AND condition: trap state alone (without silence) must NOT "
        "fire watchdog kill — TIMEOUT path catches this case later")
    assert proc.term_calls == 0


def test_watchdog_defers_when_silent_but_not_trap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silence > threshold (e.g., agent waiting on a long Bash that
    hasn't returned) but parser state is mid-tool (active in tool
    call) → AND fails → defer. Protects long-running tools from
    false positive."""
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
    parser = StreamParser()
    _seed_active_tool_use(parser)  # mid-tool state, low silence
    # Override silence by wiping last_tool_use_ts so silence_seconds
    # reads from spawn_start, which by trigger time is > 0.
    # Actually with threshold=0, silence > 0 trips, but parser state
    # is MID_TOOL → NOT trap → AND fails.
    proc = _FakeProc()
    flag, _done = _run_watchdog(proc, "silnotr", parser, timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False, (
        "AND condition: silence alone (without trap state) must NOT "
        "fire watchdog kill — could be a slow Bash / lake build")
    assert proc.term_calls == 0


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
    monkeypatch.setenv("ASTERISM_TRAP_CHECK_SEC", "1")
    monkeypatch.setenv("ASTERISM_SILENCE_THRESHOLD_SEC", "0")
    parser = StreamParser()
    _seed_mid_thinking(parser)
    # Polls: (1) wait-loop iteration, (2) wait-loop exit re-check
    # (returns None → continues to sample), (3) trap-branch re-poll
    # (returns 0 → skip kill).
    proc = _RacingProc(poll_returns_none_count=2)
    flag, _done = _run_watchdog(proc, "raceabcd", parser, timeout_sec=2,
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
