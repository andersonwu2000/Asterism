# Asterism — Data Flow

This doc covers **dynamics**: how one dispatcher tick runs, each pipeline's flow, and the
mechanisms shared across pipelines. Static shape (roles, invariants, schema) is in
`docs/architecture.md`; the full failure-vocabulary mapping lives **only** in
`docs/failure_modes.md` §2 and is not repeated here.

> Originally written 2026-05-06; fully rewritten against the code 2026-07-29 (Formalizer merge, research mode, constant corrections);
> 2026-08-02 added the discussion-group tree (v35, per-group seats); 2026-08-19 Manifest retired (v40: charter/word/settings are DB-resident).
> All numbers in this doc are **program defaults**; this repo's overrides live in `Asterism.yaml`, which is authoritative.

---

## 0. Read first: two global conventions

**Compile verification goes through the LSP gateway, not cold `lake build`.**
All pipelines' elaborate / build verification hits the resident LSP gateway warm workers (`lake serve`),
saving the 5–15s cold startup each time. A few exceptions are **deliberately** cold: dedupe's
apply/isDefEq probes, each problem's Defs/Root pre-flight before first dispatch, and the Librarian's
foreign-closure decl gate / final warn-gate / post-import-swap rebuild-gate
(warm slots only serve same-closure whole-file gates).

**`dispatch.pool == gateway workers`, 1:1 binding + own-slot discipline (#118).**
Worker pool size equals the gateway backend count and they scale together (actual slot count minus
the RAM clamp and the `gateway.interactive_slots` reserved for the serve UI). Each pipeline claims
one slot via `/register` before spawn; all verification during its lifetime hits
**its own slot** (`verify_in_session` with session token; shared dispatch lives in
`_axiom.verify_on_own_slot`, falling back to `verify_file` when there is no token). `verify_file` is
the **borrow** entry (gateway picks a slot, evicting that slot's warm content), reserved for
non-pipeline contexts: main-thread housekeeping (G1 revival, root integrity gate), operator CLI,
and pre-spawn framework probes (hint pre-pass, skeleton signature, pre-intake verification).
Borrow prefers unclaimed slots.

---

## 1. Three storage tiers

| Tier | Location | Lifetime | Purpose |
|---|---|---|---|
| **Ephemeral** | `.attempts/<pipeline_id>/` | one spawn | agent working dir; unconditionally `rmtree` on exit |
| **Cross-spawn** | `Problems/<p>/.drafts/<kind>_g<gid>.md` | until that goal is proved | progress notes left after a timeout for the next attempt |
| **Permanent** | DB + `proofs/L_*.lean` + `_strategy_s*.lean` + `Root.lean` | lives as long as the problem | single source of truth (SoT) |

Everything the agent writes into `.attempts/<pid>/` (success or not) is packed into
`dead_attempts.artifacts` before the `rmtree`. **The DB is always the SoT.**

---

## 2. One dispatcher tick

The main loop runs each tick in a fixed order:

| # | Step | What it does |
|---|---|---|
| 1 | **cascade** | Harvest the previous tick's completed pipeline outcomes, apply goal/strategy state transitions (details in `failure_modes.md` §2) |
| 2 | **verify housekeeping** | Assemble strategies whose sub-goals are all proved, write the alias into the parent; run shelved-revival (§4) |
| 3 | **post-proved gate** | Problems whose root just flipped proved: fix drift → root integrity verification → refresh TREE (end of §4) |
| 4 | **librarian refill** | Schedule Library-ization work for opt-in, already-Ingested problems (§3.5) |
| 5 | **exit check** | `all_problems_ingested` ∧ no Librarian backlog ∧ no outstanding harvest → daemon exits |
| 5b | **quota-wait gate** | Subscription quota confirmed exhausted → sleep until resets_at, pause all spawns (DB-side triggers still run; budget clock deducts the wait) |
| 6 | **bfs refill** | Open goals always enqueue `Formalizer`; those with `attempts ≥ SHELVE_THRESHOLD` go to strategist review instead, no dispatch |
| 7 | **strategist triggers** | Schedule routine (T1) / stall (T4) wakes; since v35 seats are **per-group** (`groups_needing_t1` / `groups_stalled`, queue rows `target_kind='Group'`; legacy Problem rows still recognized); wakes only delivered to `problems.state='active'` (WAKE_LEGALITY) |
| 7b | **reconcile_stuck_states** | Per-tick safety net: repairs orphaned pending_review / NULL-outcome Inject |
| 7c | **lease sweep** | Release leased queue rows whose owner is dead **or** past TTL (6h) (Windows reuses PIDs, hence both criteria) |
| 8 | **spawn** | While slots are free, pop the queue and dispatch pipelines into worker threads |

The tail of the tick also handles: `--once` exit, idle exit (no in-flight, empty queue, no open
goals, no ready strategies), periodic TREE.md redraw, budget-expiry exit. The daemon also detects
source/config fingerprint drift, drains, then spawns a successor daemon for handoff
(`dispatch.handoff_on_code_change`).

### Step 8 — spawn details

**Since v17, pop = lease claim**: the row is marked `owner_pid`+`leased_at` instead of deleted
(concurrent dispatchers can't grab the same row; leased rows still count as "in queue" for dedup
queries); only at pipeline end does `complete_queue_row` delete it. Pop / flush / startup cleanup
all filter by the daemon's `--scope`. **NL-first gate**: while the gateway is not yet warm, only
non-Lean kinds are popped (Strategist/Scholar go first, Lean work stays in the queue).

Between pop and spawn, in order:

1. 3-tuple `(target_id, kind, decision_id)` dedup (mint siblings in the same batch are distinguished by decision_id and may run in parallel)
2. Skip kinds in quota cooldown
3. Strategist rows for already-Ingested problems are dropped outright (stale)
4. **lazy verify gate**: on a problem's first dispatch in this daemon run, pay one `lake build Defs+Root` (~5–15s); on failure, quarantine
5. `pool.submit(_run_pipeline, ...)` into a worker thread

> Only four live queue kinds: `Strategist` / `Formalizer` / `Scholar` / `Librarian`.
> `Builder`/`Backward`/`Forward` are legacy row names from before the merge; the dispatcher still recognizes and routes them the same way.

---

## 3. Pipeline flows

### 3.0 Common skeleton

**One pipeline = the full lifecycle of one claude session** (including retries), housed in
`run_with_session_retries` in `Tooling/pipeline/_retry.py`. Five outcomes:
`proved` / `success` / `failed` / `exhausted` / `moot`.

**Entry**: pre-write the framework-locked files (§5) → **intake** (fresh short session writes `intake.json`:
proceed / decline; the only decline vocabulary is `no_nl_correspondence` and `unprovable`, the
latter must attach a counterexample note or fail-open lets it proceed) → only on proceed run
presearch + compile Context.md. The intake session is then resumed by the work loop
(continuation), nothing wasted.

**Retry loop (at most budget rounds; budget = SHELVE_THRESHOLD − goal.attempts)**

Each round first cascade re-checks (goal already terminal → `moot`), then spawns, branching on rc:

| rc | Meaning | Handling |
|---|---|---|
| 0 | normal return | `parse_fn` → return if terminal; non-terminal failure → buffer + warm resume next round |
| 124 | timeout (SIGKILL) | try one salvage parse; failing that, postmortem writes `.drafts/` → `exhausted` (§6.2) |
| 125 | stale session (warm only) | re-mint sid in place + cold re-spawn, no budget spent |
| 128 | thinking-trap watchdog | fresh-sid takeover continues, no budget spent (reason `agent_stuck_thinking`) |
| 129 | daemon shutdown | wrap up with reason `daemon_shutdown` |
| 126 / 127 / fast-fail | infra | early-return `failed`, no budget spent, not buffered (§6.3) |

**Wrap-up**: dispatcher writes the pipelines row → flushes the accumulated pending_failures (one
dead_attempt per entry) → `cascade_one` applies state transitions → clears `.attempts/`; only
successful outcomes clear `.drafts/`.

Easy to misread:

- **attempts++ is immediate** (at the moment each round fails); the dead_attempt row waits until
  flush. A daemon killed mid-run leaves attempts one higher (ledger drift, explicitly accepted).
- **`.drafts/` clearing depends on kind**: success tokens (`proved`/`success`) and `moot` clear it;
  `failed`/`exhausted` keep it for the next cold restart.

**Strategist Inject exception**: when the pipeline carries a `decision_id`, the budget gate is fully
bypassed (full budget, no attempts-cap check) — the Strategist saw the failure replay and still
gave the order; the framework does not second-guess. The only check kept: goal status already
terminal → `moot`. Convergence responsibility rests on the Strategist's ConfirmShelve discipline.

---

### 3.1 Formalizer — goal job (prove / split)

Decides for one goal between "prove directly" and "decompose"; the agent chooses autonomously
within the same session. OR-aware: each strategy uses an isolated filename (scratch
`_strategy_s<sid>.lean`, theorem name `s<sid>` framework-locked); the parent's `lean_path` is
untouched, rewritten only when a strategy wins at §4 Verify.

**hint pre-pass (zero spawns)**: when `goal.attempts == 0`, first swap the strategy skeleton's body
for a `by hint` probe — Lean runs the tactic set registered via mathlib's `register_hint`; on a hit
the named winner is written into `patch.lean` and goes through the **exact same** commit gate as an
agent patch; on a miss it falls silently into the normal flow.

**Entry**: INSERT a new strategy to get a fresh `s<sid>` (dead strategies are not reused) → compute
the skeleton from the parent stub (keep the declared kind, rename to `s<sid>`, body sorry; when the
signature cannot be extracted from the stub, rebuild it with the declInfo oracle's
`ppSignature`, and only failing that `parent_stub_not_decomposable`) → pre-write `patch.lean`.

**parse_fn (once per round)**:

1. bail detection: `_progress.md` has content + patch untouched + no `new_*.lean` → `agent_bailed`
2. glob `patch*.lean` → missing file `parse_proposal_fail`
3. file-top `-- decline:` branches: `unprovable` / `return_to_parent` / `shelve` / `needs_decomposition` / `no_nl_correspondence`
4. signature unmodified (compared against the skeleton) → otherwise `patch_signature_mismatch`
5. **leaf-bypass**: 0 `new_*.lean` files and body not sorry → treated as a 0-subgoal strategy: forbidden
   grep + single-file verify + axiom gate + race guard → commit if all pass
6. `forbidden_lemmas` grep (patch + all `new_*.lean`)
7. sub-goal slug validation (lowercase, ≤60 chars; name collisions auto-suffix)
8. **dedupe**: batch probe `apply @<canonical> <;> assumption` against the candidate pool (ancestors /
   sibling orphans / cross-branch proved / same-problem disproved), preceded by a slug-pattern
   pre-check and a no-progress guard. Hit on alive → write alias and build-verify (on failure fall back to opening a new sub-goal);
   hit on disproved → abort the whole batch
9. Move files to `proofs/` + auto-inject imports (agents often forget)
10. cite gate (the decomp path allows auto-link to absorb parallelizable open siblings)
11. scratch must not retain sorry → `patch_body_contains_sorry`
12. `verify_file` batch (subs + scratch) → on failure unlink + `lake_build_error`
13. race guard: goal no longer open/attempting → unlink + `goal_no_longer_open`
14. INSERT goals + strategy_subgoals; sorry-free / dedupe-hit subs go straight to proved
15. UPDATE strategy → `outcome='success'`

On exit, `outcome != 'success'` → strategy marked dead (infra reasons or empty rows are DELETEd
outright). Cascade semantics of each failure_reason: `failure_modes.md` §2.

---

### 3.2 Formalizer — mint job

Dispatched by the Strategist via a targetless `Inject` (shape-derived); produces one new toolkit
lemma into the pool. `target_kind='Problem'`; multiple mints in one batch are distinguished by
decision_id and may run in parallel. Lemma kinds:
`theorem` / `def` / `structure` / `class` / `inductive` / `instance` (named).

Flow (`forward.py`; retry budget = `FORWARD_RETRY_BUDGET`):

1. LSP edit-mode against the **fixed file** `new_forward.lean` (framework pre-writes the seed scaffold); the agent edits in place
2. intake same as the goal job (two decline vocab words); work-turn decline `-- decline: library_sufficient` → `agent_declined` terminal
3. `extract_forward_metadata`: slug / rationale / kind / sorry_free; missing fields or unrecognized kind → `parse_rejected`; `inductive` carrying sorry rejected outright
4. auto-prepend imports → self_verify (`verify_file` probe; build error → `forward_no_new_goal` + retry_context)
5. **Defs vocabulary protection**: a non-theorem kind whose slug collides with charter statement vocabulary → reject, steer toward `RequestUserAmend(Defs.lean)`
6. sorry-bearing with no type annotation → declInfo oracle fills in the signature, reject only when it can't
7. **dedupe, three branches**: same-problem alive/parked twin → `reuse` (Inject repointed to the existing goal; cascade-shelved ones revived + detached, no new row); hit on proved → land an alias; otherwise commit normally
8. `commit_forward_lemma`: move to `proofs/L_<slug>.lean` + INSERT goal (sorry_free → proved, else open; always `detached=1`)
9. shelved_link (G1): reverse-probe same-problem shelved goals; on a hit record the link now, §4 writes the alias once X is proved
10. Unconditionally backfill the decision's `produced_goal_id`; when proved, propagate the inject outcome directly

Failures touch no goal's attempts (mint is goal-less); infra failures re-enqueue the same
decision_id. Two lines of defense against junk proposals: dedupe blocks duplicates, and the
Strategist adjusts its briefs from the results in the failure replay.

---

### 3.3 Strategist

`target_kind='Group'` (since v35 seats belong to **groups**; legacy `Problem` rows still
recognized, mapped to the top-level group).
**Three triggers** (determined at spawn time, priority routine > inject_batch_done > pending_review >
stall):

| trigger | When |
|---|---|
| `routine` | ≥ `strategist.interval_min` since the last routine commit (default 120 min; clock lives in `groups.last_routine_at`, per-group; the legacy problem-level clock is dual-written, slated for retirement at Stage D). The wake's first phase runs a belief audit |
| `inject_batch_done` | All outcomes of some batch (Inject/Delegate share one batch ledger) have landed; **or the group is in structural stall at spawn time** (fresh group / deadlock / root proved awaiting Ingest all count as "empty batch done"; wall-state detection is per-group, `is_group_stalled`) |
| `pending_review` | A goal turns `pending_strategist_review` (decline escalation or attempts threshold); routed to **the group owning that goal** |

All wakes first pass `problem_accepts_wake`: any `problems.state` other than `active` is refused.
Multiple groups of the same problem can each hold a seat; `_strategist_inflight` dedups per group.

**Proposal package + Adversary loop** (research mode, always on):

1. spawn produces `decision.json` (JSON array) + non-exempt batches must attach `proposal.md` (`# Title` /
   `## Argument` / `## Proof` / `## Roadmap`; exempt kinds = {FetchPaper, RequestUserAmend,
   Noop}; non-endgame batches must include ≥1 experiment = Inject / AttemptDisproof)
2. Mechanical checks (schema, cross-decision invariants, package shape) fail → revise in the same session
3. Past mechanical checks → **Adversary**: each round a fresh sub-spawn reviews the proposal
   package in a hard-isolated projection directory and produces per-criterion `verdict.json`;
   pass/rebut is derived by the framework; rebut → revise in the same session with the critique
4. Mechanical errors and rebuttals **share** the round cap `strategist.verify_retry` (default 6);
   still rebutted at the cap → `strategist_proposal_rejected`: proposal + critique stored in
   `programme_revisions` (status='rejected'), session discarded, the next wake carries only a
   one-line record for a blind re-derivation, target cooldown
5. Pass → commit the decision batch + `programme.record_pass` (redraws `PROGRAMME.md`)

**commit_decisions side effects** (nine decision kinds):

| decision | Action |
|---|---|
| `Inject` (no target) | enqueue mint (Formalizer/Problem) + decision row (writes batch_id) |
| `Inject` (with target) | force reopen + detach when needed + un-stall the upstream strategy + enqueue Formalizer |
| `ConfirmShelve` | goal terminal(shelved) + propagate |
| `EmitDirective` | set the problem's standing directive |
| `RequestUserAmend` | write `.proposed_<file>` + problem transitions to `awaiting_human` |
| `MarkDeliverable` | mark a deliverable (anchor+claim) |
| `Ingest` | **Top-level group**: stamps `ingested_at` (the only terminal state; refused by the framework if a root is present but not proved); library:true additionally goes through sign-off/harvest. **Sub-group**: lightweight — group marked `delivered`, wakes the parent group, touches no sign-off/harvest/problem FSM; gate = anchor proved (rescue shape) or ≥1 deliverable marked by this group (anchorless shape) |
| `FetchPaper` | enqueue Scholar (payload carries query/reason; outcome backfilled by Scholar) |
| `AttemptDisproof` | the framework **mechanically** performs the negation surgery to mint the ¬P goal (the LLM never rewrites the statement — anti-strawman) |
| `Delegate` | INSERT a new group (charter=brief) + immediately schedule the new group's seat; with a target, the anchor turns `attempting`. Outcome stays NULL until the sub-group reaches a terminal state — shares the batch ledger with same-batch Injects; the parent group wakes only when all are terminal |
| `ReturnToParent` | sub-group only: group marked `returned`, rescue anchor lands `shelved` (with cascade), parent's Delegate outcome=`failed:returned`, wakes the parent group |
| `Noop` | only INSERTs an audit row |

Wrap-up: the batch layer touches `last_strategist_at` (routine additionally touches `last_routine_at`,
which is what re-arms the clock); routine wakes may also add/edit global lessons via the
`kb_curation.json` sidecar (cap 10 ops).

---

### 3.4 Scholar

Single-stage spawn dispatched by a `FetchPaper` decision: uses `Tooling.papers.search` / `papers.fetch`
to find a copy from whitelisted sources; success → paper lands in `Papers/<shelf-id>/` + bound via `problem_papers` (`paper_fetched`);
no fetchable copy → `paper_unfetchable`, with the precise request written into the decision's `outcome_detail` for the human channel.

---

### 3.5 Librarian

Harvests proved problems into mathlib-shaped `Library/`. Auto-start condition: the problem's `library: true` setting ∧
Ingested ∧ no harvest artifacts yet; while sign-off is pending, all automatic paths pause.

Chained `dedup → classify → migrate → cleanup → bridge`; the work-kind is derived from the
`library_decls` lifecycle, re-derived at the tick layer after each success until drained.
`migrate`/`cleanup` parallelize with whole files as the unit.

| Step | Form | What it does |
|---|---|---|
| **dedup** | purely mechanical | Narrow to the live usage closure of the harvest targets, mark `keep → deduped` |
| **classify** | one-shot JSON spawn | agent proposes file layout + order; framework corrects via SCC-merge + toposort |
| **migrate** | LSP + commit-retry | write the whole file's decls at once → commit gate → `migrated` |
| **cleanup** | multi-stage LLM + mechanical wrap-up | per-file refinement (drop/merge/simplify/audit/rename/import-min); zero-warning hard gate + post-rewrite axiom gate → `cleaned`/`dropped` |
| **bridge** | no agent | Gate B whole-meaning verification; PASS backfills signatures + stamps `library_bridged_at`, ends the chain |

**commit gate (every migrate; shared by the cleanup wrap-up and the deliverable bridge)**: Gate A import
closure ⊆ {Mathlib, Library, Init, Std, Batteries, Lean}; whole file 0 errors 0 sorry; per-decl
`#print axioms` ⊆ whitelist; Gate D checks `rfl` def-equivalence for `def`s; any `axiom` declaration
hard-fails. Failure rolls back and the chain sticks at that file; consecutive failures beyond `LIBRARIAN_MAX_CHAIN_RETRIES`
(=2, i.e. the 3rd) → STALLED.

**post-rewrite axiom gate (cleanup wrap-up)**: cleanup's LLM rewrite stage is the only place after
the migrate gate that can change the axiom set (e.g. `by native_decide` pulls in `Lean.ofReduceBool`);
the wrap-up reruns the per-decl axiom check against the **final text**; failure → `librarian_axiom_violation`, the file stays `migrated` for retry.

**Gate B (bridge, the "linchpin")**: re-derive the original root from the Library (Defs-free):
statement-pin + import closure + build + axiom whitelist. Marker present = the Library can genuinely
re-prove the original problem. Deliverable problems (no root to re-derive) instead get: builds-only + the
per-decl axiom gate on each harvested file's final text.

> Three gates: **A** import closure, **B** root re-derivation, **D** def-equivalence. There is no Gate C.

---

## 4. Verify housekeeping

Runs after cascade each tick, **pure framework, no LLM, single-threaded**. Each iteration fetches
two kinds of pending work (at most `max_iters=8` iterations):

- **ready strategies**: `proposed` ∧ non-empty scratch ∧ parent not terminal ∧ all sub-goals proved
- **revivals (G1)**: shelved goal S with `alias_target_id = X` and X now proved

**For each ready strategy**: atomically rewrite the parent `.lean` into an alias (import strategy module +
`def <parent_slug> := @...s<sid>`; the locked signature guarantees type match, pure string templating) → strategy
`succeeded`, parent `proved` (optimistic), siblings `superseded` → background olean warm-up
(`OleanWarmer` runs the cold build on its own thread, occupying neither the main thread nor the LLM pool; kill switch
`verify.olean_warm`). The parent may itself be a higher-level sub-goal, picked up by the chain on the next iteration.

**For each revival (S, X)**: S's sorry body is rewritten to `apply <X> <;> assumption` + build-verify
(on failure restore, stays shelved) → S turns proved + propagate.

### Root integrity gate (the core of §2 step 3)

After root flips proved, run the single integrity gate: `axiom_probe(Problems.<p>.main)` (900s cap,
the only full elaboration), catching both alias-chain drift and escaped sorryAx.

- **happy path**: `set_integrity_verified(1)` + clear cascade backups. Writes no Library files, does not exit the
  daemon (Library-ization and exit are each decided by §2 steps 4/5).
- **rogue sorryAx**: `bisect_sorryax_source` finds the culprit strategy → `rollback_cascade_chain`
  restores level by level (root drops out of proved; next tick re-decomposes the culprit); if the problem was already Ingested → automatic revocation + Librarian
  un-harvest, fully automatic takedown.

> Empirically 41+ cascade verifies with 0 interceptions — hence per-level verify is a purely mechanical alias rewrite with no per-level
> elaboration; the root gate is the last correction net for false-proved, rarely fires in practice but must not be removed.

---

## 5. Pre-spawn preparation

### Context.md compilation

Before each spawn the framework compiles a `Context.md` from the DB. **Everything the agent sees comes from here** (companion files
are only fallback). Three compilers: `compile_context` (Formalizer goal job),
`compile_forward_context` (mint), `compile_strategist_context`. Inapplicable sections are omitted entirely.

**goal job** (`compile_context`), top to bottom: BRIEF inline → KB lessons (invariant across spawns,
put first for the prompt cache) → paper index → **Programme `## Proof`** (the NL-first premise) →
directive → Strategist brief (on Inject) → goal statement → Library available →
strategy naming → parent goal & strategy → mathlib lemmas (past lake errors) →
Candidate lemmas (pre-search; when present, replaces the proved-siblings section) → **catalog pointer** (exact
statements in the `CATALOG.md` companion) → previous progress note / previous patch → Goal history
(umbrella, 4 sub-sections; projection logic in `pipeline/events.py`, design history in
`docs/archive/design/goal_history_unified.md`).

**mint** (`compile_forward_context`): brief → Library inventory → past mint proposals →
active goals → charter (+ user word) → paper index. (No TREE, **no Programme section**.)

**Strategist** (`compile_strategist_context`): trigger → (pending_review only: failure
replay / existing strategies / ancestor chain) → stall warning + Ingest availability →
disproof guidance → **Programme** (current rev full text + Adversary reservations + one line for the last rejection)
→ directive → plan note (`.drafts/strategist_plan.md`, private notes) → completed Inject
batches (with landed decl names) → pending reopen-promises → active goals → recent decisions →
TREE → catalog → "## Your charter" (own charter inline at every depth; the top group also
gets a Defs.lean preview) → "## The user's word" → (routine only: KB curation surface).

### Sandbox

agent cwd locked to problem_dir:

- **`--add-dir`**: problem_dir, attempts_dir, `.lake/packages/`, `Library/`, `Papers/`
  (each when present). **Adversary exception: all cleared**, trust boundary reduced to the projection directory
- **Read forbidden**: other `Problems/<...>/`; operator state (`~/.claude/projects/**` deny +
  auto-memory off + `spawn_guard` PreToolUse whitelist hook)
- **Tools**: `Read` / `Write` / `Edit` / `Grep` / `Bash`, Bash whitelisted to only
  `python -m Tooling.knowledge.loogle` and `python -m json.tool` (Scholar additionally gets
  `papers.search` / `papers.fetch`; spawn env injects the repo root into `PYTHONPATH`); LSP MCP
  tools (apply_edit / goal_at / errors_at / validate_file)
- **spawn flags**: `--setting-sources ""` (CLAUDE.md never loaded); user/framework files
  (problem.json/Defs/Root/PROGRAMME) fully disallowed for Write+Edit

### Pre-written framework-locked files

| job | Pre-written |
|---|---|
| Formalizer goal job | `patch.lean` = strategy skeleton (signature locked, agent edits body only) |
| Formalizer mint | `new_forward.lean` seed scaffold (imports + namespace, edited in place) |
| Strategist | no patch; outputs `decision.json` (+ `proposal.md`) |

---

## 6. Post-spawn failure / interruption handling

### 6.1 Ordinary failure retry

(build failure, forbidden_lemma, missing annotation, etc.) The helper buffers a snapshot into
pending_failures, extracts stderr into detail, and the next round warm-resumes with retry_context. Budget exhausted →
`exhausted`. Ordinary failures **do not write `.drafts/`** — session memory + retry_context are already the continuation medium.

**Reflection callback**: after the helper finishes (success, exhausted, or a decline directive), a
second claude is spawned on the same thread (`--resume`, 120s cap) to write a one-line lesson about this pipeline into
`LESSONS.md`. Best-effort, not triggered on infra failures, kill switch `lessons.reflection_enabled`.
There is also an independent framework feedback tail step (`feedback.enabled`) and an infra death-note channel.

### 6.2 Timeout (rc=124)

The main spawn exceeds `dispatch.spawn_timeout_sec` (default 900s) and gets SIGKILL. Handling order:

1. **salvage parse**: the agent may already have left valid output on disk — run `parse_fn` once; a
   terminal success/decline is collected as usual (a timeout can still count as success)
2. salvage fails and the watchdog rules a thinking trap → fresh-sid takeover continues (no exhaust)
3. otherwise **postmortem**: `claude --resume` + short prompt (180s cap) "write down your direction/blockers
   in 150 words" saved to `_progress.md` → copied to `.drafts/<kind>_g<gid>.md` → `exhausted` (no further retry)

The next dispatch (fresh pipeline) inlines it into Context as "## Your previous progress note".

> Why timeout forces exhaust: the thinking path is stuck; resuming the same session would hit the same wall. `.drafts/`
> exists precisely for the cold restart. If the postmortem itself dies, it's only a best-effort loss.

### 6.3 Infra noise (no budget spent, no dead_attempt written)

Five `PROVIDER_INFRA_REASONS`:

| reason | Trigger | Handling |
|---|---|---|
| `spawn_fast_fail` | rc≠0 and wall-clock < 10s | 30s target cooldown; 10 in a row → ask the usage endpoint first, switch to quota-wait if quota is confirmed, else daemon exits rc=2 |
| `quota_exhausted` | rc=126 | **per-kind exponential backoff** (30s×2ⁿ, cap 600s) + flush same-kind queue + may enter quota-wait |
| `missing_dep` | rc=127 (CLI missing) | 30s cooldown, operator-fix |
| `gateway_unreachable` | HTTP transport lost | 30s cooldown; 8 in a row → daemon exits rc=2 |
| `transient_timeout` | RPC timeout (slot contention) | 30s cooldown, **enters no CONSEC counter** (healthy overload, not death) |

During cooldown, bfs_refill skips that (target, kind); `.attempts/<pid>/_spawn.stderr` is kept for forensics.

---

## 7. Key constants (program defaults; overrides in `Asterism.yaml`)

| Constant | Default | Source |
|---|---|---|
| `dispatch.pool` (= gateway workers) | 4 | config.py (also subject to the RAM clamp and interactive_slots deduction) |
| `SHELVE_THRESHOLD` | 8 | `dispatch.shelve_threshold` (at threshold goes to strategist review, no longer auto-shelves) |
| main spawn hard cap (SIGKILL) | 900s | `dispatch.spawn_timeout_sec` / `WORKER_TIMEOUT_SEC` |
| intake short-turn cap | 300s | `dispatch.intake_timeout_sec` |
| Strategist wake hard cap | 10800s | `strategist.timeout_sec` (hang guard) |
| Adversary round cap | 7200s | `adversary.timeout_sec` |
| postmortem / reflection cap | 180s / 120s | `POSTMORTEM_TIMEOUT_SEC` / `_REFLECTION_TIMEOUT_SEC` |
| spawn_fast_fail threshold | 10s | `SPAWN_FAST_FAIL_SEC` |
| spawn cooldown / quota backoff | 30s / 30s×2ⁿ cap 600s | `SPAWN_COOLDOWN_SEC` / `QUOTA_BACKOFF_*` |
| consecutive fast-fail / gateway-loss caps | 10 / 8 | `CONSEC_*_LIMIT` (daemon exits rc=2) |
| queue lease TTL | 6h | `LEASE_TTL_SEC` |
| Strategist routine interval | 120 min | `strategist.interval_min` |
| Strategist verify/Adversary revision rounds | 6 | `strategist.verify_retry` |
| mint retry budget | 3 | `FORWARD_RETRY_BUDGET` |
| verify housekeeping iteration cap | 8 | `max_iters` |
| Librarian chain retry cap | 2 (STALL on the 3rd) | `LIBRARIAN_MAX_CHAIN_RETRIES` |

---

## 8. Design trade-offs quick reference

| Decision | Why |
|---|---|
| Must-see info inlined in Context.md, companions only fallback | Lesson: agents don't proactively read companions |
| Timeout goes to postmortem, not save-as-you-think | The main task isn't distracted by deliverable upkeep |
| Pipeline = session lifecycle, retry folded inside the pipeline | sid is a local var, nothing carries across pipelines |
| Compilation unified through the LSP gateway | Saves the 5–15s cold startup each time |
| Verify inline, occupies no worker slot; verify-time LLM repair dropped | Pure framework operation; LLM repair empirically fired 0 times |
| Builder/Backward/Forward merged into Formalizer | Prove/split is one judgment; separate kinds caused routing hacks and context breaks |
| OR passive (cap=1), no eager fanout | Pure token waste under strong models |
| Dedupe uses apply-probe | Lean understands α/β/η/defeq; string comparison has a low hit rate |
| hint pre-pass + write back the named winner | Taps mathlib's curated set; the artifact keeps the named tactic |
| Infra failures don't count as agent errors | Don't burn goal budget |
| Proposal package must pass the Adversary before commit | Between task and action there must be a reviewed full argument (research mode) |

---

## 9. Cross-references

- Static shape (roles, invariants, schema): `docs/architecture.md`
- Full failure reason × trigger × cascade × event mapping: `docs/failure_modes.md` §2
- Goal history umbrella design history: `docs/archive/design/goal_history_unified.md`
