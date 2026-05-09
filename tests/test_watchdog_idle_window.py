"""Watchdog idle-window guard — wall_cap fires only when the agent has
been silent (no tool_use in session jsonl) for ≥ idle_window_sec.

Reintroduced 2026-05-10 after `ff94493` removed the older stuck-by-
silence trigger. The new design uses tool_use tracking as a *guard* on
the wall_cap kill (not as a separate trigger): productive agents at
wall_cap fall through to the standard subprocess-timeout + postmortem
path, while truly idle agents still get killed for rescue.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Iterable

import pytest

from Tooling.llm import claude_cli


# ---------------------------------------------------------------------
# Helpers — unit
# ---------------------------------------------------------------------

def _write_jsonl(path: Path, events: Iterable[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n",
        encoding="utf-8",
    )


def _tool_use_event(name: str = "Read") -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": "x", "name": name, "input": {}},
            ],
        },
    }


def test_count_tool_use_events_basic(tmp_path: Path) -> None:
    """One assistant message with two tool_use blocks → count = 2."""
    log = tmp_path / "s.jsonl"
    log.write_text(json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "id": "1", "name": "Read", "input": {}},
            {"type": "text", "text": "thinking"},
            {"type": "tool_use", "id": "2", "name": "Edit", "input": {}},
        ]},
    }) + "\n", encoding="utf-8")
    assert claude_cli._count_tool_use_events(log) == 2


def test_count_tool_use_events_partial_line_tolerated(tmp_path: Path) -> None:
    """Mid-write trailing line (claude streams) is silently skipped —
    the watchdog still gets a sound count from the complete lines."""
    log = tmp_path / "s.jsonl"
    log.write_text(
        json.dumps(_tool_use_event()) + "\n"
        + '{"type":"assistant","message":{"con',
        encoding="utf-8",
    )
    assert claude_cli._count_tool_use_events(log) == 1


# ---------------------------------------------------------------------
# Watchdog behavior — drives the real _watchdog with a fake Popen and
# patched session-jsonl lookup. poll_interval is tiny so tests run fast.
# ---------------------------------------------------------------------

class _FakeProc:
    """Quack-like-Popen: poll() returns None until `done` is set, then 0.
    terminate() / wait() / kill() set the done flag (mirrors what a real
    proc does on watchdog kill)."""

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


def _run_watchdog(proc, sid: str, *, timeout_sec: int,
                  poll_interval: float = 0.02,
                  monkeypatch: pytest.MonkeyPatch | None = None,
                  ) -> list[bool]:
    """Run `_watchdog` in a thread and return the stuck_flag once the
    thread exits or the test times out (whichever first). Tests pass a
    monkeypatch instance to lower the wall_cap floor for fast firing."""
    if monkeypatch is not None:
        monkeypatch.setattr(claude_cli, "_MIN_WALL_CAP_SEC", 0)
    flag: list[bool] = [False]
    th = threading.Thread(
        target=claude_cli._watchdog,
        args=(proc, sid),
        kwargs={"stuck_flag": flag, "timeout_sec": timeout_sec,
                "poll_interval": poll_interval},
        daemon=True,
    )
    th.start()
    th.join(timeout=5.0)
    return flag


def test_watchdog_idle_kills_when_silence_exceeds_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wall_cap fires AND idle_window already exceeded (jsonl has no
    tool_use ever) → kill, stuck_flag set, proc terminated."""
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    monkeypatch.setenv("ASTERISM_IDLE_WINDOW_SEC", "1")
    # jsonl exists but is empty — last_progress stays at spawn_start,
    # so by the time wall_cap fires, silence == elapsed >= idle_window.
    log = tmp_path / "abc123.jsonl"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(claude_cli, "_find_session_jsonl",
                        lambda sid: log)
    proc = _FakeProc()
    flag = _run_watchdog(proc, "abc123", timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is True
    assert proc.term_calls + proc.kill_calls >= 1


def test_watchdog_idle_defers_when_active_at_wall_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wall_cap fires but agent has emitted tool_use within the idle
    window → watchdog exits without kill (subprocess timeout + post-
    mortem will handle the eventual deadline). Sized so the test wall
    is much smaller than the idle window: any tool_use seen on the
    first poll updates last_progress to now, and by wall_cap the
    silence is well under the configured window."""
    monkeypatch.setenv("ASTERISM_RESCUE_TIMEOUT_SEC", "1")
    monkeypatch.setenv("ASTERISM_IDLE_WINDOW_SEC", "3600")
    log = tmp_path / "abc456.jsonl"
    _write_jsonl(log, [_tool_use_event(), _tool_use_event()])
    monkeypatch.setattr(claude_cli, "_find_session_jsonl",
                        lambda sid: log)
    proc = _FakeProc()
    flag = _run_watchdog(proc, "abc456", timeout_sec=2,
                         monkeypatch=monkeypatch)
    assert flag[0] is False
    assert proc.term_calls == 0
    assert proc.kill_calls == 0
