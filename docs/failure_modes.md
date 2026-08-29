# Failure modes

> Verified against framework code at `dabf9e8f` (2026-08-30).
>
> Machine source of truth: `Tooling/state/failures.py::REGISTRY`. This document explains
> the contract and keeps every registered `failure_reason` searchable; it does not redefine
> the registry's sets. Runtime sequencing and recovery belong in [data-flow.md](data-flow.md).

## 1. The failure contract

Every completed pipeline has an `outcome`; a non-success outcome normally also has a
`failure_reason` and optional detail. `FailureTraits` gives each reason five independent traits:

| Trait | Question answered |
|---|---|
| `origin` | Did the provider, pipeline, framework, agent, a race, or a Librarian unit fail? |
| `terminal_in_loop` | Must the in-session retry loop stop immediately? |
| `agent_visible` | Is this evidence useful in the next goal context? |
| `cooldown_scope` | Should dispatch cool down this target or the whole worker kind? |
| `death_note` | Should the framework leave the mechanical death cause for the next agent? |

Consumers derive their sets from these traits. A new reason therefore requires one registry
entry, one explanation in this file, and tests for any intended change in accounting,
projection, or cooldown.

### Outcomes

`PipelineResult.outcome` has five values:

| Outcome | Meaning |
|---|---|
| `proved` | Formalizer produced a complete proof or a sorry-free minted result. |
| `success` | Formalizer committed a decomposition strategy, or another pipeline completed its unit. |
| `failed` | Work ended with a `failure_reason`; cascade behavior depends on its traits and target. |
| `exhausted` | The in-session retry budget ended. Retry failures were already recorded eagerly. |
| `moot` | A concurrent transition settled the target; no new failure or attempt is charged. |

The durable `pipelines.status` is coarser: `proved` and `success` finalize as `succeeded`;
the other terminal outcomes finalize as `failed`.

## 2. Accounting and cascade

The two ledgers answer different questions:

- `goals.attempts` is the scheduling budget: did an agent get a fair chance at this mathematics?
- `dead_attempts` is forensic evidence. A retryable goal failure is written eagerly together
  with its attempt increment; a worker or dispatcher boundary may also write a pipeline-level
  forensic row. The presence of such a row alone does not imply that a goal attempt was charged.

Provider and pipeline infrastructure reasons never charge goal attempts. Agent failures do.
Framework and race reasons follow their explicit transition paths rather than being inferred
from the English name.

### Goal-target cascade

| Result or reason | Goal effect |
|---|---|
| `proved` | Promote the goal through the verification path. |
| `success` | Keep the goal `attempting` while its live strategy/sub-goals remain. |
| `moot` | No state or attempt change. |
| retryable agent failure | The retry helper has already written evidence and incremented once. On exhaustion, send an over-threshold goal to `pending_strategist_review`; otherwise leave it dispatchable. |
| provider or pipeline infra | No goal attempt or mathematical state change; dispatcher cooldown, requeue, parking, or operator escalation handles it. |
| `agent_infeasible` | Increment once, mark `disproved`, and propagate upward. |
| `parent_needs_fix` | Increment once, mark `dead`, and propagate the fix signal upward. |
| `agent_shelved` or `return_to_nl` | Increment once and send to `pending_strategist_review`; do not propagate a mathematical falsehood. |
| `agent_declined`, `agent_bailed`, or another terminal agent failure | Increment once; threshold policy decides whether review is due. |
| `missing_parent_stub` | Increment once, shelve, and propagate because the decomposition surface vanished. |

A Formalizer mint targets a `Problem`, not a `Goal`, so it never changes goal attempts.
Infrastructure failure requeues the same Inject decision when no product was committed.
Strategist failures likewise do not touch goal attempts. Librarian uses a persistent per-file
unit fail count; `librarian_file_busy` is a wait signal and does not consume that count.

## 3. Provider and transport failures

These twelve reasons have `origin='provider_infra'`. They do not charge goal attempts.
The registry, not this table, is authoritative for cooldown and death-note traits.

| Reason | Meaning |
|---|---|
| `spawn_fast_fail` | A structured provider reports an early spawn/session failure, including framework RCs for stale session or watchdog shutdown. |
| `quota_exhausted` | Provider quota is exhausted; dispatch applies kind-scoped backoff. |
| `missing_dep` | The provider CLI or another required executable is unavailable. |
| `gateway_unreachable` | The Lean gateway transport cannot be reached. |
| `transient_timeout` | A channel-level operation timed out and is safe to retry later. |
| `verify_infra` | The gateway answered with a transient server-side failure after its own retry budget. |
| `provider_misconfigured` | Model, credentials, or headless tool permissions make the provider unusable; the whole kind is cooled down. |
| `daemon_shutdown` | An in-flight spawn ended because the daemon is shutting down. |
| `system_killed` | The OS or provider runtime killed the spawn, for example an NTSTATUS exit or runtime panic. |
| `unclassified_spawn_failure` | A nonzero exit cannot be classified honestly; it is operator evidence, not proof failure. |
| `provider_network` | Spawn stderr identifies a DNS, TLS, disconnect, or other external-network failure. |
| `local_overload` | Spawn stderr identifies local resource starvation, such as an MCP handshake timeout. |

There are two classification sites. Channel-level `rc_to_reason` maps the shared provider RC
contract; the Formalizer's in-pipeline classifier can instead use `agent_timeout` after its
salvage/rescue path. Do not infer a reason from an arbitrary numeric RC without the seated
provider's declared RC contract.

## 4. Pipeline coordination failures

These are clean declines or framework rejection of a pipeline's own product. They are
infrastructure for goal-attempt accounting, even when an LLM produced the rejected artifact.

| Reason | Meaning |
|---|---|
| `strategist_noop` | The Strategist deliberately chose Noop; this is record-keeping, not a proof error. |
| `strategist_schema_invalid` | `decision.json` or its proposal package failed mechanical/schema verification. |
| `strategist_proposal_rejected` | Adversary objections remain after the revision budget; the rejected package is preserved in `programme_revisions`. |
| `strategist_no_delta` | Repeated revision turns left `proposal.md` byte-identical, so the delta gate discarded the cycle. |
| `forward_no_new_goal` | A mint turn produced no admissible new goal/file/metadata; an infrastructure failure requeues its Inject decision. |

Adversary has no private failure vocabulary. Its provider failures use the shared registry;
missing or invalid verdict output uses `agent_no_output`.

## 5. Structured terminal decisions

These stop the in-session retry loop rather than asking the same session to try again.

| Reason | Meaning |
|---|---|
| `agent_declined` | The agent used a supported decline path without claiming infeasibility. |
| `agent_infeasible` | The agent supplied an unprovability/counterexample judgment; the goal becomes `disproved`. |
| `parent_needs_fix` | The sub-goal exposes a missing or wrong parent assumption; the parent receives the fix signal. |
| `agent_shelved` | The agent cannot make a useful attempt now; Strategist review is required. |
| `agent_bailed` | The watchdog rescue concludes further work is unlikely and preserves partial progress. |
| `same_as_disproved` | The proposal repeats a statement already disproved in this problem. |
| `same_as_dead_unchanged` | It repeats a dead twin and no newly proved fact changes the situation. |
| `duplicate_strategy` | The proposed decomposition has no novel sub-goal or link set. |
| `return_to_nl` | The claim has no justified Programme Proof correspondence; the Strategist must repair or retire the natural-language claim. |
| `goal_no_longer_open` | A parallel cascade settled the goal during the run; this race terminates the loop. |

`group_retired` is the Strategist-side race twin: a group became terminal while its wake was
still authoring, so nothing new may commit under the retired charter.

## 6. Agent proof and commit failures

Unless a row above overrides the behavior, these are agent-visible, retryable, and consume one
goal attempt when the helper records them.

| Reason | Gate or condition |
|---|---|
| `agent_error` | A generic agent-side failure, currently used by Librarian integration paths. |
| `agent_stuck_thinking` | Watchdog takeover and recovery still yielded no terminal artifact. |
| `agent_no_annotation` | A required leading rationale annotation is absent. |
| `agent_no_output` | The expected patch, decision, verdict, or unit output was not written. |
| `agent_timeout` | Formalizer's overall spawn wall expired; salvage/rescue did not yield a terminal result. |
| `axiom_violation` | The result uses axioms outside the problem whitelist or introduces an illicit axiom. |
| `batch_reference_cycle` | New sub-goal modules reference each other cyclically, so no import order exists. |
| `circular_decomposition` | A sub-goal textually restates a strict ancestor. |
| `cite_unproved_sibling` | A patch cites a sibling whose proof is not established. |
| `forbidden_lemma` | The patch uses a lemma forbidden by problem policy. |
| `forbidden_metaprogramming` | The patch contains banned elaboration-time metaprogramming or unsafe escape hatches (scanner: `Tooling/state/metaprog.py`). |
| `lake_build_error` | The candidate patch or assembled decomposition does not build. |
| `naming_violation` | A proposed declaration/slug cannot pass the naming policy or be normalized safely. |
| `no_progress` | The name/cycle gate finds a definitionally equivalent self/ancestor obligation. |
| `parse_proposal_fail` | The Formalizer output is missing or cannot be interpreted as a proof or decomposition. |
| `patch_body_contains_sorry` | A purported completed leaf still contains `sorry`. |
| `patch_signature_mismatch` | The patch changes the locked theorem signature. |
| `stale_validation` | File bytes differ from the bytes recorded by the last successful `validate_file`. |
| `subgoal_slug_collision` | A generated Lean path is owned by another goal and cannot be placed safely. |

`agent_rc_nonzero` is retained only to interpret historical rows. Unknown current provider exits
default to `unclassified_spawn_failure` when their contract supplies no trustworthy meaning.

## 7. Framework shape errors

These indicate invalid durable state, a missing file/target, or a framework exception. They are
not lessons for the next proving agent and therefore are not projected into its direct history.

| Reason | Meaning |
|---|---|
| `framework_verify_error` | The gateway returned a non-transient 4xx/malformed request-style error; retrying the same request cannot fix it. |
| `goal_not_found` | A dispatched goal row no longer exists. |
| `problem_not_found` | A queued target refers to a missing problem; target cooldown prevents a tight crash loop. |
| `lean_file_missing` | The expected Lean surface is absent. |
| `missing_parent_stub` | A decomposition cannot read its parent stub. |
| `parent_stub_not_decomposable` | The parent stub has no extractable locked signature. |
| `unknown_kind` | Dispatch received an unsupported task kind. |
| `worker_exception` | A worker thread raised an uncaught non-infrastructure exception; the dispatcher preserves forensic evidence. |

## 8. Librarian unit failures

Librarian targets a `(problem, file)` unit. Its chain scheduler persists consecutive failure
counts and stalls a unit after the configured cap; ordinary goal attempts and goal history are
unaffected.

| Stage | Reasons |
|---|---|
| migrate | `librarian_migrate_not_mechanical`, `librarian_migrate_hole_unfilled`, `librarian_migrate_build_failed` |
| classify/dispatch | `librarian_not_classified`, `librarian_schema_invalid`, `librarian_bad_work_kind`, `librarian_missing_prompt` |
| cleanup/gates | `librarian_cleaned_build_failed`, `librarian_warnings_remain`, `librarian_verify_failed`, `librarian_gate_failed`, `librarian_axiom_violation` |
| bridge/root | `librarian_bridge_not_mechanical`, `librarian_no_root` |
| ownership/integrity | `librarian_file_busy`, `librarian_file_owned_by_other`, `librarian_integrity_error`, `librarian_needs_upstream_unresolvable`, `librarian_reopened_upstream` |

`librarian_file_busy` means another worker currently owns the file, so it waits without consuming
the unit retry count. Shared `agent_error`, `agent_no_output`, and `agent_declined` may also occur.

## 9. Historical-only vocabulary

The runtime no longer dispatches Scholar. `scholar_no_query` and `paper_unfetchable` remain in
the registry so historical rows are interpretable; paper search/fetch is now a Strategist tool.
Old `Builder`, `Backward`, `Forward`, `Verify`, and `Scholar` pipeline rows likewise remain valid
historical data even though current dispatch uses Formalizer, Strategist, and Librarian.

## 10. Event projection

`Tooling/state/events.py` turns actionable durable evidence into goal context:

| Event | Source and audience |
|---|---|
| `direct_attempt` | Agent-visible Goal-target `dead_attempts`, injected into that goal. |
| `verify_failure` | Historical Strategy-target rows from before Verify collapsed into housekeeping. |
| `dead_strategy` | A dead strategy with a proposal and linked sub-goals, injected into its parent goal. |
| `infeasible_sub` | `agent_infeasible`, `parent_needs_fix`, or `agent_shelved` on a sub-goal, projected to the parent instead of repeated on the child. |

`agent_visible=False` reasons remain operator forensics and are excluded from `direct_attempt`.
`return_to_nl` reaches the Strategist through review context, not goal history. Projection is
derived from registry traits; do not maintain a second handwritten exclusion list.

## 11. Maintenance checklist

When adding or changing a failure:

1. Add or edit exactly one entry in `REGISTRY` and let derived sets follow from traits.
2. Document the trigger and audience here using the exact reason string.
3. Verify whether the retry helper or terminal cascade owns the attempt increment—never both.
4. Test cooldown, event projection, and target-specific cascade where the traits change behavior.
5. If the path adds a new multi-commit recovery window, document its reconciler in
   [data-flow.md](data-flow.md#11-failure-interruption-and-recovery).

Primary implementation map: `Tooling/state/failures.py`, `Tooling/pipeline/_retry.py`,
`Tooling/state/transitions.py`, `Tooling/state/events.py`, and
`Tooling/core/librarian_sched.py`.
