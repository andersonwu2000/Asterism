"""Live dispatch thresholds — a LEAF home (arch-review task #10(d)).

SHELVE_THRESHOLD used to live as a `core.dispatcher` module global
mutated inside `run()` — which forced ten modules across state /
pipeline / quality to lazy-import core.dispatcher UPWARD just to read
an int, creating the repo's only dependency cycle (state → core →
pipeline → state, survivable only via function-local imports). This
module imports nothing from Tooling, so every layer reads it directly;
the dispatcher (the sole writer) resolves config in `run()` and calls
`set_thresholds`.

Semantics:
  SHELVE_THRESHOLD  = M → goal shelves once attempts hits M.
  BUILDER_THRESHOLD — routing semantics RETIRED with the Formalizer
                      merge (update_plan_2026_07 #1: no Builder→Backward
                      escalation exists). Survives only as an internal
                      small-retry-budget constant (librarian hole-fill +
                      the undispatched legacy builder module); no config
                      key reads it anymore.

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


def set_thresholds(*, shelve: int, builder: "int | None" = None) -> None:
    """Sole sanctioned writer — called once by `dispatcher.run()` after
    config resolution (env → yaml → default). `builder` is accepted for
    back-compat callers/tests but no longer config-driven."""
    global BUILDER_THRESHOLD, SHELVE_THRESHOLD
    if builder is not None:
        BUILDER_THRESHOLD = int(builder)
    SHELVE_THRESHOLD = int(shelve)
