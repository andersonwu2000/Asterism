"""UTC-stamped stderr for the gateway.

gateway.log carried no timestamps: the 2026-08-30 post-mortems (the
flagship's 12:23Z/12:45Z backend restarts, the local shed/rewarm churn)
had to be dated from `ps lstart` and could not be windowed at all.
`main()` wraps `sys.stderr` in `Timestamped`; every `print(...,
file=sys.stderr)` in the package then lands stamped.
"""
from __future__ import annotations

import datetime as _dt


class Timestamped:
    """A text stream whose every line starts with `YYYY-MM-DDTHH:MM:SSZ `.
    Partial writes are stamped once, at the start of the line."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self._at_line_start = True

    def write(self, s: str) -> int:
        if not s:
            return 0
        stamp = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ ")
        out: list[str] = []
        for piece in s.splitlines(keepends=True):
            if self._at_line_start:
                out.append(stamp)
            out.append(piece)
            self._at_line_start = piece.endswith(("\n", "\r"))
        return self._inner.write("".join(out))

    def flush(self) -> None:
        self._inner.flush()

    def __getattr__(self, name: str):
        return getattr(self._inner, name)
