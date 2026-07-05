"""Infrastructure-failure classification — re-export home.

The taxonomy itself moved to `state/failures.py` (the one registry every
layer derives its failure sets from; arch-review task #5 — this module was
created to centralise INFRA_REASONS but a byte-identical private copy in
backward.py survived it, proving re-export homes don't dedupe by
themselves; the registry's drift tests do). Importers keep their
historical names:

  - Tooling/core/dispatcher.py            (cascade_one branch)
  - Tooling/pipeline/backward.py          (strategy infra-failure delete)
  - Tooling/pipeline/strategist.py        (Phase 2)
  - Tooling/pipeline/forward.py           (Phase 2)
"""
from __future__ import annotations

from ..state.failures import (  # noqa: F401
    INFRA_REASONS,
    PIPELINE_INFRA_REASONS,
    PROVIDER_INFRA_REASONS,
    is_infra,
)
