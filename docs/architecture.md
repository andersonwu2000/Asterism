# Asterism — Architecture

Originally written 2026-05-06; fully rewritten against the code 2026-07-03; drift-corrected
2026-07-29 (Formalizer merge, research mode, problem FSM); discussion group tree added
2026-08-02 (v35). This doc covers the **conceptual shape**: what roles make up the system,
where state lives, and which invariants uphold correctness. Dynamic flow (how a tick runs,
pipeline step-by-step) is in `docs/data-flow.md`; failure vocabulary in `docs/failure_modes.md`;
the code is authoritative for technical detail — read it when you touch it.

---

## 1. What this is

Abstract "prove Lean 4 theorems with LLMs" into BFS over an AND/OR graph:

```
Goal      = OR  : any one Strategy succeeds → Goal succeeds
Strategy  = AND : all sub-Goals succeed → Strategy succeeds
```

Leaf Goals are closed directly by an LLM writing tactics; non-leaf Goals are decomposed via
Strategies. The whole reasoning tree lives in sqlite (`goals` × `strategies` ×
`strategy_subgoals`); **the DB is the single source of truth**.

Two completion modes:

- **classic**: root goal proved → integrity gate → (opt-in) Library promotion.
- **anchor+claim** (since 2026-06): a human writes the Manifest in natural language; the
  Strategist generates defs/claims and marks deliverables with `MarkDeliverable`; the kernel
  computes the anchor closure for human `asterism review` / `reject`; once all deliverables
  reach a terminal state the Strategist issues `Ingest`, which goes through **human sign-off**
  (`approve-ingest` / `reject-ingest`) before harvesting into the Library. The root may be
  mere scaffolding at this point (`main : True`).
  `Root.lean` / `Defs.lean` are both optional — a pure-NL problem lacks both: no root goal
  row; a structural stall wakes the first Strategist.

---

## 2. Roles: four workers, one housekeeping

**Workers are the LLM entry points; pure framework operations never occupy a worker slot** —
this principle draws the role boundaries.

| Role | target_kind | What it does |
|---|---|---|
| **Formalizer** | Goal / Problem | The sole Lean proving worker (merged from the former Builder/Backward/Forward trio on 2026-07-27, v33). Goal-target: intake triage (incl. falsity scan, may decline) → decides on its own whether to prove directly or split into a Strategy + N sub-Goals; Problem-target (**mint**): dispatched by the Strategist, produces one new toolkit lemma. Implementation remains split across `pipeline/backward.py` (prove/split) and `forward.py` (mint) |
| **Strategist** | Problem | Reads problem state, writes a proposal package (Programme revision + decision batch), commits after the Adversary's verdict clears it (twelve decision kinds, see below) |
| **Scholar** | Problem | Dispatched via Strategist `FetchPaper`: fetches whitelisted papers into `Papers/`, builds the index (v23) |
| **Librarian** | Problem (per-file) | After proved + opt-in, runs the five-stage chain: dedup → classify → migrate → cleanup → bridge |
| **Verify housekeeping** | — | Not a worker: runs sequentially inside the dispatcher tick, assembles fully-proved strategies, writes aliases into the parent, runs G1 revival |

**The Adversary (judge) is not a worker kind** — it is a sub-spawn inside the Strategist wake,
fresh per round, that reviews the proposal package under hard isolation in a projection
directory and produces `verdict.json`; the framework derives pass/rebuttal from the
per-criterion verdicts (see "Research mode" below).

Twelve Strategist decision kinds (SoT: `strategist.py` `DECISION_KINDS`): `Inject` /
`ConfirmShelve` / `EmitDirective` / `RequestUserAmend` / `MarkDeliverable` / `Ingest` /
`FetchPaper` / `AttemptDisproof` (the framework mechanically mints the ¬P goal — belief is
not trusted; both directions must go through the kernel) / `Delegate` / `ReturnToParent` /
`CloseGroup` (these three belong to the group tree, see below; `ReturnToParent` is
child-group-only, `CloseGroup` is the reverse of `Delegate` — a parent retires a child) /
`Noop`. Three triggers: `routine` (incl. the first stage of belief audit) / `pending_review` /
`inject_batch_done` (structural-stall wakes are also this kind — fresh problem, deadlock, and
root proved awaiting Ingest all count as "empty batch done"). `Ingest` is the sole terminal
state: while a root is present the framework hard-rejects it until the root is proved;
`ingested_at` drives T1/T4 liveness, Librarian selfstart, and daemon exit.

Concurrency discipline: at most one pipeline per Goal at a time (passive OR, cap=1); at most
one in-flight Strategist per problem; mint deduplicates on `(target, kind, decision_id)` —
N mint Injects in the same batch fan out in parallel; the Librarian parallelizes per file.
A problem in `ingest_signoff` suspends all automatic Librarian paths (awaiting human sign-off).

### Research mode (Programme + Adversary, since 2026-07)

The Strategist no longer submits decision batches bare: a **proposal package** (`proposal.md`:
`# Title` / `## Argument` / `## Proof` / `## Roadmap`) goes with the decision batch to the
Adversary for round-by-round review; rebuttals ride the verify-retry loop (sharing the round
cap with mechanical checks); still rebutted at the cap → proposal + critique are stored in
`programme_revisions` (v30, status='rejected') and the session is discarded. The chain of
passed Programme revisions is the problem's strategic SoT (`PROGRAMME.md` is only a render;
v31 pins at most one passed per rev via a partial unique index).
**NL-first** (since 2026-07-25): workers treat the Programme's `## Proof` as their premise;
a goal that maps to no NL step is handed back as `no_nl_correspondence` — no inventing
mathematics. {`FetchPaper`, `RequestUserAmend`, `Noop`, `ReturnToParent`} are all exempt from
the package gate; a proposal must include ≥1 experiment
(`Inject`/`AttemptDisproof`/`Delegate`). Design SoT:
`docs/internal/research_mode_design.md`, `nl_first_design.md`.

### Discussion group tree (2026-08-02, v35)

The NL argumentation layer grew from "one Programme, one strategist, one Adversary for the
whole problem" into **a tree**:

> Group = one charter + its own Programme + its own strategist/Adversary loop + the subtree beneath it.

The charter is a natural-language claim delegated by the parent group — **charter is to a
child group what the Manifest is to the whole problem**, so a child group inherits every
whole-problem mechanism all the way to its endgame. Groups are **partitions within the same
problem** (cross-problem citation is forbidden by the cite gate), not recursive problems; the
top-level group is a real row in the `groups` table with `parent_group_id IS NULL`, unique per
problem (pinned by a partial unique index), and is the only group facing the human.

- **`Delegate`**: hands a claim the group cannot yet prove itself to a new group (optionally
  with a `target_goal_id` as rescue anchor; the anchor flips to `attempting`). Exempt from the
  Adversary's closure-law criterion 4 — the delegated item is itself the argument; the
  Adversary instead reviews that the charter is precisely decidable / the Proof is complete
  assuming it holds / it depends on no ancestor charter or this group's conclusions / it is a
  real burden, not a skipped step.
- **`ReturnToParent`**: a child group hands back (`refuted` must point at a proved ¬charter
  brick / `amend` attaches a suggested new charter / `exhausted` attaches a post-mortem).
- **Structural walls (all at the verifier layer)**: the top-level group may not
  `ReturnToParent` (nowhere to go — the machine does not toss hard problems back to the
  human); child groups may not `RequestUserAmend` (they cannot see user files; go through
  `ReturnToParent` and let the parent decide whether to escalate).
- **A parent goes quiet after delegating**: `Delegate` and `Inject` share the batch in-flight
  accounting (both in-flight predicates recognize "a live child group" as the third kind of
  product — this "enters both gates together" rule is pinned by an invariant test); only a
  child group's terminal state wakes the parent. A child group's `Ingest` is the lightweight
  version (marks `delivered`, touches no sign-off/harvest/problem FSM); handing back marks
  `returned`, and the rescue anchor falls back to `shelved`.
- Wake seats, the routine clock, wall-state detection, the Programme revision chain, plan
  notes, and the Adversary projection are all **per-group**; a goal's group membership is
  derived, not stored in a column (anchor first → the group that authored the most recent
  producing decision → top-level group; resolution to a non-active group swaps to the nearest
  active ancestor).

Design SoT: `docs/internal/discussion_group_design.md`.

---

## 3. Where state lives

| Form | Contents |
|---|---|
| **DB** (`asterism.db`, sqlite WAL; version number and table list are authoritative in `state/db.py` `_CURRENT_USER_VERSION` (v35 and 17 tables at time of writing); recent milestones: v17 queue lease, v21 spawn_usage accounting, v23 Scholar/FetchPaper, v25 AttemptDisproof, v28 user_file_history, v29 problem FSM, v30/v31 Programme revision chain, v33 Formalizer merge, v35 discussion group tree) | The whole graph, pipeline history, dead attempt forensics, Strategist decisions, Programme revisions, group tree, Librarian lifecycle, KB lessons, spawn usage |
| **`Manifest.md`** | The only human-authored file (§4) |
| **`Defs.lean` / `Root.lean`** | Problem's custom definitions / framework-managed root (§5) |
| **`proofs/L_<slug>.lean`, `_strategy_s<sid>.lean`** | One file per sub-Goal, one assembled patch per Strategy |
| **`.drafts/`, `.presearch/`** | Cross-spawn progress notes / per-node pre-search cache |
| **`.attempts/<pid>/`** | Pure scratch, unconditional rmtree at spawn end (artifacts packed into `dead_attempts.artifacts` first) |

**Every mutation of proofs/ files goes through the single `state/proof_store.py` chokepoint**
(atomic write + ownership guard + drift inventory; a lint test forbids bare writes outside
it). `asterism drift-check` can verify DB↔file consistency at any time.

The schema is "code as documentation": table definitions in `Tooling/state/db.py`, the full
migration set in `state/db_migrations.py`. State enums have their SoT in
`Tooling/state/transitions.py` (8 goal states, 5 strategy states incl. `stalled`, 5 problem
states — see §7); the 4 group states
(`active`/`delivered`/`returned`/`closed`) are driven solely by `state/groups.py`
`set_status`. Schema CHECKs are bound by tests and cannot drift.

---

## 4. Human interface

**Manifest.md** (YAML frontmatter + markdown body; field SoT `state/manifest.py`):
`axioms_whitelist`, `forbidden_lemmas`, `library: true` (opt-in Library promotion),
`signoff: false` (benchmark unattended mode only, skips human sign-off; any parse anomaly is
coerced back to true); `paper:` is deprecated (binding moved to the `problem_papers` table).
`init` parses leniently: missing fields get defaults + a warning. **Not a single character of
the body is parsed** (2026-08-11): the operator writes whatever headings they like and the
whole thing is sent verbatim to every agent (median body size across 616 Manifests: 440B).
The formerly extracted-by-name
`## Statement` / `## Strategic notes` are no longer fields — the canonical statement is the
theorem signature in `Root.lean`, and the prover's hint channel is the auto-generated
`## Candidate lemmas`.

**Human intervention points for anchor+claim** (CLI): `asterism review` (view deliverables +
kernel anchor closure), `asterism reject` (reverse-closure cascade invalidation),
`approve-ingest` / `reject-ingest`
(the sign-off gate before harvest).

**Problem layout**: `<Domain>.<slug>` → `Problems/<Domain>/<slug>/`; Domains align with
mathlib top-level naming (`Topology`/`NumberTheory`/`Analysis`… by convention, not a
hard-coded whitelist). Old problems cannot be moved with a bare `git mv` — Lean module path =
file path, the build breaks. `Defs.lean` / `Root.lean`
are both optional (pure-NL may lack both); after hand-editing the Root statement, re-run
`init` or `asterism repin`
(user-file baselines go through `user_file_history`, v28).

---

## 5. The three states of Root.lean

**A initial**: the user hand-writes the sorry stub (the framework does not generate it;
`init` only does a lake-build type check + statement extraction, `--force` bypasses the type
check; the root goal starts `frozen`). **B in progress**: the framework only produces files
under `proofs/`; Root.lean is untouched. **C proved**: two sanctioned forms — (a) assembly
writes the complete `theorem main` in place (statement preserved byte-for-byte); (b)
`prune.reconcile_proved_goals`
rewrites it as a thin indirection —

```lean
import Problems.<p>.proofs._strategy_s<NN>
namespace Problems.<p>
def main := @Problems.<p>.s<NN>
end Problems.<p>
```

Note it is a `def` (the type is inferred from the winner strategy's signature); keyword
modifiers (`noncomputable`) and the
`@[instance]` prefix are preserved (a root may declare a Prop instance — the framework only
proves Props, never produces data).
Both forms pass `verify._root_statement_pin_ok` (statement pin, task #120 — the proved root
is pinned back to the user baseline).

---

## 6. Dispatcher main loop

Fixed order every tick: cascade → verify housekeeping → post-proved gate (reconcile + root
integrity) → librarian refill → exit check → quota-wait gate → bfs refill →
strategist triggers → reconcile_stuck_states (per-tick safety net) → lease sweep → spawn.
Step-by-step detail and exit conditions in `data-flow.md` §2.

**Discipline**: cascade **propagation** always runs sequentially on the main thread
(guarded by `transitions.assert_main_thread`; CI strict mode raises). A worker thread may
perform commit-time state transitions on **its own target** (always via the transitions
checked mutators), but never runs a propagation entry point. This eliminates a whole class of
OR-races.

**pipeline = slot** (#118): dispatch.pool and gateway workers are 1:1 and scale together; a
pipeline claims one warm slot on entry and all verification during its lifetime hits its own
slot (own-slot, no eviction). Borrowing
(`verify_file`) is restricted to non-pipeline contexts, preferring unclaimed slots. Semantic
detail in data-flow §0.

At startup the daemon binds the whole process tree into a kill-on-close Job Object — when the
daemon dies, children (claude /
lake) are reclaimed automatically; no manual orphan cleanup needed.

---

## 7. State machines and cascade (conceptual)

All goal/strategy state transitions go through the checked mutators in
`state/transitions.py`: legal edges are registered in
`GOAL_EDGES` / `STRATEGY_EDGES`; in CI strict mode an unregistered edge raises directly, in
production it logs loudly. A lint test with a count ratchet forbids new raw
`UPDATE … SET status`.

Conceptual shape of the cascade (the full outcome × transition table lives **only** in
`failure_modes.md` §2):

- Failures increment `attempts`; reaching SHELVE_THRESHOLD → transition to
  `pending_strategist_review` for Strategist adjudication — **only ConfirmShelve truly makes
  it `shelved` and propagates upward** (killing the parent strategy that depends on it; a
  parent with no live strategy → keeps propagating up). Hard terminal `dead` (e.g.
  `missing_parent_stub`) still propagates directly.
- `open_goals` uses a recursive CTE to filter out orphans under dead branches; `detached=1`
  (mint output, Strategist restart targets) is additionally unioned into the alive seed.
- Every Inject decision writes an outcome; when the whole batch has landed → enqueue
  Strategist `inject_batch_done` (batch_id immutable; completion derived from "all outcomes
  non-NULL").
- Preconditions for proved: see §10 axiom gates.

**The Problem layer has its own five-state FSM** (v29, `problems.state`): `active` /
`awaiting_human` / `ingest_signoff` / `ingested` / `revoked`. `WAKE_LEGALITY` only lets
`active` receive Strategist wakes (the rest are human-owned or terminal); sole mutator
`apply_problem_transition`; `revoked`
(un-proved after ingestion) is revived via `asterism revive`. "stalled" is deliberately not a
state but a derived guard on `active` — the machine has no legal resting state. Design SoT:
`docs/internal/problem_fsm_design.md`.

---

## 8. Sequential OR expansion (passive)

Each Goal runs only one Strategy at a time; the next is born only when it dies. Under strong
models, eager fanout is pure token waste; the cost is slower wall-clock when the first
strategy heads the wrong way, mitigated by SHELVE_THRESHOLD + showing the Formalizer
"what past dead decompositions tried". Each Strategy uses a strategy-isolated filename
(`_strategy_s<sid>.lean`,
theorem name `s<sid>` locked by the framework); the parent's `lean_path` is only changed when
Verify picks a winner. Sub-goal slugs
are agent-chosen descriptive names, unique per problem (`UNIQUE(problem, slug)`).

---

## 9. Dedupe (sub-goal equivalence sharing)

When the Formalizer splits out a new sub-goal, the framework uses a Lean kernel probe
(`apply @<canonical> <;> assumption`
in a single batch cold call) against the candidate pool: ancestor chain / sibling orphans /
cross-branch proved / same-problem disproved / reuse tier (open·attempting·shelved). On hit →
no INSERT;
`strategy_subgoals` links to the canonical, the file is written as an alias and
build-verified. Fail-open: if the probe
breaks, always treat as no-hit — never block the main flow.

Key points:

- **The alias mechanism is theorem-only** — data defs are never aliased (def-blind
  misjudgment fixed in `cbe5bc3`,
  soundness-adjacent).
- Hit on disproved → abort the whole batch ("a counterexample was already given, stop
  proposing this").
- The `no_progress` gatekeeper is a single-canonical apply probe: if a sub-goal can be
  discharged in one shot by the goal being split or an unproved
  ancestor of it → reject (the split achieved nothing).
- Three mint branches: hit on a same-problem alive/parked twin → **reuse** (the Inject is
  repointed to the existing goal, reviving/detaching as needed — no new row); hit on
  **proved** → land directly as an alias (the proposal becomes a citation); otherwise
  land normally. The cite-gate resolves aliases; proved aliases are citable.
- **G1 shelved-revival**: when mint lands a new goal X, probe in reverse "can X discharge
  some shelved S"; on hit, record the link first; once X is later proved, housekeeping
  backfills the alias body and S revives, flips to proved, and propagates up.

---

## 10. The axiom gate system

Principle (settled 2026-07-03): **`proved` is only marked after the axiom set has been
verified against the whitelist; re-verify after every high-risk rewrite**. The whitelist comes
from Manifest `axioms_whitelist`; when absent, framework default
(Classical.choice / propext / Quot.sound) + warning — **never skip because the field is
absent**.

| Gate | Location | What it guards |
|---|---|---|
| **pipeline exit gate** | `_axiom.axiom_gate`, shared by both Formalizer entries (prove/split leaf-bypass + mint) (own-slot, ~150ms) | Before any goal is marked proved, its proof's axiom set ⊆ whitelist (asserted by a structural lint test) |
| **root integrity gate** | When the root flips to proved (guarded by the `integrity_verified` marker, auto-cleared on flipping away from proved) | The single full elaboration of the whole alias chain; catches drift + escaped sorryAx, bisects the culprit + rollback and re-split |
| **Librarian migrate gate** | On each file moved into the Library | per-decl `#print axioms` ⊆ whitelist + import closure + Gate D def-equivalence; any `axiom` declaration is a hard-fail |
| **cleanup final re-gate** | After cleanup rewrites proof bodies | The same per-decl check re-run against the **final text** — LLM-rewritten sections (simplify / near-dup bridge / audit whole-file rewrite) are the only place after migrate where the axiom set can change |
| **bridge endgame gate** | End of the chain | classic: Gate B re-derives the root from the Library (statement-pin + axiom probe); deliverable: after cite_drop, per-decl axiom gate per file, PASS before bridge is marked complete (`problems.library_bridged_at`, v18) |

The verify-collapse design is unchanged: per-level `verify_strategy` is a purely mechanical
alias rewrite, no per-level
elaboration; the root gate's rollback is the correction net for a false-proved slipping past
mechanical verification (fires very rarely in practice,
but must not be removed — verify-collapse deliberately does not probe non-leaf promotes).

---

## 11. Code map

```
Tooling/
  core/       dispatcher.py (main loop + scheduling), librarian_sched.py (five-stage DAG scheduling),
              cli.py, config.py, quota_wait.py / usage_quota.py (quota),
              warmup.py (NL-first gateway warmup), process_group.py (Job Object)
  state/      db.py (schema DDL + query), db_migrations.py (full migration set),
              transitions.py (goal/strategy/problem state machines + ProvedReceipt + cascade_one),
              programme.py (Programme revision chain), manifest.py, proof_store.py (proofs/
              chokepoint), recovery.py (startup repair + orphan sweep), failures.py
              (failure-reason registry = machine SoT), thresholds.py, regress.py,
              consistency.py (drift-check predicates), kb.py / kb_ingest.py (lessons, Model B)
  pipeline/   backward.py / forward.py (the Formalizer's prove-split / mint entries),
              _intake.py (Formalizer intake gate), strategist.py, adversary.py (the Adversary),
              scholar.py (paper fetching),
              librarian/, _retry.py (session retry helper), _assembly.py,
              _axiom.py (shared axiom gate), _cite_gate.py, _presearch.py, _reflection.py,
              events.py, etc.
  quality/    verify.py (housekeeping + root gate), dedupe.py, prune.py, review.py,
              knowledge_stats.py, librarian/ (dedup/gates/inventory/relabel + cleanup/*)
  agent/      context.py / phase2_context.py (Context.md compilation), runtime.py (spawn +
              spawn_usage accounting), sandbox.py
  llm/        claude_cli.py (spawn + watchdog + sandbox flags), spawn_guard.py,
              gemini/openai backends
  lsp/        gateway.py (warm verify_file + validate_file + anchorClosure RPC),
              client.py, decl_oracle.py, lifecycle
  knowledge/  lemma search (loogle etc.)
  papers/     fetch / index / search / shelf (the Papers/ shelf)
  serve/      web console (`asterism serve`: star map, Engine view, chat explainer)
  prompts/    one folder per worker, multi-stage files (formalizer/{intake,formalize,mint},
              strategist/, adversary/, scholar/, librarian/, _shared/)
```

---

## 12. Context.md: the agent's sole interface

Before every spawn the framework compiles a Context.md from the DB — **everything the agent
sees comes from here** (companion
files are fallback only; agents often skip them). Compilation principles: must-see info
inline, curated not dumped; sections stable across spawns
(BRIEF, KB lessons) go first for prompt-cache hits. Lessons come from the DB `kb_entries`
(Model B: global-only, written by reflection, inlined every spawn, cap 25); when pre-search
is present, it injects
`## Candidate lemmas` and replaces the proved-siblings section. In research mode the
Programme's
`## Proof` is injected into worker context as the programme section (the NL-first premise);
bulky content goes to the
`CATALOG.md` / `PAPER_MAP.md` companions, inline keeps only index pointers. Full section
order in
`data-flow.md` §5.

---

## 13. Non-goals (what does not exist in this system, and why)

| Not done | Reason |
|---|---|
| A 'running' state in the pipelines table | Only finished rows are stored; no zombies left when the daemon dies |
| An active cancellation propagation table | The cascade entry no-op already passively catches OR losers |
| New worker_kinds such as Generalizer / Refuter | Still deferred (Scholar v23 and Formalizer v33 already demonstrated the kind-extension path) |
| Auto-pruning OR-losing strategy files | Blast radius too large (Jordan 2026-05-26); only auto-reconcile; prune is the operator opt-in `asterism prune` |
| An events-table audit log | dead_attempts.artifacts JSON + stdout suffice |
| Two-phase `commit_state` pending/live | backup-restore + `os.replace` is enough |

---

## 14. Invariants (read before modifying)

**Concurrency and state**
- State writes only go through `transitions` checked mutators; unregistered edges raise in CI
  (lint: raw `UPDATE …
  status` count ratchet guard)
- Cascade **propagation** only on the main thread (guarded by `assert_main_thread`); worker
  threads only do commit-time transitions on their own target
- **pipeline = slot**: verification during a pipeline's lifetime goes through its own claimed
  gateway slot
  (`_axiom.verify_on_own_slot`); borrowing is restricted to non-pipeline contexts, preferring
  unclaimed slots
- The `pipelines` table stores finished rows only
- worker_kind ↔ target_kind: Formalizer → Goal (prove/split) or Problem (mint),
  Strategist → Problem, Scholar → Problem, Librarian → Problem (per-file target
  `problem\x1ffile`); Verify is not a worker
- `problems.state` transitions only via `apply_problem_transition`; wakes only delivered to `active` (WAKE_LEGALITY)

**soundness**
- `proved` is only marked after `axiom_gate` passes; Library content re-verifies axioms after
  every high-risk rewrite (§10)
- The Library never admits an `axiom` declaration
- `proofs/` file mutations only via `proof_store` (atomic write + ownership guard; lint-guarded)

**Files and schema**
- `goals.lean_path` UNIQUE; `strategies.lean_path` not UNIQUE (multiple strategies share the parent target)
- Strategy `scratch_path` is write-once (may be empty at INSERT, backfilled once, then never changes)
- Sub-goal slugs unique per problem (`UNIQUE(problem, slug)`); strategy filename/theorem name `s<sid>` framework-locked
- `.attempts/<pid>/` unconditional rmtree; agent output packed into `dead_attempts.artifacts` first
- Schema changes must bump user_version + write a migration

**Group tree**
- Exactly one top-level group per problem (`parent_group_id IS NULL`, partial unique index);
  the top-level group is a real row, not a code special case
- "A live child group" as the third kind of in-flight product must be recognized
  **simultaneously** by `has_active_inflight_inject`
  (stall side) and `has_live_inflight_inject` (anti-idle side) (pinned by an invariant test;
  the two have diverged three times historically, each time a livelock/deadlock)
- The top-level group may not `ReturnToParent`; child groups may not `RequestUserAmend` (both rejected by the verifier)
- A child group's Ingest touches no `problems.ingested_at`/sign-off/harvest/problem FSM
- Group state transitions only via `groups.set_status`

**Strategist**
- ConfirmShelve and a goal-target Inject may not point at the same target or a descendant of it
- `strategist_decisions.batch_id` is immutable; completion derived from "all outcomes in the batch non-NULL"
- Mint output goals must be `detached=1`
- Non-exempt decision batches must carry a proposal package passed by the Adversary; the
  Programme revision chain has at most one passed per rev (v31)
- Deliverable problems must pass the `ingest_signoff` human sign-off before harvest
  (benchmark problems with `signoff: false`
  excepted)

**Processes**
- The daemon process tree is bound to a kill-on-close Job Object (parent dies, children auto-reclaimed)

---

The list of proved problems is not maintained in this doc — query the DB:
`origin='root' AND status='proved'`; the Library index is
`library_decls` + `problems.library_bridged_at` (INDEX.md retired since v18; the DB is the index).
