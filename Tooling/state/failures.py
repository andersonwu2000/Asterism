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
    # The provider is structurally unusable: a model slug the CLI does
    # not know, refused credentials, or a tool auto-denied for want of a
    # permission rule (the Antigravity CLI reports that last one as
    # status=SUCCESS with nothing written — see antigravity_cli.py).
    # provider_infra so it never burns a goal attempt (the mathematics
    # did not fail), kind-scoped cooldown because the whole channel is
    # down rather than this one target, and NO death note: the audience
    # for a config error is the operator, not the agent.
    "provider_misconfigured": _T("provider_infra", agent_visible=False,
                                 cooldown_scope="kind"),
    # 07-30 audit: a shutdown-killed spawn produced nothing, but the old
    # 'framework' origin let it burn a goal attempt toward SHELVE — the
    # exact class the SG#14 gateway-death lesson exempts (cascade's
    # attempts skip reads PROVIDER_INFRA_REASONS only).
    "daemon_shutdown": _T("provider_infra"),
    # The OS (not the agent, not the framework) terminated the spawn:
    # NTSTATUS-shaped exit codes (0xC0000409 fail-fast, 0xC0000142 DLL
    # init, 0x40010004 debugger-terminate, ...) or the provider CLI's
    # own runtime crashing (Bun panic banner). 2026-08-08 post-mortem:
    # a dying workstation handed six such exits to `agent_rc_nonzero`,
    # which burned attempts and shoved five healthy goals into
    # strategist review — the mathematics never failed, the machine
    # did. Same traits as spawn_fast_fail: no attempts, target
    # cooldown, framework-written death note.
    "system_killed": _T("provider_infra", agent_visible=False,
                        cooldown_scope="target", death_note=True),
    # The spawn ran a while and exited non-zero for a reason nothing here
    # recognises. 2026-08-08 owner ruling — the counter answers "did the
    # worker get a FAIR CHANCE and fail?", so an unknown cause must not
    # be charged to the goal's mathematics: every death mode this project
    # has met (NTSTATUS exits, a Bun panic, a gateway 500, a pagefile
    # exhaustion) first arrived as an unrecognised rc and was silently
    # billed to the agent until someone audited it. The taxonomy can
    # never be complete, so the DEFAULT flips: unknown ⇒ don't charge,
    # but record. `provider_infra` because that is the trait bundle that
    # skips attempts (`transitions.py` reads PROVIDER_INFRA_REASONS);
    # the honest name says the origin is unknown, not proven-infra.
    # No death note: an unexplained mechanical fault teaches the agent
    # nothing, and repetition escalates to the OPERATOR, not the
    # Strategist — a framework fault is not something the Strategist can
    # act on, and asking it to will only get the fault written into the
    # Programme as mathematics (dispatcher's consecutive-unclassified
    # breaker).
    "unclassified_spawn_failure": _T("provider_infra", agent_visible=False,
                                     cooldown_scope="target"),

    # --- pipeline-level infra (clean declines / framework self-reject) --
    "strategist_noop": _T("pipeline_infra"),
    "strategist_schema_invalid": _T("pipeline_infra"),
    # Research mode: the Adversary rejected the proposal package after
    # the full revision cycle — proposal + criticisms are in
    # programme_revisions; the next wake re-derives blind. Target
    # cooldown paces back-to-back rejection cycles (each is several
    # spawns); no attempts++ (no agent-side proof failure happened).
    "strategist_proposal_rejected": _T("pipeline_infra",
                                       cooldown_scope="target"),
    "forward_no_new_goal": _T("pipeline_infra"),

    # --- structured decline directives (terminal in the retry loop) -----
    "agent_declined": _T(terminal_in_loop=True),
    "agent_infeasible": _T(terminal_in_loop=True, agent_visible=False),
    "parent_needs_fix": _T(terminal_in_loop=True, agent_visible=False),
    "agent_shelved": _T(terminal_in_loop=True, agent_visible=False),
    "agent_bailed": _T(terminal_in_loop=True),
    "same_as_disproved": _T(terminal_in_loop=True),
    "same_as_dead_unchanged": _T(terminal_in_loop=True),
    "duplicate_strategy": _T(terminal_in_loop=True),
    # NL-first (2026-07-25): goal has no Programme Proof correspondence
    # — routes to pending_strategist_review (mirror of agent_shelved;
    # the claim's justification is the Strategist's debt, not a death).
    "return_to_nl": _T(terminal_in_loop=True, agent_visible=False),

    # --- race (parallel cascade settled the target mid-run) -------------
    "goal_no_longer_open": _T("race", terminal_in_loop=True,
                              agent_visible=False),

    # --- framework shape errors (no agent involvement) ------------------
    "goal_not_found": _T("framework", agent_visible=False),
    # #125 (07-29): a queue row whose problem has no loadable Manifest.
    # Previously UNREGISTERED — the failure was invisible in the log and
    # had no cooldown, so T4 stall-wakes pumped a 1ms crashloop against
    # a post-startup `asterism init` the manifest cache hadn't seen.
    # cooldown_scope='target' rides the existing cooldown branch.
    "problem_not_found": _T("framework", agent_visible=False,
                            cooldown_scope="target"),
    "lean_file_missing": _T("framework", agent_visible=False),
    "missing_parent_stub": _T("framework", agent_visible=False),
    "parent_stub_not_decomposable": _T("framework", agent_visible=False),
    "unknown_kind": _T("framework", agent_visible=False),
    # v38 (2026-08-08): the worker THREAD died by an unhandled non-infra
    # exception. The dispatcher's exception handler writes this forensic
    # row to pair cascade_one's attempts++ (pre-v38 that increment had
    # no evidence row anywhere — the goal-7486 drift class).
    # agent_visible=False: a framework stack trace teaches the next
    # agent nothing.
    "worker_exception": _T("framework", agent_visible=False),

    # --- agent-side proof/commit failures (defaults) --------------------
    "agent_error": _T(),
    # Registered 07-30 (audit): emitted positionally via
    # buffer_failure(), which the keyword-only drift scan missed; _T()
    # codifies the default traits it was already receiving.
    "agent_stuck_thinking": _T(),
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
    # Soundness/sandbox gate (2026-07-30): the file carries an
    # elaboration-time metaprogramming entry (`elab`, `macro_rules`,
    # `#eval`, `initialize`, `set_option debug.skipKernelTC`, …). Same
    # traits as `forbidden_lemma` — the agent wrote it, so it burns an
    # attempt and comes back as retry_context with the rule attached.
    # Scanner + rationale: `state/metaprog.py`.
    "forbidden_metaprogramming": _T(),
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


#: The rc values the FRAMEWORK defines (llm/base.py SpawnRC + the
#: antigravity provider's 123). Every provider is contractually
#: required to translate its own failures into these, so reading them
#: is provider-independent. An rc OUTSIDE this set is a residue whose
#: meaning depends on the provider's `rc_contract` — see below.
_FRAMEWORK_RCS: frozenset = frozenset({0, 123, 124, 125, 126, 127, 128, 129})


def rc_to_reason(rc: int, *, rc_contract: "str | None" = None) -> str:
    """Map an `agent.spawn_llm` rc to its channel failure_reason — the
    single home of the rc taxonomy (was mirrored per-pipeline; strategist
    carried the last copy). rc values are the SpawnRC contract
    (llm/base.py): 124 timeout, 125 stale-session/fast-fail, 126 provider
    quota, 127 missing CLI, 128 stuck-thinking watchdog. 123 =
    provider config/authorization is broken (antigravity_cli).

    `rc_contract` is the seated provider's declaration
    (`llm/capabilities.py`: 'structured' / 'uninformative' /
    'undeclared'). It is passed as a plain STRING rather than a provider
    name because this module is a leaf — it imports nothing from Tooling
    so `state.transitions` and `pipeline.*` can both depend on it — and
    resolving a name into a declaration needs `core.config`.

    It changes exactly one thing: the RESIDUE (an rc outside
    `_FRAMEWORK_RCS`, e.g. a bare 1).
      * 'structured' — the residue is a provider-authored error signal;
        keep the historical `spawn_fast_fail` reading.
      * 'uninformative' / 'undeclared' — the residue carries no
        information (agy exits 1 for every ERROR envelope regardless of
        cause), so calling it a fast fail is a guess dressed as a
        diagnosis. `unclassified_spawn_failure` is the honest name; it
        has the same no-attempts / cooldown traits and its repetition
        escalates to the operator, which is who can actually fix an
        unnamed mechanical fault (2026-08-08 ruling).
    `rc_contract=None` means the CALLER has no provider in hand (a pure
    framework-vocabulary question) and keeps the historical reading —
    that is a caller saying nothing, not a provider that declared
    nothing.
    """
    if rc == 123:
        return "provider_misconfigured"
    if rc == 124:
        return "transient_timeout"
    if rc == 126:
        return "quota_exhausted"
    if rc == 127:
        return "missing_dep"
    if rc in _FRAMEWORK_RCS:
        # 125 stale-session, 128 stuck-thinking, 129 shutdown: framework
        # values with an agreed meaning — spawn-level fast fail (infra;
        # cooldown + no attempts burn).
        return "spawn_fast_fail"
    if rc_contract in ("uninformative", "undeclared"):
        return "unclassified_spawn_failure"
    return "spawn_fast_fail"
