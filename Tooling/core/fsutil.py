"""Windows-tolerant helpers for the `.asterism` status files.

The daemon lifecycle files (daemon-exit.txt, daemon.stop,
daemon-starting.txt) are read by the serve API's status poll every ~2s
with plain `read_text`. Python opens files WITHOUT FILE_SHARE_DELETE on
Windows, so a bare `unlink(missing_ok=True)` that collides with such a
read raises PermissionError (WinError 32). That exact collision killed
the 2026-07-13 21:01 drift-handoff waiter tracelessly (caught on
2026-07-14 by handoff-waiter.log): `daemon start` crashed clearing the
previous run's exit summary, so no successor ever booted.

These files are advisory — failing to delete one must never be fatal.
"""
from __future__ import annotations

import time
from pathlib import Path


def unlink_tolerant(path: Path, *, retries: int = 3,
                    delay_sec: float = 0.2) -> bool:
    """`unlink(missing_ok=True)` that survives a concurrent reader.
    Retries around the (milliseconds-wide) read window, then gives up
    quietly — a stale status file is recoverable, a crashed daemon
    starter is not. Returns False when the file could not be removed."""
    for attempt in range(retries):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            if attempt + 1 < retries:
                time.sleep(delay_sec)
    return False
