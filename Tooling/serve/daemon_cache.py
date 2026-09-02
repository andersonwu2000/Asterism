"""One reading of the engine's status, shared by every poller.

`core.cli.daemon_status()` is a snapshot of one instant: pid file,
scope file, code fingerprint, one read-only DB open, the gateway's
presence. It rides EIGHT endpoints (`/api/daemon`, `/api/meta`,
`/api/problems`, `/api/problems/{p}`, `/api/run`, `/api/run/events`,
`/api/telemetry/usage`, `/api/shutdown/preview`) and the console polls
several of them at once, so a single screen asked for the same instant
five times a second — each ask paying the same file and DB work.

The CLI keeps calling `daemon_status` directly: `asterism daemon
status` is a fresh process asking once, and a memo there would be a
memo of nothing. This module is the SERVE-side reading, and it is the
only one that needs a TTL.

Two rules make the staleness honest:

  - the window is short (`_TTL`), so nothing here can be more than a
    poll interval behind what the pollers would have read anyway;
  - a write that CHANGES the status clears it (`invalidate`). Start,
    stop and quit are those writes — a Run button that lied for two
    seconds after the click would be worse than the cost it saved.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

#: How long one reading stands. Shorter than the console's fastest
#: poll (2s), so a caller never waits on a value it could have had.
_TTL = 2.0

_lock = threading.Lock()
_memo: "dict[str, tuple[float, dict]]" = {}


def invalidate(workspace: "Path | str | None" = None) -> None:
    """Drop the cached reading — for one workspace, or all of them."""
    with _lock:
        if workspace is None:
            _memo.clear()
        else:
            _memo.pop(str(workspace), None)


def daemon_status(workspace: Path) -> dict:
    """The engine's status, computed at most once per `_TTL`.

    The lock is held ACROSS the computation on purpose: N concurrent
    pollers arriving on a cold memo must cost one reading, not N. The
    work behind it is local file and sqlite reads plus (only when a
    gateway says it is there) one loopback round-trip — bounded, and
    the alternative is the stampede this module exists to stop.
    """
    key = str(workspace)
    now = time.monotonic()
    with _lock:
        hit = _memo.get(key)
        if hit is not None and now - hit[0] < _TTL:
            return hit[1]
        # imported per call so a test's monkeypatch of the CLI symbol
        # is the thing this reads — the same contract the endpoints had
        # when each of them imported it for itself
        from ..core.cli import daemon_status as _read
        value = _read(workspace)
        _memo[key] = (time.monotonic(), value)
        return value
