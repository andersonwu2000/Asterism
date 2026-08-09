"""Real-time parser for `claude --output-format stream-json
--include-partial-messages` stdout.

Each stdout line is one JSON object. The interesting lines have
`type == "stream_event"` and wrap the underlying Anthropic streaming
SSE event in the `event` field. The parser maintains a thread-safe
state machine so a watchdog can ask "what is the agent doing right
now?" without polling the on-disk session jsonl (which only gets
written on message-completion and therefore has no mid-stream
visibility).

State machine (per active assistant message):
  idle        — no active message (between turns or before first turn)
  in_message  — message_start received, no active content block
  mid-thinking — content_block_start with type=thinking active
  mid-tool    — content_block_start with type=tool_use active
  mid-text    — content_block_start with type=text active
  finalized   — message_stop received; last_stop_reason recorded

On a fresh `message_start`, state resets to in_message and
last_stop_reason resets to None (a new turn invalidates the prior
stop_reason for trap-detection purposes — we care about whether the
agent is currently stuck, not whether it was stuck N turns ago).

The parser is intentionally tolerant of the upstream format:
  * Lines that aren't JSON or don't have `type` are silently ignored.
  * Lines with `type != "stream_event"` (system init, rate_limit,
    full assistant message, result) are skipped — only delta-level
    events drive state.
  * Unknown event types within stream_event are skipped without
    state change.

Why we don't consume the `assistant` message-completion lines:
  Those duplicate the per-block stream events (message_start +
  content_block_start/delta/stop + message_delta + message_stop)
  and arrive AFTER the message is finished. The watchdog needs
  in-flight visibility, which only the stream events provide.
"""
from __future__ import annotations

import json
import threading
import time
from enum import Enum
from typing import NamedTuple


class ParserState(Enum):
    IDLE = "idle"
    IN_MESSAGE = "in_message"
    MID_THINKING = "mid-thinking"
    MID_TOOL = "mid-tool"
    MID_TEXT = "mid-text"
    FINALIZED = "finalized"


class StateSnapshot(NamedTuple):
    """Read-only snapshot of parser state at a point in time.

    `state_since`: monotonic time when current `state` was entered.
        Lets the consumer compute how long the agent has been in this
        state without taking the lock again.
    `last_stop_reason`: the most recently observed `message_delta`
        stop_reason (e.g. "end_turn", "tool_use", "max_tokens",
        "stop_sequence"). Reset to None when a fresh `message_start`
        arrives.
    `messages_seen`: count of `message_stop` events. Used for diagnostic
        / forensic detail; not part of trap-detection itself.
    `last_tool_use_ts`: monotonic time of the most recent
        `content_block_start type=tool_use` event, or None if no
        tool_use has been seen yet. Used by `silence_seconds` to
        compute how long the agent has been silent.
    `spawn_start_ts`: parser creation time (≈ spawn start). Used as
        the fallback baseline for `silence_seconds` when no tool_use
        has happened yet.
    `last_event_ts`: monotonic time of the most recent stream event of
        ANY type — the liveness clock behind `stream_idle_seconds`.
    """
    state: ParserState
    state_since: float
    last_stop_reason: str | None
    messages_seen: int
    last_tool_use_ts: float | None
    spawn_start_ts: float
    last_event_ts: float


class StreamParser:
    """Thread-safe state machine consuming claude CLI stream-json
    `stream_event` lines. One instance per spawn. `feed_line` is
    called from the reader thread; `snapshot` is called from the
    watchdog (or the post-spawn TIMEOUT branch) on a different thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        now = time.monotonic()
        self._state = ParserState.IDLE
        self._state_since = now
        self._last_stop_reason: str | None = None
        self._messages_seen = 0
        # Silence tracking: watchdog uses these to compute how long
        # the agent has been silent (no tool_use). silence_seconds()
        # returns now - last_tool_use_ts, falling back to
        # now - spawn_start_ts when no tool_use has been seen.
        self._last_tool_use_ts: float | None = None
        self._spawn_start_ts = now
        # Liveness tracking, the second clock: time of the last stream
        # event of any type, INCLUDING `content_block_delta`. Measured
        # 2026-08-07 on both sonnet-5 and opus-5: an agent four minutes
        # deep in one thinking block emits a delta every ~1.5s (max gap
        # 3.5s) and calls no tool at all — so the tool-cadence clock
        # above reads it as totally silent while this one shows it
        # plainly alive. Which clock is the right one depends on what
        # the role's work looks like; the watchdog picks per kind.
        self._last_event_ts = now
        # Token accounting (task #7): the CLI stream carries the API's
        # usage numbers on every turn — message_start has the input side
        # (fresh + cache split), message_delta carries the cumulative
        # output count for the turn (last one before message_stop is
        # final). Summed per spawn; surfaced via usage() and persisted by
        # the spawn wrapper. Until now the parser read these events and
        # nobody kept the books — the system had wall-clock and attempts
        # as its only cost proxies.
        self._usage = {"input_tokens": 0, "output_tokens": 0,
                       "cache_read_input_tokens": 0,
                       "cache_creation_input_tokens": 0, "turns": 0}
        self._turn_output = 0

    def _set_state(self, new_state: ParserState) -> None:
        # Caller already holds _lock.
        if new_state == self._state:
            return
        self._state = new_state
        self._state_since = time.monotonic()

    def feed_line(self, line: str) -> None:
        """Parse one stdout line. No-op on malformed or non-stream
        lines."""
        line = line.strip()
        if not line:
            return
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(obj, dict):
            return
        if obj.get("type") != "stream_event":
            return
        event = obj.get("event")
        if not isinstance(event, dict):
            return
        etype = event.get("type")
        with self._lock:
            # Every well-formed stream event is evidence the process is
            # still producing — stamped before the state branches so the
            # types that carry no transition (content_block_delta, the
            # bulk of a thinking block) still count.
            self._last_event_ts = time.monotonic()
            if etype == "message_start":
                # New assistant turn begins. Reset stop_reason — prior
                # max_tokens (if any) is from a prior turn and no
                # longer indicates current trap risk.
                self._last_stop_reason = None
                self._set_state(ParserState.IN_MESSAGE)
                u = ((event.get("message") or {}).get("usage") or {})
                for k in ("input_tokens", "cache_read_input_tokens",
                          "cache_creation_input_tokens"):
                    v = u.get(k)
                    if isinstance(v, int):
                        self._usage[k] += v
                self._turn_output = 0
            elif etype == "content_block_start":
                cb = event.get("content_block") or {}
                cb_type = cb.get("type")
                if cb_type == "thinking":
                    self._set_state(ParserState.MID_THINKING)
                elif cb_type == "tool_use":
                    self._set_state(ParserState.MID_TOOL)
                    # Stamp tool_use start time for silence tracking.
                    # Watchdog asks "how long since last tool_use?"
                    # — long silence + thinking-trap state is the
                    # AND condition that triggers fresh-sid takeover.
                    self._last_tool_use_ts = time.monotonic()
                elif cb_type == "text":
                    self._set_state(ParserState.MID_TEXT)
                # Unknown content block types are ignored — no
                # state transition. Future Anthropic types (e.g.
                # web_search_tool_result) won't crash the parser.
            elif etype == "content_block_stop":
                # Block ended; back to message-level (waiting for next
                # block or message_stop). Don't go all the way back to
                # IDLE — we're still inside the message envelope.
                if self._state in (
                    ParserState.MID_THINKING,
                    ParserState.MID_TOOL,
                    ParserState.MID_TEXT,
                ):
                    self._set_state(ParserState.IN_MESSAGE)
            elif etype == "message_delta":
                # Carries final stop_reason. Record it for trap
                # detection (max_tokens is the smoking gun).
                delta = event.get("delta") or {}
                sr = delta.get("stop_reason")
                if isinstance(sr, str):
                    self._last_stop_reason = sr
                v = (event.get("usage") or {}).get("output_tokens")
                if isinstance(v, int):
                    self._turn_output = v     # cumulative within the turn
            elif etype == "message_stop":
                self._messages_seen += 1
                self._usage["output_tokens"] += self._turn_output
                self._usage["turns"] += 1
                self._turn_output = 0
                self._set_state(ParserState.FINALIZED)
            # Other event types (e.g. content_block_delta) don't change
            # state — they confirm activity but don't transition.

    def usage(self) -> "dict[str, int]":
        """Per-spawn token totals accumulated so far (task #7). An
        in-flight turn's output is included so a TIMEOUT kill still
        reports what was spent."""
        with self._lock:
            u = dict(self._usage)
            u["output_tokens"] += self._turn_output
            return u

    def snapshot(self) -> StateSnapshot:
        """Return the current state without blocking the parser."""
        with self._lock:
            return StateSnapshot(
                state=self._state,
                state_since=self._state_since,
                last_stop_reason=self._last_stop_reason,
                messages_seen=self._messages_seen,
                last_tool_use_ts=self._last_tool_use_ts,
                spawn_start_ts=self._spawn_start_ts,
                last_event_ts=self._last_event_ts,
            )

    def silence_seconds(self, now: float) -> float:
        """Seconds since the agent last emitted a tool_use_start event.
        Falls back to seconds since parser creation when no tool_use
        has been seen yet (cold spawn that never reached tool phase).
        Used by the watchdog as one half of the AND trap condition —
        long silence by itself isn't enough (a slow Bash / lake
        build would trip it), but combined with parser thinking-trap
        state it is strong evidence of a stuck agent.

        This is the TOOL-CADENCE clock, and it answers "is the agent
        thinking instead of acting?" — the right question for a
        formalizer, whose unit of work is a tool call. It is the wrong
        question for a role whose work is one long think; see
        `stream_idle_seconds`."""
        with self._lock:
            baseline = (self._last_tool_use_ts
                        if self._last_tool_use_ts is not None
                        else self._spawn_start_ts)
            return now - baseline

    def stream_idle_seconds(self, now: float) -> float:
        """Seconds since ANY stream event arrived — the liveness clock.

        Answers "has this process stopped producing?" rather than "is it
        acting?". For the NL layer (Strategist / Adversary) that is the
        only guard that makes sense: those roles have no work budget by
        design, so thinking without calling a tool is the job, not a
        symptom, and the tool-cadence clock read seven legitimate
        Strategist spawns as silent and killed them (2026-08-07)."""
        with self._lock:
            return now - self._last_event_ts

    # ---- Trap detection helpers ----

    def is_thinking_trap(self) -> bool:
        """Return True iff the current parser state suggests the agent
        is stuck in thinking and only a fresh sid can recover.

        Two manifestations of the same trap class:
          (a) currently in mid-thinking — agent's stream is still
              emitting thinking deltas, no tool_use_start in sight.
              SIGKILL + --resume re-enters the same thinking context
              (production evidence: SG run #9 cb7e1cde session, 7
              minutes of mid-thinking before max_tokens).
          (b) finalized + last_stop_reason == max_tokens — agent
              completed a thinking-only message that maxed out the
              thinking budget. claude CLI's auto-continue may or may
              not recover; production evidence shows it often doesn't
              (s219 case 2: 38s silence after max_tokens until
              subprocess kill).

        Either condition is a true positive for trap. False positives
        are mitigated downstream by the fresh-sid stage 2 prompt that
        lets the agent inspect the broken jsonl and decide ship-or-bail.
        """
        snap = self.snapshot()
        if snap.state == ParserState.MID_THINKING:
            return True
        if (snap.state == ParserState.FINALIZED
                and snap.last_stop_reason == "max_tokens"):
            return True
        return False
