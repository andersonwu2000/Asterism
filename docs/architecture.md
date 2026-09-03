# Asterism architecture

Verified against framework code at `dabf9e8f` (2026-08-30).

This document owns the system's **static shape**: authority boundaries, runtime roles,
persistent state, state machines, soundness gates, and invariants. Runtime sequencing belongs
in [`data-flow.md`](data-flow.md); failure classification and cascade effects belong in
[`failure_modes.md`](failure_modes.md). Historical design records explain why a mechanism was
introduced, but they are not descriptions of the current runtime.

## 1. Authority map

Do not treat one broad statement such as “the DB is the SoT” as applying to every byte. The
current ownership split is:

| Concern | Authoritative source | Derived or secondary forms |
|---|---|---|
| Graph, lifecycle, queue, pipelines, decisions, groups, Programme revisions, Library lifecycle, usage and forensics | SQLite schema and rows under `Tooling/state/db/` | `TREE.md`, `PROGRAMME.md`, UI projections |
| Goal, strategy, problem and group state vocabularies | `Tooling/state/transitions.py`, `Tooling/state/groups.py` | schema `CHECK` constraints, documentation |
| Failure taxonomy and traits | `Tooling/state/failures.py::REGISTRY` | retry/cooldown/projection sets, this document's narrative companion |
| Strategist decisions and triggers | `Tooling/pipeline/strategist/model.py` | schema accepts additional historical values |
| Problem intent at runtime | top-group `groups.charter`, `problems.user_word`, `problem_settings`, `problem_papers` | `problem.json` is the durable seed refreshed by sanctioned writers |
| Lean source bytes | `Root.lean`, `Defs.lean`, and framework-owned files under `proofs/` | DB paths and statements index those files; proof writes pass through `proof_store` |
| Configuration keys and defaults | `Tooling/core/config.py::CONFIG_SPEC` plus each `config.get` call | `Asterism.yaml` and environment values override defaults |

The database is SQLite in WAL mode. Schema version and migrations are authoritative in
`Tooling/state/db/core.py` and `Tooling/state/db_migrations.py`; at this verification point the
schema is v44 with 18 tables.

## 2. Proof graph and completion modes

Asterism models proof search as an AND/OR graph:

```text
Goal      = OR   any one live Strategy may prove it
Strategy  = AND  every linked sub-goal must be proved
```

The graph is stored in `goals`, `strategies`, and `strategy_subgoals`. Since v44 every
strategy edge records its provenance:

- `minted`: the strategy created the sub-goal. Authorship and inherited-context walks use
  these edges.
- `cited`: the strategy reuses an existing goal. Dependency, verification, pruning, and cycle
  checks use both edge kinds.

There are two supported endgames:

- **Root proof**: the root goal is proved, the root integrity gate passes, and the top group
  commits `Ingest`. Library promotion is optional.
- **Anchor and claims**: a natural-language charter drives minted claims; the Strategist marks
  deliverables, then commits `Ingest` when the charter is satisfied. A human sign-off may be
  required before Library work. `Root.lean` and `Defs.lean` are optional for a pure-NL problem.

`Ingest` is the problem-level completion decision. Root proof is a hard prerequisite when a
root exists, but root proof by itself does not terminate the problem.

## 3. Runtime roles

The live dispatcher has three pipeline kinds. The Adversary and Verify are intentionally not
independent queue workers.

| Role | Live target | Responsibility |
|---|---|---|
| **Formalizer** | `Goal` or `Problem` | Goal target: prove or split in one session. Problem target: mint one toolkit declaration from a Strategist `Inject`. Implemented by `pipeline/backward.py` and `pipeline/forward.py`. |
| **Strategist** | `Group` | Maintain one group's Programme, adjudicate reviews and stalls, and commit decision batches after mechanical checks and Adversary review. |
| **Librarian** | `Problem`, optionally one file in queue payload | Turn an ingested, opted-in problem into checked `Library/` declarations through a derived work DAG. |
| **Adversary** | sub-spawn inside a Strategist wake | Judge a proposal package in an isolated projection; it has no queue kind or independent seat. |
| **Verify housekeeping** | main dispatcher thread | Promote ready strategies, revive aliases, and run root-level integrity work; it is pure framework work, not an LLM pipeline. |

The schema still accepts `Builder`, `Backward`, `Forward`, `Verify`, and `Scholar` in historical
pipeline/queue rows. Dispatch compatibility routes the former proving names to Formalizer.
Scholar is retired: paper search and fetch are Strategist tools, and no Scholar pipeline or
prompt remains.

Concurrency is scoped by the work's identity:

- one organic Formalizer pipeline per goal; OR expansion is passive rather than eager;
- one Strategist seat per active group, so sibling groups may run concurrently;
- mint siblings are distinguished by `decision_id` and may run in parallel;
- Librarian migration and cleanup parallelize by file while serial stages remain problem-wide.

## 4. Persistent and filesystem state

| Lifetime | Location | Contract |
|---|---|---|
| Durable relational state | `asterism.db` | Graph and lifecycle truth; every dispatched pipeline is inserted as `running` before its worker starts and finalized in place. |
| Durable problem source | `Problems/<domain>/<slug>/` | Human Lean inputs, framework proof modules, generated views, and `problem.json` seed. |
| Cross-pipeline continuation | `.drafts/`, `.presearch/` | Timeout/rescue notes, Strategist plan notes, and reusable pre-search results. |
| Per-pipeline scratch | `.attempts/<pipeline_id>/` | Context, proposed outputs, provider state, and temporary gateway metadata; removed by `WorkArea` after artifacts are packed. |
| Durable operational evidence | DB forensics plus `.asterism/{mcp_logs,transcripts,...}` | `dead_attempts`, usage, tool traces, and provider transcripts survive scratch cleanup. |

Framework-owned `proofs/` mutations go through `Tooling/state/proof_store.py`, which combines
atomic replacement, path ownership checks, and drift inventory. `asterism drift-check` adds DB
and filesystem consistency checks; generated `TREE.md`, `PROGRAMME.md`, and `BRIEF.md` are
redrawable projections rather than independent authorities.

## 5. State machines

### Goals and strategies

The canonical sets are declared in `Tooling/state/transitions.py`:

| Entity | States |
|---|---|
| Goal | `open`, `attempting`, `proved`, `shelved`, `pending_strategist_review`, `disproved`, `frozen` |
| Strategy | `proposed`, `succeeded`, `dead`, `superseded`, `stalled` |

A goal is a statement, and only the kernel settles a statement, so the hard-settled goal states
are exactly the two kernel-checked verdicts: `proved` and `disproved`. Every other way a goal
stops is a park (`shelved`), told apart by its `goal_events` event and revivable. The goal state
`dead` was retired at schema v51 (2026-09-04); `dead` remains a STRATEGY state, which is where
"the decomposition was wrong" belongs — a `parent_needs_fix` decline kills the strategy and parks
the sub-goal with `event='wrong_context_park'`. A transition into `proved` requires a
`ProvedReceipt` at the checked mutator; the `disproved -> open` edge survives for operator repair
only (a strategist `Inject` on a disproved goal is refused at verify).

All normal writes use `apply_goal_transition` or `apply_strategy_transition`. Cascade
propagation is main-thread-only; worker threads may commit their own target but do not walk
upward through the graph. Exact failure-to-transition behavior is centralized in
[`failure_modes.md`](failure_modes.md).

### Problems and groups

| Entity | States |
|---|---|
| Problem | `active`, `awaiting_human`, `ingest_signoff`, `ingested`, `revoked` |
| Group | `active`, `delivered`, `returned`, `closed` |

Only an `active` problem accepts Strategist wakes. “Stalled” is derived while active; it is not
a problem state. Problem transitions pass through `apply_problem_transition`; group status
changes pass through `groups.set_status`.

Exactly one top group exists per problem (`parent_group_id IS NULL`, enforced by a partial
unique index). It alone faces the human. A child group has its own charter, Programme,
Strategist/Adversary loop, clocks, and terminal result, but shares the parent's problem and
cannot cite across problem boundaries.

## 6. Programme and decision model

Each group owns a passed Programme revision chain. `PROGRAMME.md` renders the current passed
revision; `programme_revisions` retains passed and rejected packages. A non-exempt decision
batch must provide `proposal.md` with Title, Argument, Proof, and Roadmap sections, pass
mechanical verification, change after a rebuttal, and clear the Adversary before commit.

The live decision behaviors are:

| Decision | Architectural effect |
|---|---|
| `Inject` | Mint a new goal or explicitly redispatch/reopen a target goal. |
| `ConfirmShelve` | Settle a goal as shelved and propagate the lost route. |
| `RequestUserAmend` | Enter `awaiting_human` with a proposed charter/Lean-file amendment. |
| `MarkDeliverable` | Mark a kernel-backed claim for the anchor-and-claims endgame. |
| `Ingest` | Top group: enter the sign-off/ingested endgame. Child group: mark the group delivered. |
| `Delegate` | Open a child group; its terminal status resolves the parent's batch product. |
| `ReturnToParent` | Child-only hand-back as `refuted`, `amend`, or `exhausted`. |
| `CloseGroup` | Parent retires an active child group. |
| `Noop` | Audit-only decision; it creates no work product. |

`EmitDirective`, `FetchPaper`, and `AttemptDisproof` remain parseable so the verifier can teach
their replacements, but cannot commit. Standing guidance belongs in Programme conventions;
papers use the Strategist tool surface; disproof uses the ordinary proof machinery.

Inject and Delegate share batch completion semantics. A batch is complete only when every
produced goal, strategy, or child group has a non-NULL terminal outcome. `batch_id` is
immutable; a completion relay wakes the authoring group.

## 7. Soundness boundary

The controlling principle is: **no goal enters `proved`, and no declaration enters the
Library, without the relevant kernel-facing gate**.

| Gate | Boundary |
|---|---|
| Formalizer axiom gate | Before an immediately proved minted goal or a proof strategy is accepted; the used axiom set must fit the effective whitelist. |
| Validate/commit parity gates | Name collisions, ancestor cycles, stale validation, forbidden metaprogramming, citations, declaration shape, and other commit-time refusals are mirrored as early as possible in the editing tools. Commit remains authoritative. |
| Verify promotion | A ready strategy is promoted mechanically only after all linked goals are proved; the checked transition supplies a receipt. |
| Root integrity gate | Rechecks the complete root closure, statement pin, and axioms; on escaped `sorryAx` it bisects and rolls back the culprit chain. |
| Librarian gates | Import closure, whole-file verification, per-declaration axioms, no `axiom` declarations, def-equivalence for definitions, final rewrite recheck, and root/deliverable bridge. |

When `axioms_whitelist` is absent, `state.intent.effective_axioms` uses the framework default
(`Classical.choice`, `propext`, `Quot.sound`) and warns; absence never disables checking.
Elaboration-time metaprogramming is separately refused because it executes with framework
privileges and is not made safe merely by `#print axioms`.

## 8. Human intent and Root.lean

Runtime intent has three independent channels:

- the top group's charter is the problem's goal;
- `problems.user_word` is the human's standing, verbatim direction and is shown at every group
  depth;
- `problem_settings` contains machine settings such as forbidden lemmas, axiom whitelist,
  Library opt-in, and sign-off behavior; paper bindings live in `problem_papers`.

`problem.json` seeds those values during init and is refreshed best-effort by sanctioned
writers. The daemon does not poll it as runtime authority.

For a rooted problem, `Root.lean` moves through three conceptual forms:

1. the human-authored statement with a hole, registered as a frozen root goal;
2. an unchanged root while work proceeds under `proofs/`;
3. a proved root, either a complete theorem body or a thin import/alias to the winning
   strategy. The root statement pin must still match the user baseline.

## 9. Durability and process boundaries

- Queue pop is a lease (`owner_pid`, `leased_at`), not a delete. Completion deletes the row;
  startup recovery and the per-tick TTL sweep release abandoned leases.
- A `pipelines` row exists for the full dispatch lifetime. Startup recovery finalizes stale
  `running` rows after a daemon crash.
- Per-retry evidence is written before its paired `goals.attempts` increment, so the remaining
  crash window can under-count an attempt rather than leave an unexplained increment.
- Ready strategies, Librarian work, and most queue contents are re-derived from durable state.
  Pending-review and unresolved batch relays also have a per-tick reconciler.
- Proof writes use atomic replacement and backups; startup recovery, consistency sweep, and
  root integrity are separate correction layers.
- The daemon process tree is attached to a kill-on-close process group/Job Object so provider
  and Lean children are reclaimed with the daemon.

Operationally, `.asterism/degraded.json` records best-effort mechanisms that failed open (for
example a dedupe probe). This is observability, not a second lifecycle state.

## 10. Configuration resolution

For a registered key, `config.get` resolves in this order:

1. its primary process environment variable, then the workspace `.env` value;
2. the dotted path in `Asterism.yaml`;
3. any declared legacy environment variables;
4. the call-site default.

`CONFIG_SPEC` is the key registry and drift gate. Exact defaults belong there, not in these
architecture/data-flow documents. Configuration is cached for a daemon run; source,
`Asterism.yaml`, or `.env` fingerprint drift can trigger a drain-and-handoff when enabled.

`dispatch.ram_budget` changes the concurrency model: when set and parseable, adaptive RAM
admission owns the Lean/NL split and `dispatch.pool` becomes a fallback/executor bound. When it
is absent, the static pool model remains active. See [`data-flow.md`](data-flow.md) for runtime
admission and elaboration walls.

## 11. Code map

```text
Tooling/
  core/
    dispatcher/       main loop, refill, triggers, worker boundary, singleton lock
    config.py         config registry and precedence
    ram_ledger.py     adaptive Lean/NL admission
    librarian_sched.py, quota*.py, network_wait.py, degraded.py
  state/
    db/               schema facade split by domain
    transitions.py    checked state transitions and cascade
    failures.py       failure registry
    groups.py, programme.py, intent.py, proof_store.py, recovery.py, consistency.py
  pipeline/
    backward.py       Formalizer goal arm
    forward.py        Formalizer mint arm
    _retry.py         shared session/retry lifecycle
    strategist/       decision model, verification, commit, wake
    adversary.py
    librarian/
    events.py, _axiom.py, _cite_gate.py, _disprove.py, _presearch.py
  quality/
    verify.py         ready-strategy/revival/root housekeeping
    dedupe.py, dedupe_probe.py, names.py
    librarian/
  agent/
    context.py, phase2_context/   Context and companion compilation
    runtime.py, sandbox.py
  llm/
    provider adapters, capability model, sandbox envelope and guards
  lsp/
    gateway/          sessions, elaboration lanes/wall, verification, RAM governor
    lifecycle.py, client.py, decl_oracle.py
  knowledge/          inspect, loogle, compute, validation and paper tools
  papers/             paper shelf/search/fetch/index
  prompts/            formalizer, strategist, adversary, librarian, shared prompts
  serve/              console/API projections and chat explainer
```

## 12. Modification invariants

1. Transition state through the checked mutators; never add a raw status write casually.
2. Run propagation only on the dispatcher main thread.
3. Require a `ProvedReceipt` for every transition into `proved`.
4. Preserve the distinction between `minted` and `cited` strategy edges.
5. Route framework-owned proof writes through `proof_store` and keep path ownership unique.
6. Keep pipeline start/finish and per-retry evidence ordering intact.
7. Treat a live child group as an in-flight batch product in both stall and anti-idle queries.
8. Keep exactly one top group per problem; top/child human-interface restrictions belong in
   the decision verifier.
9. Do not let a non-active problem accept automatic wakes or Librarian work during sign-off.
10. Keep validation mirrors helpful, but make commit gates authoritative and fail closed at
    soundness boundaries.
11. Add schema changes through a versioned migration and bind new enums to their code SoT.
12. Add a failure reason first to `failures.REGISTRY`, then document it in
    [`failure_modes.md`](failure_modes.md).
