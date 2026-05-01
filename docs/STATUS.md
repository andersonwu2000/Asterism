# Asterism v2 — Current Status

Updated 2026-05-02. Compaction-safe handoff note.

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

## Recent commits

| Commit | Topic |
|---|---|
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
- **F37 follow-up regression**: wilson Sonnet + Haiku must still prove.
  Sonnet baseline 15.7 min; Haiku baseline 39.5 min.
- **#250 F38 live smoke**: Gemini provider live test on cantor (~5 min)
  pending Gemini quota reset.
- **MODEL_TIERS doc** (deferred per user) — per-model recommended
  thresholds as a doc table, not a runtime lookup.
- **Verify-failed-with-all-subs-proved** (observed 2026-05-02 on
  compactness, multiple strategies — s19 / s24 / s26 / s28 / s30 all
  died this way). Sub-goals individually `proved` (lake build OK in
  isolation), but `_strategy_sNN.lean` patch fails its Verify lake
  build with errors like `typeclass instance problem is stuck
  Membership (PropForm α) ?m.2`. Cause: LLM-written lemma signatures
  in sub-goals are alpha-equivalent but not implicit/typeclass-
  identical to what the parent strategy's combining tactics expected;
  Lean elaborator's stricter unification at composition time rejects
  them. F12 cascade currently retries via `goal.attempts++ → re-Backward
  decompose`, which is correct but expensive (re-prove all sub-goals).
  Cheaper directions to evaluate: (a) Verify-time patch retry — feed
  proved sub-goal signatures back to LLM to rewrite ONLY the strategy
  patch without redoing sub-goals; (b) Backward signature lock —
  pin sub-goal type signature explicitly so Builder can't drift;
  (c) Don't try to fix — gather more samples and confirm prevalence
  before designing. Track failure_reason='lake_build_error' rows on
  Strategy targets across runs to estimate cost.

## Test count

392 unit tests + 2 lake-integration tests (skipped if `lake` missing).
All green at HEAD.
