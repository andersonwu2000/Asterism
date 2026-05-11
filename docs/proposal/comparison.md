# Asterism vs other LLM theorem provers — landscape

Honest positioning. Asterism is **architecturally** distinct from
existing systems; on **benchmark numbers** it has not yet been
evaluated. The proposal is to close the benchmark gap while preserving
the architectural advantages.

## Architecture comparison

| System | Year | Strategy | Decomposition | Model layer | Engineering posture |
|---|---|---|---|---|---|
| LeanDojo / ReProver | 2023 | Single-tactic prediction + premise retrieval | None — flat tactic predictor | Trained T5 + BM25 / dense retrieval | Research code; large public benchmark |
| Sagredo (Gowers + Anthropic) | 2024 | Multi-turn interactive Lean ↔ Claude | None — conversational refinement | Claude (no fine-tune) | Demo; not framework |
| DeepSeek-Prover V2 | 2024 | Recursive subgoal proof + MCTS | Model emits subgoals + recurses on itself | Custom trained model | Production-quality release |
| **Asterism** | 2026 | Multi-agent cascade decomposition | Backward (Opus) decomposes; Builder (Sonnet) closes leaves | Claude API; framework agnostic | Production engineering (gateway crash recovery, sandbox, circuit breaker, axiom probe) |

## Where Asterism is genuinely different

| Aspect | Asterism | Others |
|---|---|---|
| Multi-agent specialization | Backward (decompose) + Builder (close leaf) — distinct models | One model, all roles |
| OR-parallel strategies | Multiple Backward strategies on same goal, framework dedup + cascade-shelve | Single-strategy |
| Persistent state | SQLite-backed cascade DB; daemon resumable across crashes | In-memory / single-shot |
| Cascade depth tested | SG depth 10 (real research-grade structure) | miniF2F mostly ≤ 3 |
| Axiom-level verification | `#print axioms <name>` on every Backward acceptance + final root | `lake build` only (lets sorryAx through) |
| Engineering layer | LSP gateway pool, writeOlean RPC, watchdog v4, circuit breaker, spawn sandbox, library promotion | Research-prototype |
| Framework / model decoupling | Swap model = change config; same framework runs on any API | Tightly coupled to trained model |

## Where Asterism is currently weaker

| Aspect | Status |
|---|---|
| Public benchmark numbers | **0** (no miniF2F / putnambench numbers yet) |
| Problems attempted | Single digits (SG, PN, cantor, proj, wilson, ...) |
| Trained model contribution | None — pure API caller |
| Academic visibility | 0 papers, 0 citations |
| Reproducibility infra | Pre-release; no public benchmark scripts (until this proposal) |
| Training data contribution | None (LeanDojo's main contribution) |

## What this proposal aims at

1. **Close the benchmark gap**: run miniF2F validation (244) and test
   (244) sets, report success rate. Adapter shipped at
   `Benchmarks/minif2f/adapter.py` (no framework change required).

2. **Comparative study**: hold framework constant, swap model
   (Sonnet 4.6 only vs Opus 4.7 + Sonnet vs Claude 4.6 vs GPT-5 vs
   DSP-V2 vs ReProver). Quantify where multi-agent overhead pays off.

3. **Depth study**: do the per-problem proved/shelved curves separate
   when problem depth grows? Hypothesis: single-agent fails sharply
   above depth ~3-4; multi-agent degrades gracefully.

4. **Open release**: framework + benchmarks + run notes + datasets
   (every cascade trace usable as training data for future models).

## Pre-empting common questions

**Q: Why not just train a model like DSP-V2?**
A: Different research bet. DSP-V2 invests in model + needs retraining
for architecture changes. Asterism invests in framework + model-agnostic
— allows rapid ablation (multi-agent vs single, parallel vs serial,
verify-then-cascade vs root-only-verify). DSP-V2 and Asterism are
complementary; one could run DSP-V2 as the "model" inside Asterism's
framework.

**Q: SG is in Mathlib / training data, the model just memorized.**
A: SG is NOT in Mathlib (verifiable: `grep -r "Sylvester" .lake/`).
Even if the model has seen the proof in training, producing a
mechanically-verified Lean 4 derivation depth-10 with auxiliary
algebraic identities that haven't existed before is substantively
different from regurgitating a proof sketch.

**Q: Cost?**
A: One SG end-to-end run ≈ $10-20 API tokens. Per-problem watchdog +
attempt budgets cap blowups. Cost scales linearly with problem count,
not exponentially.

**Q: Reproducibility?**
A: Framework is open-source-ready (this repo). Every commit has a
trace of changes + run notes. miniF2F adapter pluggable in 5 minutes.
Professor can clone + run identical experiments.
