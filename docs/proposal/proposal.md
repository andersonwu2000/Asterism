# Asterism — research proposal

**Multi-agent LLM theorem proving with cascade decomposition and
kernel-level verification.**

## What is Asterism

A framework that drives LLMs to produce mechanically-verified Lean 4
proofs of mathematical theorems. The framework manages decomposition,
verification, and cascade promotion; the LLMs (Claude Opus + Sonnet
via API) supply the mathematical content.

## What's already working

| Artifact | Status |
|---|---|
| Sylvester-Gallai theorem proved end-to-end | ✅ depth 10, lake build 8399/8399, axiom-clean |
| `proj_nonexpansive` (metric projection nonexpansive) | ✅ depth 3 |
| `cantor_xi_measure`, `compactness`, `gen_generates`, `inner_zero_iff_smul` | ✅ proved earlier |
| Multi-agent framework (Backward + Builder) | ✅ production hardening done |
| Custom Lean LSP server with writeOlean + printAxioms RPCs | ✅ |
| OR-parallel cascade with dedupe + shelve | ✅ |
| Crash-recovery: sandbox + circuit breaker + watchdog v4 | ✅ |
| miniF2F benchmark adapter | ✅ shipped at `Benchmarks/minif2f/` |
| Test suite | ✅ 780 tests, 1 skipped |

## Research questions

**RQ1 — Multi-agent advantage**. Does decomposition by a specialized
agent (Opus Backward) + leaf-closing by another (Sonnet Builder)
outperform single-agent on problems of depth > 3? Hypothesis: yes,
multi-agent shows graceful degradation as depth grows; single-agent
shows sharp cliff.

**RQ2 — Architecture vs model**. Holding the framework constant, how
much success rate does model choice contribute (Opus vs Sonnet vs
Haiku) vs framework engineering (parallel exploration, dedupe, axiom
gates)? Hypothesis: framework engineering dominates at depth 5+;
model strength dominates at depth ≤ 3.

**RQ3 — Failure characterization**. When the system can't close a
goal, what's the structural reason? Build a taxonomy:
sorryAx-shortcut / axiom-violation / type-mismatch / decomposition-
divergence / proof-too-long / etc. Use this to inform next-round
framework + agent prompting improvements.

**RQ4 — Library transfer**. Does an accumulating `Library/<Topic>/`
of proved lemmas reduce the cost of future problems in the same
domain? Run experiment: prove Set A first, prove Set B with vs
without Set A's library available.

## Concrete deliverables

| 6-month milestone | Output |
|---|---|
| 1. miniF2F validation (244 problems) | Success rate, depth breakdown, failure taxonomy. Direct compare with LeanDojo / DSP-V2 |
| 2. miniF2F test (244) | Final benchmark numbers, no train leak |
| 3. putnambench (270) | College-competition-level depth test |
| 4. Multi-agent ablation | Same problems on (Opus-only, Sonnet-only, Opus+Sonnet) configs |
| 5. Depth study | Curated 100 problems with measured depth, plot success vs depth curve |
| 6. Library transfer study | Two-phase experiment, measure transfer benefit |
| 7. Framework paper | Submission to a systems/ML conference. Multi-agent architecture + production engineering + benchmark numbers |

## Resources required

| Item | Estimate |
|---|---|
| API budget (Anthropic, ~3-month pilot) | ~$3-5k (1 SG run ≈ $15; 244 miniF2F runs ≈ $1-2k) |
| Compute | Local workstation (current SG+PN ran on a single laptop); no GPU |
| Time | 1 FTE-equivalent (current sole developer), 6-12 months |
| Co-author / advisor support | Architectural review + paper writing guidance |

## Why this is the right bet

1. **LLM-driven proofs are a real frontier** — DSP-V2 and others have
   shown the trajectory; the question is no longer "can it" but
   "how far can architecture extend the limits".

2. **Asterism's architectural angle is unique** — no other public
   system runs multi-agent cascade with production engineering at this
   level. Existing systems compete on training data + single-model
   sophistication; Asterism competes on framework + decomposition.

3. **The work is reproducible from this commit** — every claim
   verifiable: `lake build Problems.sylvester_gallai.Root` proves SG;
   `python -m pytest` runs 780 tests; commit history shows every
   engineering decision. Professor can clone + verify any claim
   independently.

4. **Engineering already paid down** — 6 months of framework hardening
   (gateway crash recovery, sandbox, watchdog v4, circuit breaker,
   axiom probe) means the framework is benchmark-ready *now*, not in
   "6 months once we fix the infrastructure".

## What I'm asking

- Advisor support (this proposal's review + paper-writing guidance)
- API budget for benchmark runs ($3-5k over 3-6 months)
- Time to execute (the framework is in place; the science is the next
  6 months)

The work succeeds or fails on whether the benchmark numbers come in.
If miniF2F success rate at depth 3-5 is competitive with DSP-V2 on
fewer problems and depth study shows the predicted graceful-degradation
pattern, the architectural claim is validated. If not, the negative
result is still publishable + suggests where to invest next.
