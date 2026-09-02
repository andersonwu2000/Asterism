"""Is this console process running the code that is on disk?

The stale-console banner used to compare the release `VERSION` file to
itself: `version` (read once at boot) against `disk_version` (read now).
That is the right question with the wrong evidence — a dev workspace has
no VERSION file, so both sides were null, the banner could never fire,
and a serve started before a commit went on answering with its old
endpoints under the new bundle's pages. The reader had no way to know
which of its answers were lies; the process is the only thing that
could have told them, and it was comparing nothing to nothing.

The evidence that is true in every workspace is the source tree itself.
`lsp/lifecycle.code_fingerprint` already hashes every `Tooling/**.py`
file's (relpath, mtime_ns, size) — it is the daemon's own staleness
signal (`daemon-fp.txt` → `daemon_status.code_stale`), so a console and
an engine mean the same thing by "stale code". It is mtime-based, which
makes a plain edit enough: no commit, no release, no version bump.

`loaded()` is frozen at import — the moment this process actually read
its code. `on_disk()` is memoized briefly: the walk is ~17ms over the
whole tree, and the banner is answering a question about minutes.
"""
from __future__ import annotations

import threading
import time

#: How long one tree walk stands. The console polls `/api/meta` every
#: 3s and several tabs may poll at once; a banner about a process's
#: whole lifetime does not need a fresher reading than this.
_TTL = 5.0

_lock = threading.Lock()
_disk: "tuple[float, str] | None" = None


def _fingerprint() -> str:
    from ..lsp.lifecycle import code_fingerprint
    return code_fingerprint()


#: What THIS process loaded, taken at import — the one number a stale
#: process still knows for certain about itself.
_LOADED = _fingerprint()


def reset() -> None:
    """Drop the memoized disk reading (tests; an explicit re-check)."""
    global _disk
    with _lock:
        _disk = None


def loaded() -> str:
    return _LOADED


def on_disk() -> str:
    global _disk
    now = time.monotonic()
    with _lock:
        if _disk is not None and now - _disk[0] < _TTL:
            return _disk[1]
        value = _fingerprint()
        _disk = (time.monotonic(), value)
        return value
