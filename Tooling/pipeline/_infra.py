"""Phase 2 — shared infrastructure-failure classification.

Centralises the `INFRA_REASONS` set previously duplicated in
`dispatcher.cascade_one` and `backward._run_backward_strategy_step`.
A failure_reason in this set is "agent didn't actually do work" —
provider quota, missing CLI, gateway transport, etc. Such failures
must NOT burn the target's attempts counter; the dispatcher applies a
per-(target,kind) or per-kind cooldown instead.

Phase 2 additions:
  - `strategist_noop`            — Strategist's Noop decision (clean exit)
  - `strategist_schema_invalid`  — self_verify rejected the decision JSON
  - `forward_no_new_goal`        — Forward declined / dedupe blocked

Importers:
  - Tooling/core/dispatcher.py            (cascade_one branch)
  - Tooling/pipeline/backward.py          (strategy infra-failure delete)
  - Tooling/pipeline/strategist.py        (Phase 2)
  - Tooling/pipeline/forward.py           (Phase 2)
"""
from __future__ import annotations


# Provider / transport / spawn-side failures. Pipeline never reached
# the LLM, or the LLM never responded — no useful agent output to
# learn from. Dispatcher cools the channel; attempts unchanged.
PROVIDER_INFRA_REASONS: frozenset[str] = frozenset({
    "spawn_fast_fail",      # rc != 0, wall < 10s (claude.exe crash)
    "quota_exhausted",      # rc = 126 (provider rate limit)
    "missing_dep",          # rc = 127 (CLI binary missing)
    "gateway_unreachable",  # gateway HTTP transport failed
    "transient_timeout",    # network / socket level timeout
})


# Phase 2 — Strategist / Forward pipeline-level infrastructure failures.
# Failed *because the framework rejected its own output as malformed*,
# or the agent explicitly declined a productive decision. Same cooldown
# semantics as PROVIDER_INFRA_REASONS — no attempts increment, the
# next trigger (T0/T1/T2 wall-clock or pending review) re-spawns.
PIPELINE_INFRA_REASONS: frozenset[str] = frozenset({
    "strategist_noop",            # Strategist Noop decision (intentional)
    "strategist_schema_invalid",  # self_verify rejected agent's JSON
    "forward_no_new_goal",        # Forward agent declined / all dedupe
})


# Union for callers that want "any infra reason".
INFRA_REASONS: frozenset[str] = PROVIDER_INFRA_REASONS | PIPELINE_INFRA_REASONS


def is_infra(failure_reason: str) -> bool:
    """True iff `failure_reason` is an infrastructure failure (no
    attempts increment, channel-level cooldown applies)."""
    return failure_reason in INFRA_REASONS
