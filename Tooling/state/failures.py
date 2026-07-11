"""Failure-reason registry — ONE table for the taxonomy every layer consumes
(arch-review task #5).

The failure MODEL was always consistent (who failed / what the retry loop
does / does it burn goal budget / does the agent see it), but its
REPRESENTATION lived in six partially-overlapping literal sets:
`_retry._TERMINAL_DECLINE_REASONS`, `_infra.PROVIDER/PIPELINE_INFRA_REASONS`,
a byte-identical private copy in backward.py, `events._NON_AGENT_REASONS`,
the dispatcher cooldown tuple, `_maybe_reflect`'s death-note tuple, and a
second `_INFRA_REASONS` in transitions.cascade_one. Adding a reason meant
remembering four-to-six edit points with nothing mechanical catching a miss
— the same disease CONFIG_SPEC cured for config keys and EVENTS cured for
transition labels.

Every consumer now derives its set from the traits here; the historical
sets survive as re-exports (same names, same members — pinned by
tests/test_failure_registry.py against literal snapshots). Adding a reason
= one entry here (+ its failure_modes.md row, which test_doc_sot_drift
already enforces).

This module is a LEAF (imports nothing from Tooling) so `state.transitions`
and `pipeline.*` can both import it without cycles.

Trait semantics
---------------
origin           'provider_infra' — provider/transport/spawn never produced
                 agent output (no attempts++, channel cooldown; backward
                 DELETEs the placeholder strategy row);
                 'pipeline_infra' — framework rejected its own output or the
                 agent declined a decision (same no-attempts semantics);
                 'race' — a parallel cascade terminated the target mid-run;
                 'framework' — target/file shape error before any agent ran;
                 'agent' — the agent did real work that failed (forensic
                 rows kept, attempts burned);
                 'librarian' — librarian chain unit failures (fail-count
                 capped by the chain scheduler, not goal attempts).
terminal_in_loop the in-pipeline retry helper exits its loop instead of
                 re-spawning (structured decline / race moot).
agent_visible    events.py projects the dead_attempt into the goal's own
                 Context.md history (False = forensic-only, or
                 cross-projected to the parent as infeasible_subs).
cooldown_scope   dispatcher cooldown on failure: 'target' = per-(target,
                 kind) SPAWN_COOLDOWN_SEC; 'kind' = per-kind exponential
                 quota backoff + queue flush; None = no channel cooldown.
death_note       the framework writes the death cause as agent feedback
                 (spawn-level deaths have no resumable session to
                 self-report).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureTraits:
    origin: str = "agent"
    terminal_in_loop: bool = False
    agent_visible: bool = True
    cooldown_scope: "str | None" = None
    death_note: bool = False


_T = FailureTraits

REGISTRY: "dict[str, FailureTraits]" = {
    # --- provider / transport / spawn (agent never produced output) -----
    "spawn_fast_fail": _T("provider_infra", agent_visible=False,
                          cooldown_scope="target", death_note=True),
    "quota_exhausted": _T("provider_infra", cooldown_scope="kind",
                          death_note=True),
    "missing_dep": _T("provider_infra", cooldown_scope="target",
                      death_note=True),
    "gateway_unreachable": _T("provider_infra", cooldown_scope="target"),
    "transient_timeout": _T("provider_infra", cooldown_scope="target"),

    # --- pipeline-level infra (clean declines / framework self-reject) --
    "strategist_noop": _T("pipeline_infra"),
    "strategist_schema_invalid": _T("pipeline_infra"),
    "forward_no_new_goal": _T("pipeline_infra"),

    # --- structured decline directives (terminal in the retry loop) -----
    "agent_declined": _T(terminal_in_loop=True),
    "agent_infeasible": _T(terminal_in_loop=True, agent_visible=False),
    "parent_needs_fix": _T(terminal_in_loop=True, agent_visible=False),
    "agent_shelved": _T(terminal_in_loop=True, agent_visible=False),
    "agent_bailed": _T(terminal_in_loop=True),
    "same_as_disproved": _T(terminal_in_loop=True),
    "same_as_dead_unchanged": _T(terminal_in_loop=True),

    # --- race (parallel cascade settled the target mid-run) -------------
    "goal_no_longer_open": _T("race", terminal_in_loop=True,
                              agent_visible=False),

    # --- framework shape errors (no agent involvement) ------------------
    "goal_not_found": _T("framework", agent_visible=False),
    "lean_file_missing": _T("framework", agent_visible=False),
    "missing_parent_stub": _T("framework", agent_visible=False),
    "parent_stub_not_decomposable": _T("framework", agent_visible=False),
    "unknown_kind": _T("framework", agent_visible=False),
    "daemon_shutdown": _T("framework"),

    # --- agent-side proof/commit failures (defaults) --------------------
    "agent_error": _T(),
    "agent_no_annotation": _T(),
    "agent_no_output": _T(),
    # Emitted via _spawn_failure()'s RETURN VALUE (pipeline/__init__.py),
    # not a failure_reason= literal — the registry drift test's AST scan
    # cannot see that path, so these two were silently missing
    # (2026-07-06 doc audit). Default traits ARE their historical
    # behavior: agent-visible, retryable, no cooldown.
    "agent_timeout": _T(),
    "agent_rc_nonzero": _T(),
    "axiom_violation": _T(),
    # Batch stubs referencing each other in a cycle — no module import
    # order exists (task #84 intra-batch import injection, 2026-07-10).
    "batch_reference_cycle": _T(),
    "circular_decomposition": _T(),
    "cite_unproved_sibling": _T(),
    "forbidden_lemma": _T(),
    "lake_build_error": _T(),
    "naming_violation": _T(),
    "no_progress": _T(),
    "parse_proposal_fail": _T(),
    "patch_body_contains_sorry": _T(),
    "patch_signature_mismatch": _T(),
    "subgoal_slug_collision": _T(),

    # --- librarian chain units (fail-count capped, not goal attempts) ---
    "librarian_axiom_violation": _T("librarian"),
    "librarian_bad_work_kind": _T("librarian"),
    "librarian_bridge_not_mechanical": _T("librarian"),
    "librarian_cleaned_build_failed": _T("librarian"),
    "librarian_file_busy": _T("librarian"),
    "librarian_file_owned_by_other": _T("librarian"),
    "librarian_gate_failed": _T("librarian"),
    "librarian_integrity_error": _T("librarian"),
    "librarian_migrate_build_failed": _T("librarian"),
    "librarian_migrate_hole_unfilled": _T("librarian"),
    "librarian_migrate_not_mechanical": _T("librarian"),
    "librarian_missing_prompt": _T("librarian"),
    "librarian_needs_upstream_unresolvable": _T("librarian"),
    "librarian_no_root": _T("librarian"),
    "librarian_not_classified": _T("librarian"),
    "librarian_reopened_upstream": _T("librarian"),
    "librarian_schema_invalid": _T("librarian"),
    "librarian_verify_failed": _T("librarian"),
    "librarian_warnings_remain": _T("librarian"),

    # --- scholar (paper v2, D11) ---
    "scholar_no_query": _T(),
    "paper_unfetchable": _T(),
}


def _by(pred) -> frozenset:
    return frozenset(r for r, t in REGISTRY.items() if pred(t))


# ---------------------------------------------------------------------
# Derived views — the historical sets, now computed. Consumers import
# these (directly or via their historical re-export homes); the literal
# snapshots live in tests/test_failure_registry.py so any trait edit
# that would silently change a consumer's behavior trips CI.
# ---------------------------------------------------------------------

PROVIDER_INFRA_REASONS: frozenset = _by(lambda t: t.origin == "provider_infra")
PIPELINE_INFRA_REASONS: frozenset = _by(lambda t: t.origin == "pipeline_infra")
INFRA_REASONS: frozenset = PROVIDER_INFRA_REASONS | PIPELINE_INFRA_REASONS
TERMINAL_DECLINE_REASONS: frozenset = _by(lambda t: t.terminal_in_loop)
NON_AGENT_REASONS: frozenset = _by(lambda t: not t.agent_visible)
TARGET_COOLDOWN_REASONS: frozenset = _by(
    lambda t: t.cooldown_scope == "target")
DEATH_NOTE_REASONS: frozenset = _by(lambda t: t.death_note)


def is_infra(failure_reason: str) -> bool:
    """True iff `failure_reason` is an infrastructure failure (no
    attempts increment, channel-level cooldown applies)."""
    return failure_reason in INFRA_REASONS


def rc_to_reason(rc: int) -> str:
    """Map an `agent.spawn_llm` rc to its channel failure_reason — the
    single home of the rc taxonomy (was mirrored per-pipeline; strategist
    carried the last copy). rc values are the SpawnRC contract
    (llm/base.py): 124 timeout, 125 stale-session/fast-fail, 126 provider
    quota, 127 missing CLI, 128 stuck-thinking watchdog."""
    if rc == 124:
        return "transient_timeout"
    if rc == 126:
        return "quota_exhausted"
    if rc == 127:
        return "missing_dep"
    # 125 stale-session, 128 stuck-thinking, anything unknown: treat as a
    # spawn-level fast fail (infra; cooldown + no attempts burn).
    return "spawn_fast_fail"
