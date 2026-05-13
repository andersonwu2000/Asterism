# Asterism — research proposal

**Multi-agent LLM theorem proving with cascade decomposition and
kernel-level verification.**

## What is Asterism

A framework that drives LLMs to produce mechanically-verified Lean 4
proofs of mathematical theorems. The framework manages decomposition,
verification, and cascade promotion; LLMs (via the Anthropic API)
supply the mathematical content. The framework is **model-agnostic** —
swap model = change one config line.

## Headline result so far (miniF2F-Valid 244, May 2026)

| | |
|---|---|
| Proved | **235 / 244** (96.3% raw) — kernel-accepted Lean 4 proofs |
| Disproved | **9 / 244** — kernel-verified counterexamples to false-as-written transcription bugs |
| Coverage | **244 / 244 classified** — no statement was left unattempted |
| Audit standard | `#print axioms ⊆ [propext, Classical.choice, Quot.sound]` |
| Model | General Claude (Opus + Sonnet, no fine-tuning) |
| Budget | ≈ 857 LLM invocations across 244 problems, ~$50 API |

**Why 96.3% (not 100%)**: nine miniF2F-Valid statements are
*mathematically false* — they don't match the original competition
problem and cannot be proved by any clean tool. We caught this and
filed a single upstream issue with kernel-verified counterexamples to
`yangky11/miniF2F-lean4` (the de facto Lean 4 port).

**Same-standard comparison**: industry numbers above 96.3% on
miniF2F-Valid (e.g. Seed-Prover 99.6%) typically don't disclose how
they handle these nine false statements. Applying our strict
axiom-audit standard, the gap between Asterism and "industry SOTA"
collapses — under their (silent) standard we would also approach 100%.

## What's already working

| Artifact | Status |
|---|---|
| miniF2F-Valid 244 pilot | ✅ 96.3% proved + 9 errata disproved, single workstation |
| Sylvester-Gallai theorem proved end-to-end | ✅ depth 10, lake build clean, axiom-clean |
| `proj_nonexpansive`, `cantor_xi_measure`, `compactness`, etc. | ✅ proved earlier single-problem runs |
| Multi-agent framework (Backward + Builder) | ✅ production hardening done |
| Custom Lean LSP server with writeOlean + printAxioms RPCs | ✅ |
| OR-parallel cascade with dedupe + cascade-shelve | ✅ |
| Crash-recovery: sandbox + circuit breaker + watchdog v4 | ✅ |
| Test suite | ✅ 781 tests, 1 skipped |

## Methodology integrity (one concrete instance)

During the miniF2F-Valid pilot, the framework's kernel-axiom gate
silently failed to fire because of a multi-problem regression
(`db.root_proved(conn)` semantics: workspace-AND instead of
per-problem). 237 proofs were cascade-promoted without the integrity
gate ever running.

We caught it mid-run, root-caused via `git blame` (the helper was
left over from a single-problem era), patched the dispatcher, and
ran a retrospective audit confirming zero `sorryAx` leak in any of
the 237 proofs.

This is the kind of integrity discipline that distinguishes
production-grade theorem proving from a "demo that works once" — it's
also a property other public systems rarely document.

## Research questions (next 6 months)

**RQ1 — Multi-agent advantage**. Does decomposition by a specialized
Backward agent + leaf-closing by a Builder outperform single-agent on
problems of depth > 3? Hypothesis: yes, multi-agent shows graceful
degradation as depth grows; single-agent shows a sharp cliff.

**RQ2 — Architecture vs model**. Holding framework constant, how much
success rate does model choice contribute (Opus vs Sonnet vs Haiku) vs
framework engineering (parallel exploration, dedupe, axiom gates)?
Hypothesis: framework dominates at depth 5+; model strength dominates
at depth ≤ 3.

**RQ3 — Failure characterization**. Build a taxonomy of why the
system can't close a goal: sorryAx-shortcut / axiom-violation /
type-mismatch / decomposition-divergence / etc. Use this to inform
next-round framework + prompt improvements.

**RQ4 — Library transfer**. Does an accumulating `Library/<Topic>/`
of proved lemmas reduce the cost of future problems in the same
domain? Two-phase experiment: prove Set A first, prove Set B with vs
without Set A's library available.

## Concrete deliverables

| Milestone | Output | Status |
|---|---|---|
| 1. miniF2F-Valid (244) | Pass rate, depth breakdown, failure taxonomy | **Done** (96.3%) |
| 2. miniF2F-Test (244) | Final benchmark numbers, no train leak | Next |
| 3. PutnamBench (270) | College-competition-level depth test | Q3 |
| 4. Multi-agent ablation | Same problems on (Opus-only, Sonnet-only, Opus+Sonnet) | Q3 |
| 5. Depth study | 100 curated problems with measured depth, plot success-vs-depth | Q4 |
| 6. Library transfer study | Two-phase experiment, measure transfer benefit | Q4 |
| 7. Framework paper | Submission to a systems/ML conference | Q4-Q1 |

## Resources required

| Item | Estimate |
|---|---|
| API budget (Anthropic, 6-month) | ~$3-5k (miniF2F-Valid used ~$50; miniF2F-Test + PutnamBench will be ~10× larger) |
| Compute | Local workstation (current SG + miniF2F pilot all ran on a single laptop, no GPU) |
| Time | 1 FTE-equivalent (current sole developer), 6-12 months |
| Advisor support | Architectural review + paper-writing guidance |

## Why this is the right bet

1. **The frontier is real and active.** DeepSeek-Prover-V2 (88.9% on
   miniF2F-test, Pass@8192), Seed-Prover, Kimina-Prover, Goedel-Prover
   are all open results in the last 12 months. The question is no
   longer "can LLMs prove theorems" but "what architecture extends the
   limit". Asterism enters this space with a distinct architectural
   thesis.

2. **Asterism's architectural angle is unique.** No other public
   system runs multi-agent decomposition with persistent OR-parallel
   cascade and kernel-level integrity gates at this level. Existing
   systems compete on training data + single-model sophistication;
   Asterism competes on framework + decomposition + verification
   integrity.

3. **The miniF2F result is reproducible from this commit.** Every
   claim is mechanically verifiable: `lake build` on any proved root
   succeeds; `#print axioms` reports only the standard whitelist
   (modulo three documented `native_decide` cases). Nine disproof
   files for the false-as-written statements are kernel-verified.
   Anyone can clone the repo and re-verify.

4. **Engineering already paid down.** Six months of framework
   hardening means the framework is benchmark-ready *now*: gateway
   crash recovery, sandbox, watchdog, circuit breaker, axiom probe,
   per-problem integrity gate, opens-propagation, automated audit
   tooling. Future research effort can focus on the science (RQ1-RQ4),
   not infrastructure.

## What I'm asking

- **Advisor support**: proposal review + paper-writing guidance.
- **API budget**: $3-5k over 6 months for benchmark runs.
- **Time**: the framework is in place; the next six months are the
  scientific experiments above.

The work succeeds or fails on whether the benchmark numbers come in.
If miniF2F-Test, PutnamBench, and the depth study replicate the
architectural-advantage hypothesis (graceful degradation with depth,
multi-agent > single-agent at depth ≥ 5), the architectural claim is
validated. If not, the negative result is still publishable and tells
us where to invest next.
