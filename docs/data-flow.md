# Asterism data flow

Verified against framework code at `dabf9e8f` (2026-08-30).

This document owns **runtime sequencing**: daemon startup, one dispatcher tick, pipeline
lifecycle, agent context, gateway admission, and recovery. Static state and invariants belong
in [`architecture.md`](architecture.md). Failure traits, accounting, and cascade branches
belong in [`failure_modes.md`](failure_modes.md).

## 1. End-to-end flow

```text
durable state
    │
    ├─ derive queue work ── lease row ── insert pipeline(running)
    │                                      │
    │                                      ├─ compile Context + scratch
    │                                      ├─ run worker / retries / gates
    │                                      └─ finalize pipeline + release scratch
    │
    ├─ cascade completed outcome on the main thread
    ├─ promote ready strategies / revive aliases
    ├─ verify newly proved roots
    ├─ derive Librarian and Strategist work
    └─ repeat until Ingest + Library endgame or an operator/limit stops the run
```

The queue is a delivery mechanism, not the authority for whether work exists. BFS work,
Strategist wakes, and Librarian units are re-derived from database state. A queue row is
leased while a pipeline is in flight and deleted only when that pipeline completes.

## 2. Daemon startup and dispatcher tick

### Startup

`Tooling/core/dispatcher/loop.py::run` establishes the runtime in this order:

1. resolve static or RAM-ledger concurrency and initialize the executor;
2. connect, migrate the schema, validate scope, and load DB-backed problem intent;
3. run startup recovery, then sweep orphan spawn sandboxes;
4. regenerate `BRIEF.md` for registered problems and surface human-paused problems;
5. warm the Lean gateway in the background and run the Lean interface contract gate;
6. begin the tick loop. NL work may run while Lean workers are still warming.

The daemon records source and configuration fingerprints at boot. With handoff enabled, a
later fingerprint change stops new dispatch, drains in-flight work, and transfers the scope to
a successor. This is a lifecycle mechanism, not hot reload: a running pipeline always finishes
under the process that started it.

### One tick

The stable tick order is:

| Phase | Action |
|---|---|
| collect | Read completed futures, finalize their queue leases, and call `cascade_one` for ordinary pipelines. Librarian results instead advance their derived chain unit. |
| verify | `verify_housekeeping` repeatedly promotes ready strategies and processes shelved alias revivals. |
| root gate | Reconcile proved-goal files, run integrity for roots whose marker is clear, then redraw their tree. |
| Library refill | Derive every dispatchable serial/per-file Librarian unit; the durable Library lifecycle holds the exit gate open. |
| exit checks | Exit only when scoped problems are ingested and no Library work or harvest state remains. `--once`, wall budget, idle, stop, and fatal gateway conditions have their own exits. |
| global holds | Update quota wait, network wait, provider/model quota blocks, and adaptive RAM pressure. |
| BFS refill | Enqueue eligible open goals as Formalizer work. Goals at the attempt threshold go to Strategist review instead. |
| Strategist triggers | Enqueue per-group routine and structural-stall seats. Pending review and completed-batch relays also have event-driven paths. |
| reconcile | Repair pending reviews or unresolved Inject products whose wake/queue edge was lost. |
| lease sweep | Release leases owned by a dead process or older than the TTL. |
| spawn | Pop claimable work permitted by gateway readiness, quota, cooldown, RAM, scope, and duplicate checks. |

Before a worker starts, the dispatcher resolves its problem, performs the problem's once-per-run
Defs/Root preflight, creates a pipeline id, inserts `pipelines.status='running'`, and submits
the worker. The worker finalizes that same row to `succeeded` or `failed`; a process crash leaves
an explicit `running` row for startup recovery.

Librarian file units are persisted as `target_id=problem` plus `queue.payload.file`. At pop time
the dispatcher forms an in-process `problem\x1ffile` identity for duplicate tracking and worker
routing; that separator is not the durable queue contract.

## 3. Common pipeline boundary

Every queue worker runs with its own SQLite connection and `WorkArea`:

1. `.attempts/<pipeline_id>/` is created and any pipeline-specific skeleton/context is staged;
2. the provider executes one or more turns;
3. framework parsers and commit gates read the final bytes from disk;
4. the worker finalizes the dispatch-time pipeline row and returns a compact result to the main
   thread;
5. artifacts needed for forensics are packed before `WorkArea` removes scratch and returns any
   claimed gateway session.

`PipelineResult.outcome` is separate from `pipelines.status`:

| Outcome | Meaning at the worker boundary |
|---|---|
| `proved` | A Formalizer mint landed an immediately proved goal. |
| `success` | The requested product committed: a proof/decomposition strategy, a sorry-bearing minted goal, a Strategist batch, or a Librarian unit. |
| `failed` | Terminal non-success, including structured declines, infra, races, and rejected work. |
| `exhausted` | The in-session retry budget ended after recorded agent-side failures. |
| `moot` | The target settled before this iteration could do useful work. |

Only `proved` and `success` map to `pipelines.status='succeeded'`; the other outcomes map to
`failed`. Goal attempts, dead-attempt evidence, cooldowns, and state cascade are deliberately
not inferred from that status alone; see [`failure_modes.md`](failure_modes.md).

## 4. Formalizer goal flow

`Tooling/pipeline/backward.py::run_backward` is the live Goal-target Formalizer entry. It uses
one strategy frame for both direct proof and decomposition:

1. load the goal and create a fresh strategy id/theorem name;
2. build and prewrite `patch.lean` with a locked declaration signature;
3. on the first organic attempt, run the deterministic `hint` pre-pass; a hit still goes
   through the ordinary commit gates;
4. run the short intake turn; `proceed` continues the same session, while a structured decline
   returns through the failure model;
5. run pre-search and compile the work `Context.md`;
6. enter `run_with_session_retries`; warm retries receive the prior reason and detail;
7. parse the final disk files and choose one commit shape:
   - no new sub-goal plus a complete proof body: commit a zero-subgoal strategy;
   - one or more `new_*.lean` files: validate and commit a decomposition strategy.

The commit path checks the class of errors, not just individual known examples:

- top-level name and slug ownership;
- locked signature and final `validate_file` hash (`stale_validation`);
- forbidden lemmas and elaboration-time metaprogramming;
- strict-ancestor and batch reference cycles;
- citation status and edge provenance (`minted` versus `cited`);
- textual twin reuse before kernel-level dedupe/no-progress probes;
- sorry placement, whole batch verification, and the axiom gate;
- a final target-state race guard before rows and proof files become durable.

The validate surface mirrors name, slug, and ancestor-cycle gates to teach the error before
commit, but commit is authoritative. A committed strategy returns `success`; the parent becomes
`attempting` in cascade and is proved later by Verify housekeeping after every dependency is
proved.

## 5. Formalizer mint flow

A targetless Strategist `Inject` queues `Formalizer` with `target_kind='Problem'` and a
`decision_id`. `Tooling/pipeline/forward.py::run_forward` produces one declaration:

1. prewrite the fixed `new_forward.lean` scaffold;
2. run intake, pre-search, and the mint context;
3. edit the same file across retries and parse its metadata/kind;
4. enforce metaprogramming, name, charter-vocabulary, declaration-shape, verify, and axiom
   gates;
5. dedupe in three useful directions:
   - reuse an alive/parked same-problem twin;
   - land a proved alias when an equivalent theorem already exists;
   - otherwise create a new detached goal/file;
6. store `produced_goal_id` on the authoring decision and look for reverse shelved-revival
   links.

A sorry-free declaration lands proved and returns `proved`; a theorem with a remaining proof
obligation lands open/detached and returns `success`. The Inject product is not considered
complete merely because the file was written: its decision outcome follows the produced goal
until that goal settles. Provider-infra failures requeue the same decision when no goal was
produced.

## 6. Strategist and Adversary flow

A Strategist seat belongs to a group. At spawn time the trigger is re-derived from persistent
state in this priority order:

1. `routine` when the group's routine clock is due;
2. `inject_batch_done` for an unacknowledged completed batch;
3. `pending_review` for a goal owned by the group;
4. `stall` when the group's slice has no live frontier or product;
5. residual `routine` if the reason that queued the seat vanished.

`stall` is recorded separately but behaves like `inject_batch_done`; both are members of
`BATCH_DONE_LIKE` and must advance the group rather than leave it idle. No wake is accepted for
a non-active problem, and a group that retires during dialogue aborts before commit.

A review does not take a seat beside its own batch. A goal entering `pending_strategist_review`
settles the Inject that produced it (`returned:review`), and while the owning group still has
in-flight batch work no separate `pending_review` seat is queued — the verdict is one of that
batch's reports and rides its wake. Every wake that reaches verify owes a verdict on the goals
awaiting one, whatever the trigger. `pending_review` keeps its own recorded identity but reads
`inject_batch_done.md`, as `stall` and `routine_fired` do (`strategist.PROMPT_ALIAS`).

One wake runs this loop:

1. compile the group's context, including every actionable pending-review dossier on a
   non-routine wake;
2. the Strategist writes `decision.json` and, for a non-exempt batch, `proposal.md`;
3. parse and mechanically verify the decision set and package;
4. reject a revision that is byte-identical to the proposal just rebutted; three consecutive
   no-deltas discard the wake;
5. stage an isolated Adversary projection and obtain per-criterion objection lists;
6. on rebuttal, resume the same Strategist session with the critique; mechanical errors,
   no-deltas, and rebuttals share the configured revision budget;
7. on pass, commit decisions and record/redraw the Programme revision; on discard, persist a
   rejected revision and a terse notice for the next blind re-derivation.

Decision side effects and structural restrictions are summarized in
[`architecture.md`](architecture.md#6-programme-and-decision-model). The exact verifier and
commit code is under `Tooling/pipeline/strategist/`.

## 7. Librarian flow

The Librarian starts only for a problem that is ingested, opted into Library promotion, and not
waiting for sign-off. The scheduler derives work from `library_decls` and
`librarian_fail_counts` rather than trusting a queued stage name:

```text
dedup → classify → migrate (per file) → cleanup (per file) → bridge
```

| Stage | Work and gate |
|---|---|
| `dedup` | Compute the live usage closure and classify keep/cite/drop candidates. |
| `classify` | Ask for file placement; mechanically merge SCCs and topologically order declarations/files. |
| `migrate` | Move a whole file's declarations, fill mechanical holes where possible, and run the commit gate. |
| `cleanup` | Refine, simplify, audit, rename, minimize imports, require a zero-warning final file, and rerun per-declaration axioms after rewrites. |
| `bridge` | Classic root: rederive the original statement from Library. Deliverable form: rebuild and axiom-check every harvested file. Stamp `library_bridged_at` on success. |

Failure counts are persistent per unit. A busy file does not count; repeated real failure past
the chain cap leaves that unit stalled for operator inspection without changing proof-goal
attempts.

## 8. Verify and root integrity

`Tooling/quality/verify.py::verify_housekeeping` runs synchronously after cascade and iterates to
a bounded fixed point:

- a `proposed` strategy whose linked goals are all proved is written into its parent as a thin
  alias, marked `succeeded`, and its competing strategies are superseded;
- a shelved goal with a proved `alias_target_id` is rebuilt as a delegation to that target and
  revived after verification.

Promotion is deliberately mechanical; it does not run an LLM repair turn. A background olean
warmer may build the newly promoted alias spine outside both the dispatcher main thread and LLM
executor.

When a root first becomes proved with `integrity_verified=0`, the post-proved gate reconciles
its files and probes the complete root closure. Success sets the marker and clears cascade
backups. Escaped `sorryAx` triggers source bisection and `rollback_cascade_chain`; an already
ingested problem is revoked and unharvested rather than leaving a false Library result.

## 9. Context and sandbox boundary

### Context compilation

Every worker receives a generated `Context.md`; large lazy material lives beside it in bounded
companions such as `CATALOG.md`, `BATCHES.md`, `ADJUDICATIONS.md`, `PAPER_MAP.md`, and attempt
history files. Empty sections are omitted.

| Seat | Ordered content groups |
|---|---|
| Formalizer goal | brief and lessons; papers; Programme/standing guidance and Inject argument; goal and reusable Library; strategy/parent frame; pre-search or proved siblings; catalog pointer; prior progress/patch; unified goal history |
| Formalizer mint | Inject argument; group conventions and Programme proof; in-problem Library; pre-search; prior mint proposals and active goals; charter/user word; forbidden lemmas; papers |
| Strategist | trigger and user word; non-routine review dossiers; stall/Ingest/disproof gates; own group and children; Programme/directive/plan note; batch outcomes and reopen promises; active goals and failure replay; tree/catalog/adjudications; charter and papers; routine-only KB curation |

The exact order is code, not prose: `agent/context.py::compile_context`,
`agent/phase2_context/forward.py::compile_forward_context`, and
`agent/phase2_context/compile.py::compile_strategist_context`.

### Filesystem and tools

Provider adapters implement one envelope:

- the working scope is the problem plus the pipeline's scratch and explicitly granted
  Library/Papers/mathlib surfaces;
- other problems, operator state, foreign attempts, and framework/user-owned inputs are fenced;
- writes are limited to the attempts sandbox or the role's sanctioned edit surface;
- `problem.json`, `Defs.lean`, `Root.lean`, and `PROGRAMME.md` are denied to worker edits;
- shell execution is denied; common tools are provider-independent MCP operations:
  `inspect`, `write_file`, `compute`, `loogle`, and `validate_json`;
- the Strategist additionally receives `paper_search` and `paper_fetch`; the Formalizer Lean
  phase receives the LSP editing/inspection/validation tools;
- the Adversary sees only its projection, not the source workspace.

`spawn_guard.py`, `llm/envelope.py`, and the provider adapters jointly enforce this boundary.
Commit gates remain the final defense if a provider-side permission layer fails open.

## 10. Gateway and resource flow

The gateway is warmed in the background. Lean queue kinds remain unleased until warmup and the
interface contract pass; Strategist work can proceed because it does not claim a Lean slot.

A Lean pipeline registers its target and receives a session token bound to one warm slot.
Editing, diagnostics, declaration queries, and validation use that session. Non-pipeline
housekeeping borrows through `verify_file`, preferring an unclaimed slot.

Every elaboration must either converge or hit the wall in `lsp/gateway/wall.py`:

- the primary time meter is Lean worker CPU time, with a wall-clock backstop;
- when the adaptive ledger is active, private-memory growth in that elaboration is also
  bounded;
- queue time behind an elaboration lane is credited back to the provider session's wall;
- a wall hit kills/reclaims the worker, records a teaching verdict, and refuses identical
  content again in that session;
- native computation receives an additional confirmation gate so “still elaborating with no
  diagnostics” is never reported as success.

With no `dispatch.ram_budget`, the static pool limits all in-flight pipelines. With a valid RAM
budget, Lean and NL admissions split:

- the gateway warm target opens at the lesser of elaboration lanes and the RAM target, then
  grows one slot at a time under measured calm;
- Lean admission follows confirmed open gateway slots;
- NL admission follows the budget remainder and measured available memory;
- pressure pauses new dispatch, and waiting NL work may ask the gateway to yield an idle Lean
  slot.

Exact knobs and defaults remain in `core/config.py::CONFIG_SPEC`, `core/ram_ledger.py`, and
`lsp/gateway/wall.py` rather than being copied here.

## 11. Failure, interruption, and recovery

The Formalizer retry helper eagerly records each retryable agent failure, then continues the
same session with a compact retry context. Timeout and thinking-trap paths may salvage a valid
disk result, transfer to a fresh session, or leave a `.drafts/` progress note. Provider and
framework failures use the registry traits and dispatcher cooldown/park logic. The complete
taxonomy is [`failure_modes.md`](failure_modes.md).

Recovery is layered by durable fact:

| Residue | Recovery owner |
|---|---|
| stale `pipelines.status='running'`, abandoned queue leases, incomplete strategy placeholders | startup `state/recovery.py` plus the lease sweep |
| orphan spawn sandbox or interrupted file projection | startup sandbox sweep and its manifest/backup |
| ready strategy or alias revival not yet promoted | next tick's derived Verify queries |
| pending-review goal or settled Inject/Delegate with a missing relay | per-tick `reconcile_stuck_states` and DB batch reconciliation |
| DB/file ownership or lifecycle drift | `proof_store.inventory`, `state/consistency.py`, `asterism drift-check` |
| false proved root or post-Ingest soundness failure | root integrity rollback, problem revocation, and Librarian unharvest |
| generated view stale after a commit | redraw from DB (`TREE.md`, `PROGRAMME.md`, `BRIEF.md`) |

Recovery converges from durable state; it does not make queue rows or generated Markdown into
new authorities.
