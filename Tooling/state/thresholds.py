"""Live dispatch thresholds — a LEAF home (arch-review task #10(d)).

BUILDER_THRESHOLD / SHELVE_THRESHOLD used to live as `core.dispatcher`
module globals mutated inside `run()` — which forced ten modules across
state / pipeline / quality to lazy-import core.dispatcher UPWARD just to
read two ints, creating the repo's only dependency cycle (state →
core → pipeline → state, survivable only via function-local imports).
This module imports nothing from Tooling, so every layer reads it
directly; the dispatcher (the sole writer) resolves config in `run()`
and calls `set_thresholds`.

Semantics (unchanged):
  BUILDER_THRESHOLD = N → first N attempts (0..N-1) dispatch Builder,
                          attempts >= N dispatch Backward.
  SHELVE_THRESHOLD  = M → goal shelves once attempts hits M.

Read the LIVE value at call time (`thresholds.SHELVE_THRESHOLD`), never
bind it at import (`from .thresholds import SHELVE_THRESHOLD` freezes
the pre-run() default). Tests tune via
`monkeypatch.setattr(thresholds, "SHELVE_THRESHOLD", n)`.
`core.dispatcher` keeps read-only aliases via module `__getattr__` for
historical call sites and operator muscle memory.
"""
from __future__ import annotations

BUILDER_THRESHOLD: int = 3
SHELVE_THRESHOLD: int = 8


def set_thresholds(*, builder: int, shelve: int) -> None:
    """Sole sanctioned writer — called once by `dispatcher.run()` after
    config resolution (env → yaml → default)."""
    global BUILDER_THRESHOLD, SHELVE_THRESHOLD
    BUILDER_THRESHOLD = int(builder)
    SHELVE_THRESHOLD = int(shelve)
