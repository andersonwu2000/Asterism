# A Theorem-Proving Framework Combining General-Purpose LLMs and Formal Verification

## Abstract

Asterism is a proof framework that combines general-purpose large language
models with Lean 4 formal verification.
Its architecture coordinates multiple agents through a dynamic pipeline
driver and tracks proof dependencies via an AND/OR graph, addressing the
loss of coherence that LLMs exhibit over long stretches of reasoning;
every proof it produces is mechanically verified by Lean.
In an initial trial over the 244 problems of miniF2F-Valid, Asterism
proved every genuinely provable statement and generated counterexamples
for the nine theorems that are unprovable as stated in the benchmark
itself; over the same period it also produced proofs of classical
results including the Sylvester-Gallai theorem and the zero Lebesgue
measure of the Cantor set.
This document describes the framework's motivation, core method,
accumulated results, and research path forward.

## 1. Why AI + Lean

Contemporary large language models possess substantial mathematical
knowledge and symbolic manipulation ability, and they operate around
the clock, generating plausible-looking inferences at scale.
However, human verification cannot match that throughput, while the
nature of LLMs means their output offers no guarantee of logical rigour
— a property mathematics cannot do without; in other words, the
mismatch between throughput and rigour is the principal bottleneck for
applying AI to mathematical research.

Lean, as a formal verification system, supplies the most appropriate
remedy: a mechanical check that compensates for the rigour LLMs lack.
With the LLM proposing proof ideas and Lean verifying each one,
mathematicians can be substantially relieved of the most tedious parts
of the verification work.
As LLMs continue to advance in code editing and logical reasoning, the
feasibility and potential of the AI + Lean combination can be expected
to keep expanding — which is why LLM-based provers have seen a
pronounced rise in research and deployment activity in recent years.

## 2. Method

Asterism uses an AND/OR graph to track the exploration of a proof.
Nodes come in two kinds:
  OR Node — a goal to be proved; the node succeeds whenever any one
  of its proposed proof strategies succeeds.
  AND Node — a proof strategy; the node succeeds when every subgoal
  produced by the strategy succeeds.
On receiving a goal, the framework generates a proof strategy together
with several easier-to-prove subgoals, judges whether each subgoal
needs further decomposition, and recurses through the same process for
each.
Once all subgoals are proved, the framework mechanically assembles
them into a proof of the original goal.
When a strategy hits a wall — through difficulty or through an error
in its premises — the framework discards it and generates a new
strategy under the same goal.

Asterism is driven by a dynamic pipeline that manages multiple
parallel pipelines in real time.
The Backward pipeline proposes proof strategies from a given goal;
the Builder pipeline closes leaf-node proofs.
The architecture preserves ample room for extension — additional
pipelines may later handle strategic planning, anticipating necessary
prior lemmas, and discovering reusable abstract lemmas or relevant
literature.
The framework also defines explicit handling for stuck or
erroneous states: an agent may, when needed, request a new strategy,
hand off to a more suitable pipeline, or terminate when it identifies
that the target itself is ill-posed; and shared mechanisms let
proof techniques and prior failure experience accumulate and transfer
across spawns so that proving ability improves over time.

The overall design goal is to provide LLMs with a comfortable
collaborative environment in which AI, under the framework's guidance,
divides labour and explores — delivering automated, efficient, and
rigorous proof capability that supports mathematicians through the
heavy lifting of logical verification.

## 3. Design rationale

#### **Why multi-agent?**
The miniF2F trial showed that proving directly with the Builder
pipeline yielded a markedly lower success rate than a Backward +
Builder collaboration.
Structural advantages of the multi-agent design include, but are not
limited to:
1. Parallel collaboration advances different subgoals simultaneously,
   sharply reducing overall wall-clock time;
2. Lightweight proofs can be delegated to cheaper models while deeper
   strategic planning employs stronger models, making budget allocation
   more efficient;
3. Agents accumulate and transfer experience through shared documents,
   preventing a single model from repeatedly trying the same wrong
   strategies and routes;
4. A single model's context length and attention are limited;
   multi-agent designs hold a clear advantage when broad exploration
   or very long proofs are required.

Since the second half of 2025, recent SOTA provers such as BFS-Prover,
Seed-Prover, and HILBERT have all shifted toward multi-agent
architectures in their development and research, marking a clear
trend.

#### **Why a general-purpose model?**
Most prior provers trained their own specialised models, ranging
from 7B to 671B parameters; training costs are heavy and, even when
weights are released, most researchers lack the hardware to run them.
With the rapid rise in code-writing ability of Claude (especially the
2026 Claude Code line), our miniF2F benchmark results show that, under
a well-designed framework, a general-purpose model proves at a level
comparable to that of specialised trained models.

Additional long-term benefits of building on a general model:
1. Model improvement is driven continuously by the API provider;
   Asterism itself benefits without retraining anything;
2. Deployment cost is reduced to a subscription fee plus a minimal
   memory footprint; no GPU is needed.

Within the current landscape of public LLM-based theorem provers,
Asterism is one of the few options that ordinary users can run
without specialised hardware.

## 4. Preliminary results

Within the first month of development, Asterism ran the full 244
problems of the miniF2F-Valid dataset.
Of these, 235 (including 20 IMO problems) received proofs verified by
the Lean kernel; the remaining 9 were flagged as ill-stated by the
Backward agent, which produced counterexamples that have themselves
been formally verified.
Cross-checking the commit history of yangky11/miniF2F-lean4 confirmed
that all nine are encoding errors introduced during Lean 4
transcription — the original competition problems are correct; the
formalisations had simply dropped a precondition, used natural-number
division where a real was intended, or misplaced a quantifier.
The nine counterexamples have been consolidated into a single upstream
issue ready to be filed with the yangky11/miniF2F-lean4 maintainers.

For statements at university level and above, the framework has
produced complete proofs of, among others, the Sylvester-Gallai
theorem (fastest run finished in 93 minutes), the zero Lebesgue measure
of the Cantor set, and the irreducibility of the cyclic
highest-weight sl₂-representation.
These trials together show that, on statements from AMC/AIME/IMO level
up to undergraduate mathematics, the current architecture is capable
of producing complete proofs.

## 5. Research direction

The planned research stages are as follows:

**Step 1. Add new pipelines to expand the framework's capability.**

By introducing Strategist, Forward, and Librarian pipelines, Asterism
will gain the ability to search the literature and construct
mathematical tools of its own when attacking conjectures; the framework
itself will be adjusted to support the node management and
collaborative communication that a larger pipeline pool requires.
PutnamBench (270 problems, current public SOTA still below 30%) will
serve as the verification instrument.

**Step 2. Target theorems that are known but not yet formalised.**

The Lean and Mathlib communities maintain long lists — hundreds of
results — of statements that are mathematically known yet not in any
formal system. Such targets are work the community explicitly needs;
they are also the right setting for testing whether the framework
can construct an entire proof structure on its own.
We plan to pick 10–20 cross-domain targets and attempt end-to-end
formalisation.

**Step 3. Attempt open problems from the Erdős corpus.**

This stage corresponds to Asterism's long-term ambition: a framework
that, with minimal human intervention, can independently verify or
even discover new mathematical results.

The overall objective is for Asterism to progress from
"can prove problems given to it" to "can decide on its own what to
explore, which tools to develop, and construct the proofs itself."
The framework has already reserved the necessary room for extension,
and the directions for further refinement are mapped out.

## 6. Budget

- Token budget: USD 300–500 per month.
- Compute: existing hardware is sufficient; larger workloads that need
  a wider pipeline pool (≈1.2 GB per pipeline worker) may require
  additional RAM.
- Time: 6–12 months.

## 7. References

The full source of Asterism is publicly available on GitHub
(andersonwu2000/Asterism).
Recent related work referenced in this document:

- HyperTree Proof Search (arxiv 2205.11491)
- Goedel-Prover V1 (2502.07640), V2 (2508.03613)
- BFS-Prover V1 (2502.03438), V2 (2509.06493)
- Kimina-Prover Preview (2504.11354)
- DeepSeek-Prover-V2 (2504.21801)
- StepFun-Prover (2507.20199)
- Seed-Prover (2507.23726)
- HILBERT (2509.22819)
- miniF2F-Lean Revisited (2511.03108)
