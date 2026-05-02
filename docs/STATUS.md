# Asterism v2 — Current Status

Updated 2026-05-02 (post-F41/F43/F44 batch). Compaction-safe handoff note.

## Live test queued (post-compact action item)

**Re-run compactness with Sonnet, 2hr+ budget, to quantify combined
F41/F43/F44 effect.**

Setup already in place:
- `Problems/compactness/Manifest.md` carries verified-easy 4-sub root
  decomposition hint (commit `ed877a3`). Sonnet's first Backward
  followed it verbatim in the prior run.
- `Asterism.yaml` has `dispatch.pool: 12` set.
- Daemon currently NOT running. Compactness DB state from prior run
  is stale-leftover; reset before launching:
  `python -m Tooling.cli reset compactness && python -m Tooling.cli init compactness`.
- Launch: `ASTERISM_BUDGET_SEC=7200 python -m Tooling.cli run`.

What to measure (compare to last run @ commit `f98c473`):
- Total wall-clock to root proved (last run hit 95min budget without
  proving root)
- Verify failure count vs Verify-retry success count
  (`SELECT failure_reason, count(*) FROM dead_attempts WHERE target_kind='Strategy'`
  + grep daemon log for `[verify_retry] strategy=...`)
- Wandering Read counts (parse session jsonls for absolute-path Reads
  pointing outside the active Problem)
- Total cascade count (proxy for re-Backward thrash)

> **Operator workflow** — see `docs/OPERATOR.md` for CLI subcommands,
> `Asterism.yaml` schema, recurring traps. Kept under `docs/` so solver
> agents (claude / gemini subprocesses) don't auto-load it.

> **User preferences** are in the operator's global memory, not here.

## Proved problems

| Problem | Commit | Prover | Wall-clock | Axioms |
|---------|--------|--------|-----------|--------|
| wilson | 9c2c2a0 | Haiku | 39.5 min | propext, Classical.choice, Quot.sound |
| wilson (Sonnet) | 6b0cf3b | Sonnet | ~15 min | propext, Classical.choice, Quot.sound |
| compactness | 46c8941 | Sonnet | ~60 min | propext, Classical.choice, Quot.sound |
| cantor | 6bd6c15 | Sonnet | ~5 min | [] (constructive) |
| gen_generates | 4c6f423 | Sonnet | ~30 min | propext, Quot.sound |

Latest regression check (post-F35/F36): wilson re-proved by Sonnet in 15.7 min,
axioms identical to baseline.

## Ablations / dead ends (don't re-investigate)

- Wilson core `(↑(p-1)! : ZMod p) = -1` is single-step — Sonnet only closes
  via `Nat.prime_iff_fac_equiv_neg_one` (Mathlib helper, not in
  Manifest's forbidden_lemmas). When Sonnet recalls the name, wilson
  finishes in ~15 min; otherwise no decomposition helps because the
  sub-goal IS the parent's hardest step. baseline `6b0cf3b`'s "fast"
  wilson WAS this shortcut.
- F27 `--tools` trim is NOT the cause of the wilson Sonnet regression
  (verified by `ASTERISM_CLAUDE_TOOLS=default` ablation).
- **F40** Two-phase Builder delivery (`ASTERISM_BUILDER_TWO_PHASE=1`,
  commit `2b6ff1a` reverted at `232a3e0`). Hypothesis: weak models miss
  the patch.lean deliverable. Empirics on wilson + Haiku Builder + Sonnet
  Backward: 18 Builder pipelines / 30 min, 3 succeeded, 15 failed, of
  which **11 lake_build_error** (Phase B wrote a patch but Lean rejected
  it — hallucinated lemmas, wrong tactics, syntax errors) vs only **4
  phase_a_no_proposal**. PROPOSAL content was fine; patch quality is the
  bottleneck. F40 doesn't lift Lean reasoning quality. Don't reintroduce
  unless a model's dominant fail mode is documented as deliverable miss.
  Gemini path unverified (quota exhausted on first dispatch).
- **F31 substring tier** (`if "haiku" in model: ...`) retired together
  with the `Asterism.yaml` introduction. Brittle by design (vendor
  naming drift). Weak-tier projects now write `dispatch.builder_threshold:
  5` + `shelve_threshold: 10` in `Asterism.yaml` explicitly.

## Architectural delta this session (2026-05-02 batch)

Driven by compactness telemetry on the prior run + a Manifest-hint experiment:

- **Manifest hint mechanism** verified (commit `ed877a3`). Adding a
  `### Recommended root decomposition` block under `## Strategic notes`
  in Manifest.md steers Sonnet's Backward to follow the suggested 4-sub
  shape verbatim. Useful when the operator knows a tractable proof
  structure (e.g. baseline reproductions). Does NOT generalize to true
  conjectures where no ground-truth decomp exists — see F41 below.
- **Per-Problem TREE.md** (commit `5b3489c`). Every cascade auto-writes
  `Problems/<p>/TREE.md` with the AND/OR proof tree (slug-named, dead
  strategies annotated with cause). Replaces `python -c 'import sqlite3; ...'`
  inspection during runs.
- **F43 Inline PAST_*.md** (commit `db37bee`). Telemetry showed Sonnet
  Read PAST_VERIFIES.md zero times across 59 sessions despite the
  prompt pointer — so re-Backward never learned from prior Verify
  failures, and the same type-drift kept recurring. Switched to
  framework-driven eager inlining; kind-asymmetric (Builder gets
  PAST_ATTEMPTS only, Backward gets PAST_VERIFIES only).
- **F44 cwd → problem_dir** (commit `d4f9321`). Soft-sandbox the agent's
  cognitive frame to the active Problem. Doesn't enforce reads (claude
  CLI's `--add-dir` doesn't), but reduces wandering reads to other
  Problems / workspace files. Effect uncertain ahead of time;
  measurable post-compactness rerun.
- **F41 Verify-time patch retry** (commit `7f7f293`). When Verify Step 1
  lake build fails (the dominant type-drift trigger), one cold LLM call
  rewrites ONLY the strategy patch with sub-goal proofs as fixed
  reference. On success, Verify continues to Step 2 saving every
  sub-goal's prove cost; on failure, restore + standard cascade. Off
  via `ASTERISM_VERIFY_RETRY=0`.
- **`asterism reset` pipelines bug** (commit `141a5e2`). Reset was
  leaking pipeline rows pointing to deleted goals/strategies. Fixed.
  Surfaced during F41 investigation (looked like a dead_attempt
  recording bug at first).

## Recent commits

| Commit | Topic |
|---|---|
| 7f7f293 | F41 — Verify-time patch retry (one-shot LLM repair) |
| 141a5e2 | Fix asterism reset leaking stale pipelines table rows |
| d4f9321 | F44 — anchor agent cwd at problem_dir (soft sandbox) |
| db37bee | F43 — inline PAST_ATTEMPTS / PAST_VERIFIES into Context.md |
| ed877a3 | compactness Manifest hint (verified-easy 4-sub root decomp) |
| b2a706b | STATUS: bump test count |
| b1072ce | Revert STATUS F41 prose entry (task tracker is canonical) |
| 5b3489c | Per-Problem TREE.md auto-rendered on every cascade |
| f98c473 | Asterism.yaml: drop redundant Examples block |
| 8922cc2 | Move CLAUDE.md → docs/OPERATOR.md (out of solver agent auto-load) |
| 6123dab | OPERATOR.md: trim narrative |
| 655d907 | (was) CLAUDE.md — operator notes (see 8922cc2 rename) |
| b64f58f | asterism doctor — pre-flight diagnostic |
| d7af009 | Asterism.yaml + 4-step resolution chain; retire haiku-substring tier |
| 44385dd | asterism reset / status — replace ad-hoc per-Problem ops |
| e63932c | STATUS: F40 ablation conclusion + uuid sub-fix |
| 232a3e0 | Revert "[F40] Two-phase Builder delivery (opt-in)" |
| a4bbeb5 | Fix F33 cold-spawn rc=1: --session-id requires dashed UUID |
| 4710987 | F39 — per-pipeline provider/model selection |
| 382e23c | Provider-neutral failure_detail + dispatcher worker-exception recovery |
| 5a0ed10 | F38 — Gemini CLI provider via Code Assist free tier |
| 49a848a | F37 — OR-parallel → passive sequential strategy retry |
| 945c8d4 | F33 follow-up: inline retry error in prompt |
| 46c73c9 | F33 — same-session Builder retry |
| 2c541aa | Reorder Context.md sections |
| a7cb787 | F36 — restore proof-sketch latitude |
| 433d87d | F35 — lemma_lookup `@`-prefix parser |
| 7db1603 | F34 — expand TACTIC_TRY_LIST |
| d1bd0ff | F32 — strip lake noise |
| 83304d7 | F31 — model-aware thresholds (later retired) |
| 531dedd | F28 — daemon log auto-path |
| 1933c83 | F30 — companion file smart_truncate |
| af3f575 | F29 — PROPOSAL anti-fluff (partially reverted) |
| 0091561 | F27 — CLI flag trim |
| 1ec26ec | F26 — lazy-load Context.md |
| a7caf1a | F15 — Root.lean lifecycle |

## Next pending

- **#227 F10**: Sonnet + Dedupe v4 live-validation. v4 is verified safe
  after F14 but doesn't fire on wilson / compactness (max depth 2-3, no
  ancestor reuse). Either retire as "validated safe" or wait for a
  deeper-recursion problem.
- **#254 F42**: Cross-strategy sub-goal reuse — broaden dedupe beyond
  strict ancestors. dead strategy's proved sub-goals currently invisible
  to new strategies on the same parent. Compactness prior run lost
  ~20 proved sub-goals to orphans when strategy 15 cascade-died.
- **#250 F38 live smoke**: Gemini provider live test on cantor (~5 min)
  pending Gemini quota reset.
- **MODEL_TIERS doc** (deferred per user) — per-model recommended
  thresholds as a doc table, not a runtime lookup.

## Test count

409 unit tests + 2 lake-integration tests (skipped if `lake` missing).
All green at HEAD.
