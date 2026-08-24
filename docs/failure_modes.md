# Asterism — Pipeline outcomes & failure modes

Written 2026-05-06; fully re-verified against code 2026-07-29 (Formalizer merge alignment).

Each pipeline emits one outcome at termination; non-success outcomes carry `failure_reason` for
forensic + event projection. **The machine SoT is `REGISTRY` in `Tooling/state/failures.py`**
(traits derive the infra/projection/cooldown sets; tests bind to it); this doc is its human
narrative layer — the full mapping of trigger conditions and cascade semantics lives **only
here**; do not add mapping tables in other docs. New reason = one registry entry + one line here.

> Terminology: the only remaining workers are `Formalizer` (Goal arm = prove/split, Problem
> arm = mint) / `Strategist` / `Scholar` / `Librarian`. "Builder", "Backward", "Forward" in the
> tables are the Formalizer's three historical predecessors — reason vocabulary is inherited,
> trigger sites unchanged (prove arm follows Builder, split arm Backward, mint arm Forward);
> only pre-merge queue rows still appear under the old kind names.

---

## 1. Pipeline outcomes

Outcome string when a pipeline terminates (pipeline.PipelineResult.outcome):

| outcome | applies to | meaning | cascade principle |
|---|---|---|---|
| `proved` | Formalizer | proof complete (hint-prefixed, leaf-bypass, or sorry-free mint) | goal `proved` |
| `success` | Formalizer | strategy committed (patch + sub-goals placed + build passes) | goal `attempting` |
| `failed` | Formalizer | carries `failure_reason`, see §2 (terminal decline / infra rc / goal_not_found) | varies by reason |
| `exhausted` | Formalizer | helper budget spent; the final retry's reason is reflected in `failure_reason` | (helper already ++ attempts); at SHELVE goes to strategist review, no auto-shelve; otherwise status untouched so the goal gets re-dispatched |
| `moot` | Formalizer | helper entry / mid-loop cascade re-check finds the goal already terminal | uniform no-op (no state change, no dead_attempts row, no attempts++) |

**Common cascade rules** (table columns list only reason-specific behavior):
- Default: the helper writes one dead_attempt + attempts++ **on the spot** for each failed spawn (v38: the pipelines row is INSERTed as `running` at dispatch, so the FK is satisfied from the start and there is no more buffer-then-flush — the old protocol lost forensic rows together with the stack frame when a worker thread died of an exception, while the increment had already been booked; goal 7486, 2026-08-08); at SHELVE_THRESHOLD → **transition to `pending_strategist_review` for Strategist adjudication, no more auto-shelve** (bfs_refill also intercepts over-threshold goals into review before dispatch). Real shelves come only from Strategist ConfirmShelve or individual hard-terminal branches
- The BUILDER_THRESHOLD escalation route retired with the Formalizer merge (no config key; prove/split is decided by the agent within the session)
- **Strategist Inject exception**: when a pipeline carries a `decision_id`, the budget gate and attempts cap are **fully bypassed** — once the Strategist has reviewed the failure replay and approved, the framework does not second-guess; the only remaining guard is `moot` when the goal status is already terminal
- The seven provider-infra reasons (spawn_fast_fail / quota_exhausted / missing_dep / gateway_unreachable / transient_timeout / system_killed / unclassified_spawn_failure) → no attempts++, no dead_attempt row. All except quota set a 30s target cooldown; `quota_exhausted` uses per-kind exponential backoff (30s×2ⁿ cap 600s) + flush of the same-kind queue + may transition to quota-wait. CONSEC daemon-exit: spawn_fast_fail=10 (on hitting the cap, first confirm against the usage endpoint; real quota transitions to quota-wait instead of exiting), gateway_unreachable=8, transient_timeout not counted in CONSEC
- Cascades for the four declines: agent_declined → attempts++ (entry_kind routing removed with v33); agent_infeasible → attempts++ + goal `disproved` + propagate; parent_needs_fix → attempts++ + goal `dead` + propagate; agent_shelved / no_nl_correspondence → attempts++ + transition to pending_strategist_review, no propagation
- **Upward path of soft-shelve** (`_maybe_stall_parent_strategies` → `_maybe_review_goal_out_of_routes`, 07-09 `453c0636`): after a sub-goal soft-shelves, once all sub-goals of the parent strategy are settled ⇒ the strategy goes `stalled` and the parent goal goes to T2 review (otherwise a goal that is `attempting` with no live strategy is never touched again — BFS only consumes `open`). **The aliveness criterion includes promises** (07-30, b6_1 four-level cascade): a `shelved` sub-goal counts as **alive** if the batch owning its latest ConfirmShelve still has unsettled Injects ⇒ no stall, no review, the parent simply waits — same rationale as `pending_strategist_review` counting as alive (something is scheduled to happen). Batch semantics guarantee continuity: `maybe_enqueue_inject_batch_done` schedules the wake the moment the last Inject settles, so no overdue timer is needed; unfulfilled promises are caught once by the problem-level stall criterion (`_subtree_has_live_frontier`; `attempting` itself does not count as live frontier), not once per level. Shelved goals without promises behave as before

---

## 2. Failure reasons (master table)

Since Phase 7 the retry logic lives in the in-pipeline retry helper (`Tooling/pipeline/_retry.py`).
The 1:1 invariant attempts ↔ dead_attempts: for each failed spawn the helper writes one
dead_attempt + attempts++ **on the spot** (since v38 the pipelines row exists at dispatch, so
the FK is directly satisfied; "buffer + retry" in the table reads, since v38, as "written to DB
immediately, then retried" — the old buffer-then-flush lost forensic rows on worker exception
death while the increment was already booked). For non-terminal-decline failures (lake error,
forbidden_lemma, etc.) the cascade only does the status transition and no longer does
attempts++ (already counted on the spot by the helper).

> Terminology: "verify-collapse" = folding the old Verify worker_kind into inline main-loop
> housekeeping. Pre-collapse Strategy-target `dead_attempts` rows remain in the DB as
> history; new pipelines no longer produce such rows. See `data-flow.md` §4.

| failure_reason | origin | trigger | helper handling | cascade handling | event_type projection |
|---|---|---|---|---|---|
| `lake_build_error` | Builder + Backward | Phase 2 patch / Backward strategy assembly build fails | buffer + retry next round in same session (retry_context carries stderr) | (helper already ++); exhausted → status transition | `direct_attempt` |
| `forbidden_lemma` | Builder + Backward | patch text hits the problem's `forbidden_lemmas` setting | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `forbidden_metaprogramming` | Backward + Forward | patch / sub-goal stub / mint candidate contains an elaboration-time metaprogramming entry point (`elab`/`macro_rules`/`#eval`/`initialize`/`unsafe`/`@[implemented_by]`/`set_option debug.skipKernelTC` etc.; scanner=`Tooling/state/metaprog.py`, matched after comment stripping) — elab-time code runs with **framework privileges** (sandbox escape), and `Environment.add`-style insertions neither pass the kernel nor show up in `#print axioms` | buffer + retry (retry_context carries "write plain theorem/def; soundness is carried by the kernel + axiom gate") | (helper already ++); exhausted → status transition | `direct_attempt` |
| `parse_proposal_fail` | Backward | patch.lean missing; or patch=1 new=0 + sorry body + no decline directive (after Phase 6.5 a non-sorry patch body counts as leaf-bypass, not a failure) | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `patch_signature_mismatch` | Backward | agent changed the locked `theorem sX <binders> : <type>` signature | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `stale_validation` | Backward | patch.lean's bytes at commit differ from the sha the last `validate_file()` recorded (`_validated.json`) — the agent edited after its final validation, so the green it reported is about other content (disk-authority ruling 2026-08-24; no record = no gate, the pure LSP-loop flow stays legal) | buffer + retry (the way out is one `validate_file()` call on the final state) | (helper already ++); exhausted → status transition | `direct_attempt` |
| `naming_violation` | Backward | sub-goal slug violates charset / length lint (lowercase `[a-z][a-z0-9_]*`, ≤ 60 chars; camelCase framework auto-normalize and collision framework auto-suffix are not violations; only the mechanically unfixable remain — digit-start / punctuation / unicode etc.) | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `circular_decomposition` | Backward | sub-goal verbatim restates a strict ancestor (same name + theorem-head identical) = proving X by reducing to X, zero progress; the `_2` auto-suffix would mask it as an infinitely degenerating subtree | buffer + retry (retry_context carries a "try a different decomposition" hint) | (helper already ++); exhausted → status transition | `direct_attempt` |
| `batch_reference_cycle` | Backward | sub-goal stubs in the same batch reference each other cyclically — Lean modules cannot mutually import, no valid placement order (since task #84 non-cycle edges get imports mechanically injected by the framework; a cycle is the only thing that cannot be injected; the mirror predicts this within the session) | buffer + retry (merge statements or rewrite to remove the reference) | (helper already ++); exhausted → status transition | `direct_attempt` |
| `axiom_violation` | Builder + Backward | when the problem has an `axioms_whitelist` setting, confirm-build reports `axiom_error` or a rogue axiom outside the whitelist is used (including `sorryAx`) → restore backup, reject | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `cite_unproved_sibling` | Builder + Backward | cite-gate: the patch cites a sibling `L_<slug>` not yet proved (orphan / open / dead / disproved) | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `patch_body_contains_sorry` | Backward | leaf-bypass patch body still contains `sorry` (neither a legal decomposition nor a true leaf) | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `same_as_disproved` | Backward | sub-goal verbatim restates a statement already `disproved` within this problem (`_retry.py` `_TERMINAL_DECLINE_REASONS`) | terminal exit (no retry) | (helper already ++); generic failed | `direct_attempt` |
| `same_as_dead_unchanged` | Backward | sub-goal restates a `dead` twin within this problem, with nothing newly proved since the twin died — a blind retry in an unchanged world; detail attaches the twin's last failure forensic; if anything was proved after the twin died it passes as novel | terminal exit (no retry) | generic failed | `direct_attempt` |
| `duplicate_strategy` | Backward | decomposition has no novel sub-goal and its link set is identical to an existing proposed/stalled strategy on the same goal — a byte-identical re-claim (P3; detail names the existing s<id>) | terminal exit (no retry) | generic failed | `direct_attempt` |
| `no_progress` | Backward | sub-goal detected via isDefEq as definitionally equal to the goal being split itself (zero progress; a deeper dedupe tier than `circular_decomposition`'s same-name textual comparison) | buffer + retry (different decomposition) | (helper already ++); exhausted → status transition | `direct_attempt` |
| `agent_no_annotation` | Builder + Backward (Phase 2) | rc=0, build passes but patch.lean leading comment is blank | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `agent_no_output` | Builder Phase 2 | rc=0 but the agent wrote no `patch*.lean` | buffer + retry | (helper already ++); exhausted → status transition | `direct_attempt` |
| `agent_rc_nonzero` | (historical) | the old "any other rc" default; replaced 2026-08-08 by `unclassified_spawn_failure`; kept in the registry to interpret old dead_attempts rows | — | — | `direct_attempt` |
| `unclassified_spawn_failure` | Formalizer (`_spawn_failure`) | rc≠0, rc≠124, wall-clock ≥ 10s — **a death no criterion recognizes**. Owner ruling 2026-08-08: the counter asks whether the worker got a **fair chance** and failed; unexplained deaths must not be counted (every kind of death this project has seen — NTSTATUS, Bun panic, gateway 500, pagefile exhaustion — first appeared as an unknown rc silently charged to the agent until an audit surfaced it; the classification table can never be exhaustive, so the default flips) | early return, does not buffer itself, no budget spent | **no attempts++**, 30s cooldown, **`CONSEC_UNCLASSIFIED_LIMIT`=5 consecutive → daemon exits rc=2, handed to the operator** (a framework fault the strategist can do nothing about; handing it over only gets the fault rewritten as mathematics) | not projected (infra) |
| `agent_timeout` | Builder + Backward | claude rc=124 (SIGKILL at WORKER_TIMEOUT_SEC, default 900s, `dispatch.spawn_timeout_sec`) | **salvage parse once** (after the idle-window guard an active agent may have valid output on disk without a clean exit): parse returns terminal-success / decline → attach directly; returns non-terminal failure → fold into detail, run the original postmortem (writes `.drafts/`) + buffer + forced exhaust (no further retry) | (helper already ++); exhausted → status transition; on successful salvage the reason goes success/decline rather than timeout | `direct_attempt` |
| `agent_declined` | Builder | agent writes `-- decline: needs_decomposition` (unified directive system, 2026-05-10) | terminal exit (does not buffer itself) | **attempts++**; at SHELVE goes to review (entry_kind routing removed with v33; the Formalizer splits within its own session, so in practice this reason is only used by mint's `library_sufficient` and Librarian declines) | `direct_attempt` |
| `agent_infeasible` | Builder + Backward | agent writes `-- decline: unprovable` (incl. counterexample; formerly `parent_type_infeasible`) | terminal exit (does not buffer itself) | **attempts++** + goal `disproved` + `_propagate_disproved` | `infeasible_sub` (projected to the parent goal, not to itself; filter `_NON_AGENT_REASONS` excludes self) |
| `parent_needs_fix` | Builder + Backward | agent writes `-- decline: return_to_parent` (with a concrete fix hint: which hypothesis is missing / which structure to swap) | terminal exit (does not buffer itself) | **attempts++** + goal `dead` + `_propagate_dead`; description projected into the parent context's fix hint section | `infeasible_sub` (as above; the renderer uses `failure_reason` to distinguish fix-hint vs counterexample) |
| `agent_shelved` | Builder + Backward | agent writes `-- decline: shelve` (no counterexample, pure give-up) | terminal exit (does not buffer itself) | **attempts++** + `_enqueue_strategist_review` (to pending_strategist_review, no propagation) | `infeasible_sub` (as above; soft signal, left for future Strategist review) |
| `no_nl_correspondence` | Formalizer (intake sentinel or work-turn `-- decline:`) | NL-first (2026-07-25): the goal, or a sub-goal that would have to be invented, maps to no Programme Proof step — don't invent mathematics, hand it up | terminal exit (does not buffer itself) | **attempts++** + to pending_strategist_review, no propagation (the Strategist argues it to closure in the Proof or retires the claim) | not projected (`agent_visible=False`; the decline note reaches the Strategist via review context) |
| `agent_stuck_thinking` | Formalizer (`_retry.py`) | watchdog rules a thinking trap (rc=128); still no terminal output after fresh-sid takeover | buffer + keep retrying (the takeover itself costs no budget) | (helper already ++); exhausted → status transition. **Note: not yet in the `failures.py` REGISTRY** (traits all take defaults; pending fix) | `direct_attempt` |
| `agent_bailed` | Backward (rescue option d) | during the watchdog wall_cap → rescue spawn, the agent judges itself unlikely to succeed and exits after writing `_progress.md` to attempts_dir (no patch.lean / no split) | terminal exit (does not buffer itself) | **attempts++** + shelve only past SHELVE (goal stays open / attempting, re-dispatched next time); the outer wrapper persists `_progress.md` to `.drafts/backward_g<id>.md` for the next cold spawn | `direct_attempt` |
| `goal_no_longer_open` | Backward | race detected at parse stage: lake build finished but the goal is already proved/shelved | terminal exit (does not buffer itself) | generic `failed`/attempts++ (dispatcher writes the final dead_attempt) | not projected (`agent_visible=False`) |
| `subgoal_slug_collision` | Backward | pre-placement `proof_store` ownership guard: the sub-goal's `L_<slug>.lean` path is already owned by a **different** goal (cross-batch / re-decomposition collisions missed by `_resolve_slug_collisions`) → structural write refusal, prevents clobber-then-orphan DB↔file drift | terminal exit (does not buffer itself, wrote no files) | generic `failed`/attempts++ | `direct_attempt` |
| `forward_no_new_goal` | Forward | no `new_<slug>.lean` / file unreadable / elaborate failure / metadata missing (`Forward rationale:` etc.) / slug collides with charter statement vocab; an agent decline `library_sufficient` goes through `agent_declined` terminal instead | buffer + retry (elaborate stderr in `retry_context`, budget=FORWARD_RETRY_BUDGET=3) | Forward cascade: touches no goal, writes the inject decision outcome (infra failure re-enqueues the same decision_id, `763179f`) | not projected (target=Problem; goal_history projection only reads Goal-target rows) |
| `quota_exhausted` | Builder + Backward | rc=126 (gemini quota exhausted) | early return, does not buffer itself, no budget spent | **no attempts++**, 30s cooldown, not in CONSEC | not projected (infra) |
| `missing_dep` | Builder + Backward | rc=127 (CLI missing) | early return, does not buffer itself, no budget spent | **no attempts++**, 30s cooldown, not in CONSEC | not projected (infra) |
| `spawn_fast_fail` | Builder + Backward | rc≠0 and wall-clock < 10s (claude.exe crash / cwd) | early return, does not buffer itself, no budget spent | **no attempts++**, 30s cooldown, CONSEC=10 triggers daemon exit rc=2 | not projected (infra) |
| `system_killed` | Formalizer (`_spawn_failure`) | NTSTATUS-shaped rc ≥ 0x40000000 (0xC0000409 fail-fast / 0xC0000142 DLL-init / 0x40010004 debugger-terminate) or stderr with a Bun crash banner — the OS/CLI runtime killed the spawn, not agent behavior (2026-08-08 post-mortem: six such rcs went through `agent_rc_nonzero`, burned attempts, and pushed five healthy goals into review) | early return, does not buffer itself, no budget spent | **no attempts++**, 30s cooldown, not in CONSEC | not projected (infra, death note) |
| `gateway_unreachable` | Builder + Backward (1db4e8c) | worker thread got URLError / OSError(ECONNREFUSED/ECONNRESET/ENETUNREACH/ETIMEDOUT) / Windows WinError 10061/10054/64 — gateway HTTP transport completely unreachable | early return (dispatcher side, never enters the helper) | **no attempts++**, 30s cooldown, CONSEC=8 triggers daemon exit rc=2 (no infinite retry when the gateway is permanently dead) | not projected (infra) |
| `transient_timeout` | Builder + Backward (post-pilot fix) | worker thread got a `TimeoutError` (`$/lean/rpc/call` timeout at lsp_client.py:169, slot-contention RPC starvation, etc.) | early return (dispatcher side) | **no attempts++**, 30s cooldown, **not in CONSEC** (slot contention is healthy overload, not a dead gateway; counting it would make the circuit breaker misfire under a 244-problem benchmark) | not projected (infra) |
| `verify_infra` | Forward mint arm + Backward (2026-08-12) | `lifecycle.verify_file` returns `{"error": …, "transient": True}` — the gateway **does respond** but returns 5xx and outlasts the ~50s retry budget; most common: slots vanishing under a live session (`no slot claimed`) | early return (pipeline side) | **no attempts++**, 30s cooldown, **not in CONSEC** (the process is alive and talking; also these **arrive in clusters** — three in four minutes on 08-11, two in five minutes on 08-12 — counting them would falsely kill the daemon) | not projected (infra; `agent_visible=False` — "your slot disappeared" has no teaching value) |
| `framework_verify_error` | Forward mint arm + Backward (2026-08-12) | the other half of the same `error`: `transient=False` — 4xx, target file missing, malformed response. Retry cannot fix it (the framework asked for the wrong thing) | early return (pipeline side) | **no attempts++**, no cooldown, not in CONSEC | not projected (infra) |
| `superseded` (legacy) | pre-collapse Verify worker | no new rows produced after verify-collapse; historical DBs only | n/a | n/a | not projected |

**Framework-level reasons** (rare; triggered by framework / DB / FS races):

| failure_reason | origin | trigger |
|---|---|---|
| `goal_not_found` | Builder + Backward | `db.get_goal(goal_id)` returns None (DB / dispatch race) |
| `problem_not_found` | dispatcher (#125) | the queue row's problem has no `problems` row (a late-init problem `init`ed after daemon start) → 30s target cooldown, prevents a 1ms crashloop |
| `lean_file_missing` | Builder | parent goal's `.lean` does not exist on disk |
| `missing_parent_stub` | Backward | reading the parent lean failed (OSError) |
| `parent_stub_not_decomposable` | Backward | skeleton cannot extract a signature from the parent stub |
| `goal_no_longer_open` | Backward | mid-run the goal status is no longer `'open'` (race protection; `_abort` first rolls back written files) |
| `group_retired` | Strategist | the wake's authoring group reached a terminal status mid-dialogue (ancestor ReturnToParent cascade / post-delivery ghost wake) — the wake self-aborts at the round boundary or the pre-commit door; the discarded proposal + dialogue go to `programme_revisions` (2026-08-19: g464/g485 debated 11 rounds past their cascade-close) |
| `unknown_kind` | dispatcher | `_run_pipeline` got a task_kind that is neither Builder nor Backward (unreachable in current code; kept for enum completeness) |
| `worker_exception` | dispatcher (v38, 2026-08-08) | worker thread died of an uncaught **non-infra** exception: the cascade books one attempts++ against the Goal target, and this forensic row is written on the spot by the dispatcher's exception handler (the pipelines row exists since dispatch, so the FK is writable), so every increment has evidence; infra classifications (gateway_unreachable etc.) neither ++ attempts nor write this row |

These go through the generic cascade (attempts++), **events not projected** (the agent can neither
see nor act on them; `dead_attempts` is still INSERTed for operator forensics). Exception:
`missing_parent_stub` has a dedicated branch — after attempts++ it goes **straight to shelved +
propagates up** (no threshold wait; a vanished stub file causes a tight-loop re-dispatch).

**Notes**:
- rc → reason has **two mappings**: the in-pipeline `_spawn_failure` (124→`agent_timeout`, NTSTATUS/runtime crash→`system_killed`, <10s→`spawn_fast_fail`, **everything else→`unclassified_spawn_failure`, no attempts counted**) and the channel-level `failures.rc_to_reason` (124→`transient_timeout`, 125/128/unknown→`spawn_fast_fail`; used by Strategist/Adversary). The rc vocabulary also includes 125 stale-session, 128 stuck-thinking, 129 shutdown (`llm/base.py` `SpawnRC`).
- `agent_declined` is a string shared across pipelines: mint's `library_sufficient` and the Librarian's "cannot be mechanized" both use it. The split arm has no such escape (it exits via `unprovable` / `return_to_parent` / `shelve`).
- `lake_build_error` comes from patch build failure on the prove arm; on the split arm, from strategy assembly batch build failure. Design history of the directive vocabulary: `docs/archive/design/decline_directives.md`.

**Strategist / Librarian failure_reasons** (not Goal-target; not in the master table above):

These two pipelines' targets are not ordinary Goals; cascade and event projection both differ from Builder/Backward: failures do **not** touch sub-goals and do **not** project into any Context.md (target≠Goal; `events.py` only reads Goal-target rows).

Strategist (`Tooling/pipeline/strategist.py`):
- `strategist_schema_invalid` — `decision.json` parses but fails `verify_decisions` / the proposal-package mechanical checks; revised in a same-session resume, round cap `strategist.verify_retry` (default 6, counter shared with Adversary rebuttals)
- `provider_misconfigured` (rc 123, added 2026-07-30 with the Antigravity provider) — the provider is structurally unusable: a model slug the CLI does not recognize, rejected credentials (Gemini CLI personal tier discontinued 2026-06-18), or a tool auto-denied headlessly for lack of a `permissions.allow` rule. **For the latter, `agy` returns `status: SUCCESS` while writing nothing**, so the provider itself checks the attempts dir for artifacts and returns 123 when there are none. Traits: `provider_infra` (does not burn goal attempts — the math did not fail), `cooldown_scope='kind'` (a broken channel is not a single target), no death note (the reader is the operator, not an agent). **Retry cannot fix it** — fix `~/.gemini/antigravity-cli/settings.json` or the model config; authorization details are all recorded in the header of `Tooling/llm/antigravity_cli.py`
- `strategist_noop` — the Strategist legitimately decides Noop (nothing to do right now); not an error, record-keeping only
- `strategist_proposal_rejected` — the Adversary still objects after revision rounds are spent: proposal + all critiques stored in `programme_revisions` (status='rejected'), session discarded, next wake carries only a one-line rejection record and re-derives blind; target cooldown throttles consecutive rejection loops; does not burn root.attempts
- **Every discard path leaves a record** (v34 `programme_revisions.discard_reason`): Adversary rebuttal / proposal-package mechanical rejection / revision spawn rc≠0 / revision round failing to deliver decision.json / judge spawn dying or twice failing to deliver a verdict — all write a `status='rejected'` row noting which channel discarded it; `rejection_notice` carries the reason into the next wake and states explicitly that the batch was never dispatched. Rationale: `_plan.md` lands on disk the moment the spawn ends (before the verdict), so a discarded batch leaves notes claiming it was dispatched (SG 07-29 burned two wakes). When an early verify rejection happens before the proposal text was read into memory, `_discard_proposal` falls back to reading `proposal.md` from the attempts dir
- Also shares `agent_no_output`. **Adversary channel**: judge spawn **infra rc** (`is_infra`) is first retried inside `review` up to `INFRA_SPAWN_RETRIES` times (15s backoff); only when spent does it return the infra reason from `rc_to_reason` — a single provider hiccup must not void a proposal the Strategist already finished (#132, SG 07-30 measured 6.2min/28k tokens); a missing or unparseable `verdict.json` uses the **independent** `VERDICT_TRIES` budget (the judge twice failing to deliver a verdict = wake-level failure) → `agent_no_output`. The same family of fixes also applies to strategist revision-round spawns. No Adversary-specific reason string

Librarian (`Tooling/pipeline/librarian/`): failures go through the **per-unit fail-count** of `core/librarian_sched.py` `_advance_librarian_chain` (`librarian_fail_counts`, persistent across restarts); consecutive failures beyond `LIBRARIAN_MAX_CHAIN_RETRIES` (=2, i.e. the 3rd) → the unit **STALLs** (no more refill, no goal touched, no shelve). `librarian_file_busy` does not count (another worker holds the file).
- **migrate**: `librarian_migrate_not_mechanical` (needs LLM, not a purely mechanical relabel) / `librarian_migrate_hole_unfilled` (sorry holes remain after relabel) / `librarian_migrate_build_failed` (the moved file does not build)
- **classify**: `librarian_not_classified` (prerequisite classify incomplete) / `librarian_schema_invalid` (classify agent output fails schema) / `librarian_bad_work_kind` (dispatch got an unknown work_kind) / `librarian_missing_prompt`
- **cleanup**: `librarian_cleaned_build_failed` (does not build after polish) / `librarian_warnings_remain` (builds but warnings remain, Mathlib-PR zero-warning bar unmet; most common sticking points = unused hypothesis binder + line-length; cleanup must clear to zero mechanically/agentically) / `librarian_verify_failed` / `librarian_gate_failed` (per-file Mathlib-PR gate failed) / `librarian_axiom_violation` (**post-rewrite axiom gate**: cleanup's LLM rewrite stages (simplify / near-dup bridge / audit whole-file rewrite) are the only stage after migrate's axiom gate that can change a decl's axiom set; at the end, per-decl `#print axioms ⊆ whitelist` is re-run on the final text; an `axiom` declaration is always a hard-fail)
- **bridge**: `librarian_bridge_not_mechanical` / `librarian_no_root` / `librarian_axiom_violation` (deliverable branch: after cite_drop, run the per-decl axiom gate on every harvested file — deliverable problems have no root to re-derive from and builds-only does not cover the axiom surface; classic problems are covered by Gate B's root closure probe)
- **cross-file / upstream**: `librarian_file_busy` (not counted) / `librarian_file_owned_by_other` / `librarian_integrity_error` (DB↔file drift) / `librarian_needs_upstream_unresolvable` / `librarian_reopened_upstream`
- **shared**: `agent_error` (Librarian agent spawn rc≠0) / `agent_no_output` / `agent_declined` (the agent judges the unit cannot be mechanized)

**Scholar (paper v2, D11)**: `scholar_no_query` (FetchPaper decision row has no query — commit-side bug or hand-edited decision) / `paper_unfetchable` (parse succeeded but no whitelisted copy to fetch; the precise request (DOI/URL) is written into the decision's `outcome_detail`, manual channel takes over). Neither counts goal attempts; the non-projection is because target=Problem (goal_history only projects Goal-target rows), not reason filtering.

`daemon_shutdown` (`_retry.py`, rc=129) — the wrap-up reason for in-flight retries when the
daemon receives a shutdown signal. **Note**: the registry currently marks it `origin='framework'`
rather than infra, so it falls into the generic cascade — it actually does attempts++, contrary
to the intent that shutdown should not burn budget (known defect; registry fix pending).

---

## 3. Event types (goal_history v1)

`compile_context` in `Tooling/agent/context.py` produces event objects through the `events.py`
projection layer and injects them into the `## Goal history` umbrella section (refactor in
progress, see `goal_history_unified.md`).

| event_type | DB source | digest structure | injected into whose Context.md | actionability |
|---|---|---|---|---|
| `direct_attempt` | `dead_attempts` where `target_kind='Goal'` AND `failure_reason NOT IN _NON_AGENT_REASONS` | `failure_reason` + truncated `failure_detail` + short PROPOSAL excerpt | `dead_attempts.target_id` (this goal itself) | must-see |
| `verify_failure` | `dead_attempts` where `target_kind='Strategy'` (pre-collapse rows; no longer produced after verify-collapse) | truncated strategy `proposal_md` + lake stderr summary | `strategies.goal_id` | must-see |
| `dead_strategy` | `strategies` where `status='dead'` AND `proposal_md != ''` AND ≥1 linked sub-goal | truncated `proposal_md` + list of sub-goal slugs the strategy split out | `strategies.goal_id` | must-see |
| `infeasible_sub` | `dead_attempts` where `failure_reason IN ('agent_infeasible','parent_needs_fix','agent_shelved')` JOIN `strategy_subgoals` to find the parent | sub-goal slug + `failure_reason` tag + summary (`_extract_root_cause` extracts `## Root cause` / `## Fix hint` / `## Counterexample`) | **parent goal id** (not the failed sub itself) | must-see |
| (filtered out) | `dead_attempts` where `failure_reason IN _NON_AGENT_REASONS` | — | — | not projected |

**`_NON_AGENT_REASONS`** — the set of non-projected reasons. **Derived from the full set of
`agent_visible=False` entries in the `failures.py` REGISTRY** (events.py only re-exports; the SQL `NOT IN` references it), currently 12 entries:
- `spawn_fast_fail` — infra fault (claude.exe crash / cwd / quota)
- `agent_infeasible` / `parent_needs_fix` / `agent_shelved` — the three cascade-up declines are re-projected as `infeasible_sub` (into the parent context); not repeated in the failing goal's own direct_attempts
- `no_nl_correspondence` — the decline note reaches the Strategist via review context, not goal history
- `goal_not_found`, `problem_not_found`, `lean_file_missing`, `missing_parent_stub`, `parent_stub_not_decomposable`, `goal_no_longer_open`, `unknown_kind` — framework / DB / FS races; the agent can neither see nor act on them

**The two axes of the audience rules** (no more kind-gating on Builder/Backward):

1. **Target locality** — the event target's relation to the currently dispatched goal (self / own strategy / parent's sub)
2. **Actionability** — must-see / on-demand / not projected

Detailed axis design, why kind-gating could disappear, implementation mapping → `docs/archive/goal_history_unified.md` §"Audience rules".

**Edge cases**:

- **`dead_strategy` ↔ `verify_failure` overlap**: the same dead strategy can have a corresponding row in both places (status='dead' + dead_attempts target_kind='Strategy'). The projection layer dedupes — the strategy-id set for `dead_strategy` first subtracts those covered by `verify_failure` (`compile_context` computes the exclude set + SQL `NOT IN` in `events.dead_strategies`; effective only when the audience includes verify_failure).
- **`agent_infeasible` dual identity**: the DB row looks like any other direct_attempt (`target_kind='Goal'`, `target_id=the failed sub-goal`), but the actionable signal sits at the parent. The projection layer checks `failure_reason == 'agent_infeasible'` and re-projects as `infeasible_sub` with `target_goal` set to the parent. No parent (root itself infeasible, theoretically impossible) → drop.
- **Empty bucket**: an event_type empty for a goal → no sub-section header, no companion file (avoids empty files polluting the sandbox).

---

## 4. Crash-window compensation table (task #11, 2026-07-04 inventory)

State propagation is non-transactional (every db helper commits on its own; §13 rejected
two-phase). This table = the exhaustive conclusion of "what does a daemon dying between commit
boundaries leave behind × who rescues it"; full per-window evidence in the inventory record
(session task #11).
Compensation layers: **R**=startup `recovery.recover_at_startup`, **T**=per-tick `reconcile_stuck_states`,
**B**=`db.reconcile_settled_inject_outcomes`, **S**=`consistency.consistency_sweep`
(second layer of `asterism drift-check`; `repair_unambiguous` auto-repairs the unambiguous
subset inside R), **G**=root integrity gate + `proof_store.inventory`.

| Window class | Half-done state | Handling |
|---|---|---|
| A1/A4 verify promote, file first | alias file written, strategy not succeeded / backup not cleared | R (backup restore/cleanup) + re-ready_for_verify ✅ |
| A2 between succeeded↔proved | succeeded strategy + goal not proved | R reopens and re-solves (dedupe converges); **S predicate** `succeeded_strategy_unproved_goal` makes it visible |
| A3/F3/F4 sibling sweep / cascade midway | live strategies left under a terminal goal, half-alive/zombie subtrees | **R+S**: `repair_unambiguous` completes the step the cascade owed (proved→superseded, killed→dead, via checked mutator); `stalled` has no legal edge, report-only; zombie trees visible via the `unreachable_alive_goal` predicate |
| B1 revival file written, not flipped | shelved goal file=alias not stub | **Fixed for good**: `_revive_shelved_alias` made idempotent (only recognizes its own handwriting: this canonical's import+apply delegation) → resumes build-verify+flip; S predicate `revival_pending` monitors |
| C1 rollback midway | partial restore | gate re-run converges; bisect may kill one extra upstream innocent (accepted explicitly, cost = one re-Backward) |
| D1-D6 backward placement windows | file without row / half INSERT / placeholder strategy | R (half-baked cleanup + orphan sweep + redispatch) ✅; D2 zombie rows visible via S; D6 bulk-dead inject outcomes backfilled by B |
| E1-E5 forward placement windows | file without row / not detached / no backlink | R sweep+redispatch converges (may re-mint; slug collision fails and backfills); E2 zombies visible via S `unreachable_alive_goal` |
| F1/F2 inject outcome/batch-wake lost | terminal but decision NULL / wake lost | B backfills the outcome ✅; wakes backstopped by the routine interval ♻️ |
| F5/F6 enqueue lost | pending_review / Forward re-dispatch without queue row | T backfills every tick ✅ (T's design purpose) |
| G1-G3 harvest/queue windows | worker commit finished but no cascade / queue row lost | full R; queue contents entirely re-derivable from durable state (architectural guarantee) ✅ |
| G2 attempts>dead_attempts | ledger drift | **Accepted explicitly**: attempts is the threshold SoT and the LLM call really happened; dead_attempts is pure forensics |
| H1 programme_revisions writes (v30) | between rejection/pass row and batch link / PROGRAMME.md render | **Not inventoried** — owes one window analysis per the maintenance rule (render re-derivable from DB, low risk; half-done rejection rows unverified) |
| H2 problems.state FSM (v29) | between problem transition and its companion writes | **Not inventoried** — `apply_problem_transition` is the only mutator; crash windows pending analysis |
| H3 Delegate group-open sequence (v35) | group INSERT → decision row → `opened_by` backfill → anchor to attempting → new-group seat enqueue, each step committing on its own | Partly rescued: lost seats backstopped by T1 (new group clock NULL, picked up within one interval); "group terminal but Delegate outcome NULL" backfilled by **B** (the group branch of `reconcile_settled_inject_outcomes`, tested). "Group without opened_by" and "anchor transitioned but decision not landed" **pending inventory** |
| H4 ReturnToParent sequence (v35) | decision row → anchor shelve+cascade → `groups.set_status('returned')` (chained: fill parent-group outcome + batch-done enqueue) | Same as H3: the outcome side backfilled by B; the half-done middle **pending inventory** |
| H5 child-group lightweight Ingest (v35) | `set_status('delivered')` single write+commit | Window extremely narrow; outcome side backfilled by B ✅ |
| H6 charter single copy | charter lives only in the `groups` table, no file-side mirror | **Accepted explicitly**: outside the proofs/ chokepoint's jurisdiction, not covered by drift-check; the DB is the SoT |
| E-class addendum | mint is now re-enqueued under the Formalizer kind | E1-E5 rescue conclusions unchanged; row names map to the forward placement paths |

Maintenance rule: **every new propagation path (a new multi-commit sequence) must add a row to
this table**, plus one of three: name an existing rescue layer / add an S predicate / accept
explicitly with rationale. (H1/H2 and the middle windows of H3/H4 are booked under this rule,
pending inventory.) Deferred: a commit-fault-injection harness (for every propagation entry
point, sweep "crash after the Nth commit" and assert all three reconcile layers sweep green) —
wait until S has been live for a while and observe the residue before deciding.

---

## 5. Cross-references

- Dynamic flow (full pipeline flow incl. failures): `docs/data-flow.md`
- goal_history v1 audience rules / implementation design history: `docs/archive/design/goal_history_unified.md`
- reason registry (machine SoT, trait definitions): `Tooling/state/failures.py`
- full cascade logic: `Tooling/state/transitions.py` `cascade_one` (dispatcher only re-exports)
- session retry / postmortem mechanism: `Tooling/pipeline/_retry.py`, `pipeline/_drafts.py`
