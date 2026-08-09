"""Unit tests for Tooling.llm.stream_parser.

Each test feeds canonical claude CLI stream-json lines (captured from
real `--output-format stream-json --include-partial-messages` output)
and asserts the resulting parser state. Trap-detection tests cover the
two manifestations the watchdog cares about:
  (a) currently in mid-thinking — agent stream is still emitting
      thinking deltas with no tool_use_start.
  (b) finalized + last_stop_reason == max_tokens — completed thinking-
      only message hit budget cap.
"""
from __future__ import annotations

import json

from Tooling.llm.stream_parser import (
    ParserState, StateSnapshot, StreamParser,
)


# ---------------------------------------------------------------------
# Stream event constructors mirroring claude CLI envelope
# ---------------------------------------------------------------------

def _stream_event(event: dict) -> str:
    """Wrap an Anthropic SSE event into claude CLI's stream-json
    envelope, return one JSONLines string (no trailing newline)."""
    return json.dumps({
        "type": "stream_event",
        "event": event,
        "session_id": "test-sid",
        "uuid": "test-uuid",
    })


def _message_start() -> str:
    return _stream_event({
        "type": "message_start",
        "message": {
            "id": "msg_test", "role": "assistant", "content": [],
            "stop_reason": None,
        },
    })


def _content_block_start(index: int, block_type: str) -> str:
    cb: dict = {"type": block_type}
    if block_type == "thinking":
        cb["thinking"] = ""
    elif block_type == "text":
        cb["text"] = ""
    elif block_type == "tool_use":
        cb.update({"id": "toolu_x", "name": "Read", "input": {}})
    return _stream_event({
        "type": "content_block_start",
        "index": index,
        "content_block": cb,
    })


def _content_block_delta(index: int, delta_type: str,
                         payload: str = "x") -> str:
    delta: dict = {"type": delta_type}
    if delta_type == "thinking_delta":
        delta["thinking"] = payload
    elif delta_type == "text_delta":
        delta["text"] = payload
    elif delta_type == "input_json_delta":
        delta["partial_json"] = payload
    return _stream_event({
        "type": "content_block_delta",
        "index": index,
        "delta": delta,
    })


def _content_block_stop(index: int) -> str:
    return _stream_event({
        "type": "content_block_stop",
        "index": index,
    })


def _message_delta(stop_reason: str) -> str:
    return _stream_event({
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": 10},
    })


def _message_stop() -> str:
    return _stream_event({"type": "message_stop"})


# ---------------------------------------------------------------------
# Initial state + tolerance
# ---------------------------------------------------------------------

def test_initial_state_is_idle() -> None:
    p = StreamParser()
    snap = p.snapshot()
    assert snap.state == ParserState.IDLE
    assert snap.last_stop_reason is None
    assert snap.messages_seen == 0


def test_malformed_json_silently_ignored() -> None:
    """Mid-write claude output may produce a partial line. Parser must
    not raise — partial lines are skipped, state stays unchanged."""
    p = StreamParser()
    p.feed_line('{"type":"stream_event","event":{"ty')  # truncated
    p.feed_line("not json at all")
    p.feed_line("")
    assert p.snapshot().state == ParserState.IDLE


def test_non_stream_event_lines_ignored() -> None:
    """system / assistant / result lines (non-stream_event) don't
    drive state — only stream_events do. Otherwise the duplicated
    `assistant` message-completion line would create false transitions."""
    p = StreamParser()
    p.feed_line(json.dumps({"type": "system", "subtype": "init"}))
    p.feed_line(json.dumps({"type": "assistant", "message": {
        "content": [{"type": "text", "text": "hi"}],
        "stop_reason": "end_turn",
    }}))
    p.feed_line(json.dumps({"type": "result", "subtype": "success"}))
    assert p.snapshot().state == ParserState.IDLE


# ---------------------------------------------------------------------
# Normal turn: thinking → tool_use → finalized
# ---------------------------------------------------------------------

def test_normal_turn_thinking_then_tool_use() -> None:
    """Canonical agent turn: thinking block, then tool_use block,
    then end. State walks: IDLE → IN_MESSAGE → MID_THINKING →
    IN_MESSAGE → MID_TOOL → IN_MESSAGE → FINALIZED."""
    p = StreamParser()
    states: list[ParserState] = [p.snapshot().state]
    for line in [
        _message_start(),
        _content_block_start(0, "thinking"),
        _content_block_delta(0, "thinking_delta", "considering..."),
        _content_block_stop(0),
        _content_block_start(1, "tool_use"),
        _content_block_delta(1, "input_json_delta", '{"f":'),
        _content_block_stop(1),
        _message_delta("tool_use"),
        _message_stop(),
    ]:
        p.feed_line(line)
        states.append(p.snapshot().state)
    assert states == [
        ParserState.IDLE,
        ParserState.IN_MESSAGE,
        ParserState.MID_THINKING,
        ParserState.MID_THINKING,  # delta doesn't transition
        ParserState.IN_MESSAGE,
        ParserState.MID_TOOL,
        ParserState.MID_TOOL,
        ParserState.IN_MESSAGE,
        ParserState.IN_MESSAGE,    # message_delta doesn't transition
        ParserState.FINALIZED,
    ]
    snap = p.snapshot()
    assert snap.last_stop_reason == "tool_use"
    assert snap.messages_seen == 1


def test_text_only_turn() -> None:
    """Plain text response (no thinking, no tools) — MID_TEXT state
    should appear briefly. Common for trivial prompts."""
    p = StreamParser()
    for line in [
        _message_start(),
        _content_block_start(0, "text"),
        _content_block_delta(0, "text_delta", "hello"),
        _content_block_stop(0),
        _message_delta("end_turn"),
        _message_stop(),
    ]:
        p.feed_line(line)
    snap = p.snapshot()
    assert snap.state == ParserState.FINALIZED
    assert snap.last_stop_reason == "end_turn"


# ---------------------------------------------------------------------
# Trap detection: the two manifestations
# ---------------------------------------------------------------------

def test_trap_detection_mid_thinking_in_flight() -> None:
    """Manifestation (a): agent currently emitting thinking_deltas
    with no follow-up tool_use_start. The watchdog samples this state
    and routes to fresh-sid stage 2 takeover."""
    p = StreamParser()
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "thinking"))
    p.feed_line(_content_block_delta(0, "thinking_delta", "pondering"))
    # Still mid-thinking; no content_block_stop yet.
    snap = p.snapshot()
    assert snap.state == ParserState.MID_THINKING
    assert p.is_thinking_trap() is True


def test_trap_detection_finalized_max_tokens() -> None:
    """Manifestation (b): thinking block completed, message hit
    max_tokens. Agent will likely stay silent without fresh sid
    (s219 case 2 evidence: 38s silence after max_tokens until
    subprocess kill)."""
    p = StreamParser()
    for line in [
        _message_start(),
        _content_block_start(0, "thinking"),
        _content_block_delta(0, "thinking_delta", "thinking hard"),
        _content_block_stop(0),
        _message_delta("max_tokens"),
        _message_stop(),
    ]:
        p.feed_line(line)
    snap = p.snapshot()
    assert snap.state == ParserState.FINALIZED
    assert snap.last_stop_reason == "max_tokens"
    assert p.is_thinking_trap() is True


def test_no_trap_after_normal_completion() -> None:
    """Normal turn ending in tool_use or end_turn → not a trap.
    Watchdog should NOT kill."""
    p = StreamParser()
    for line in [
        _message_start(),
        _content_block_start(0, "tool_use"),
        _content_block_stop(0),
        _message_delta("tool_use"),
        _message_stop(),
    ]:
        p.feed_line(line)
    assert p.is_thinking_trap() is False


def test_no_trap_during_mid_tool() -> None:
    """Agent currently invoking a tool — definitely not stuck thinking."""
    p = StreamParser()
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "tool_use"))
    assert p.snapshot().state == ParserState.MID_TOOL
    assert p.is_thinking_trap() is False


def test_max_tokens_then_new_turn_clears_stop_reason() -> None:
    """Agent recovered from a prior max_tokens by starting a new turn.
    The fresh `message_start` clears last_stop_reason — we don't want
    to trigger trap detection on a stop_reason from a turn the agent
    has already moved past (s219 case 1 recovery: max_tokens at 07:24
    then thinking + Read at 07:24:14-15)."""
    p = StreamParser()
    # Turn 1 hits max_tokens.
    for line in [
        _message_start(),
        _content_block_start(0, "thinking"),
        _content_block_stop(0),
        _message_delta("max_tokens"),
        _message_stop(),
    ]:
        p.feed_line(line)
    assert p.is_thinking_trap() is True
    # Turn 2 begins (claude CLI auto-continued or user re-prompted).
    p.feed_line(_message_start())
    snap = p.snapshot()
    assert snap.last_stop_reason is None
    assert snap.state == ParserState.IN_MESSAGE
    assert p.is_thinking_trap() is False


def test_state_since_advances_on_transition() -> None:
    """state_since timestamp moves forward only when state actually
    changes — repeated deltas in mid-thinking should NOT keep
    resetting it (the watchdog uses state_since to compute how long
    the agent has been stuck)."""
    import time as _time
    p = StreamParser()
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "thinking"))
    t1 = p.snapshot().state_since
    _time.sleep(0.01)
    p.feed_line(_content_block_delta(0, "thinking_delta", "more"))
    p.feed_line(_content_block_delta(0, "thinking_delta", "even more"))
    t2 = p.snapshot().state_since
    assert t1 == t2, "delta events must not reset state_since"


# ---------------------------------------------------------------------
# Snapshot type sanity
# ---------------------------------------------------------------------

def test_snapshot_is_immutable_namedtuple() -> None:
    p = StreamParser()
    snap = p.snapshot()
    assert isinstance(snap, StateSnapshot)
    # NamedTuples don't support attribute assignment; AttributeError
    # confirms we can hand snapshots to consumers without lock concerns.
    import pytest
    with pytest.raises(AttributeError):
        snap.state = ParserState.MID_THINKING  # type: ignore[misc]


# ---------------------------------------------------------------------
# Silence tracking — last_tool_use_ts + silence_seconds
# ---------------------------------------------------------------------

def test_silence_seconds_falls_back_to_spawn_start() -> None:
    """Cold spawn that hasn't emitted any tool_use yet — silence is
    measured from parser creation. Watchdog uses this to detect agents
    stuck in a long thinking-only opening turn."""
    import time as _time
    p = StreamParser()
    snap = p.snapshot()
    assert snap.last_tool_use_ts is None
    # Sleep enough that Windows' coarse timer (15ms granularity)
    # leaves a margin above zero. 50ms requested → at least ~30ms slept.
    _time.sleep(0.05)
    silence = p.silence_seconds(_time.monotonic())
    assert silence > 0.01


def test_silence_seconds_resets_on_tool_use_start() -> None:
    """When agent emits a `content_block_start type=tool_use`, the
    parser stamps last_tool_use_ts. silence_seconds(now) then returns
    `now - last_tool_use_ts`, which should be near-zero immediately."""
    import time as _time
    p = StreamParser()
    _time.sleep(0.05)
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "tool_use"))
    silence = p.silence_seconds(_time.monotonic())
    # Should be near 0, definitely less than the 50ms we slept before.
    assert silence < 0.04, (
        f"silence_seconds after tool_use_start should be near 0; "
        f"got {silence}")
    snap = p.snapshot()
    assert snap.last_tool_use_ts is not None


def test_silence_seconds_tracks_latest_tool_use() -> None:
    """After multiple tool_use events, silence_seconds tracks the
    MOST RECENT one, not the first. This is what the watchdog AND
    condition needs: 'has the agent done anything tool-related
    recently?'"""
    import time as _time
    p = StreamParser()
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "tool_use"))  # tool 1
    p.feed_line(_content_block_stop(0))
    _time.sleep(0.05)
    p.feed_line(_content_block_start(1, "tool_use"))  # tool 2
    silence = p.silence_seconds(_time.monotonic())
    # Should be near 0 (resets to tool 2's timestamp), NOT 50ms.
    assert silence < 0.04


def test_silence_seconds_grows_during_thinking() -> None:
    """After a tool_use, agent enters thinking — silence grows as
    long as no new tool_use fires. This is the s219 trap pattern:
    last tool_use at T, then long thinking, silence grows linearly
    until watchdog samples it."""
    import time as _time
    p = StreamParser()
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "tool_use"))
    p.feed_line(_content_block_stop(0))
    p.feed_line(_message_stop())
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "thinking"))
    # Now in mid-thinking, no tool_use. Silence should grow.
    s1 = p.silence_seconds(_time.monotonic())
    _time.sleep(0.05)
    s2 = p.silence_seconds(_time.monotonic())
    assert s2 > s1
    assert s2 - s1 >= 0.04


# ---------------------------------------------------------------------
# Stream liveness — the second clock (2026-08-07)
# ---------------------------------------------------------------------

def test_thinking_deltas_keep_the_stream_clock_alive() -> None:
    """The two clocks must diverge on exactly the shape that burned
    seven Strategist spawns in one day: a long think with no tool call.

    Measured against the real CLI (sonnet-5 and opus-5, 2026-08-07): a
    thinking block emits a delta every ~1.5s and calls no tool for
    minutes, so tool cadence reports total silence while the stream is
    plainly alive. `content_block_delta` carries no state transition,
    which is why the parser used to drop it on the floor."""
    import time as _time
    p = StreamParser()
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "thinking"))
    _time.sleep(0.05)
    for _ in range(3):
        p.feed_line(_content_block_delta(0, "thinking_delta"))
    now = _time.monotonic()
    assert p.stream_idle_seconds(now) < 0.02   # a delta just arrived
    assert p.silence_seconds(now) >= 0.04      # no tool_use, ever
    assert p.silence_seconds(now) > 2 * p.stream_idle_seconds(now)
    assert p.snapshot().last_event_ts > p.snapshot().spawn_start_ts


def test_stream_clock_grows_when_the_stream_really_stops() -> None:
    """The guard the NL layer keeps: nothing arriving at all."""
    import time as _time
    p = StreamParser()
    p.feed_line(_message_start())
    p.feed_line(_content_block_start(0, "thinking"))
    s1 = p.stream_idle_seconds(_time.monotonic())
    _time.sleep(0.05)
    s2 = p.stream_idle_seconds(_time.monotonic())
    assert s2 - s1 >= 0.04
