# 15-min demo storyboard

Audience: math / CS professor evaluating whether to support Asterism.
Goal: convince via concrete artifacts + honest positioning.

## Phase 1 — The problem (2 min)

> "I'll show you the Sylvester-Gallai theorem proved by an LLM-driven
> system. SG is from 1943, Erdős-Kelly distance-minimization argument.
> Mathlib doesn't have it — let me show you."

```bash
grep -ri "Sylvester" /d/Asterism/.lake/packages/mathlib/ | head -3
# (no hits — confirms not in mathlib training input)
```

Show theorem statement:
```lean
theorem main : ∀ (P : Finset (ℝ × ℝ)),
  (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
  ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q
```

> "This is a non-trivial planar-geometry combinatorics result. Now
> watch what happens with ChatGPT single-shot."

[Optional live: open ChatGPT / Claude, paste statement, give 30s,
show the output — almost certainly broken or sorry-laden.]

## Phase 2 — Asterism's approach (5 min)

> "Asterism is a framework that drives Claude Opus and Sonnet in
> distinct roles. Opus is the Backward agent — given a hard goal, it
> proposes a decomposition into sub-goals and writes a structural
> proof. Sonnet is the Builder agent — given a leaf-shaped sub-goal,
> it tries to close it directly."

Open `runs/sg_run_19.md`. Walk through:
- 17:39 — daemon starts on `main`
- Opus Backward decomposes main into `kelly_collinear` (via classical
  contrapositive). Quote the agent's `proposal_md`.
- Cascade goes 10 levels deep over 93 minutes.
- Final 5 leaves at depth 10 (`area_sq_pos`, `v_lagrange_id`, ...) are
  algebraic identities — Builder Sonnet closes each in seconds.
- s378 (`kelly_minimizer_exists`, first attempt) used `sorryAx`
  silently. Acceptance gate caught it → marked dead → re-Backward'd.

Open `docs/proposal/sg_cascade.md` mermaid graph. Walk the tree.

> "This decomposition wasn't pre-prompted. Opus chose Kelly's argument
> autonomously and structured the cascade so Sonnet had tractable
> leaves."

## Phase 3 — Independent verification (3 min)

> "Why should you trust any of this? Let me run a kernel-level check."

```bash
cd /d/Asterism
time lake build Problems.sylvester_gallai.Root  # ~17s on warm cache
# Build completed successfully (8399 jobs).
```

> "Lake's kernel checks the entire proof tree against Lean's type
> theory. 8399 jobs — every transitive lemma verified. Now the axiom
> check:"

```bash
# `#print axioms` walks dependency graph for sorryAx + domain axioms
python -c "
from Tooling import gateway_lifecycle as gl
from pathlib import Path
gl.start_gateway(Path('.'))
r = gl.verify_file(Path('Problems/sylvester_gallai/Root.lean'),
                   axioms_for='Problems.sylvester_gallai.main')
print('axioms:', r.get('axioms'))
"
# axioms: ['Classical.choice', 'Quot.sound', 'propext']
```

> "Only Mathlib-standard axioms. No `sorryAx`. The proof is real."

## Phase 4 — Scale (3 min)

> "Same framework runs miniF2F" (high-school olympiad benchmark)
> "for direct comparison with LeanDojo / DeepSeek-Prover."

Show `Benchmarks/minif2f/`:
```bash
ls Benchmarks/minif2f/
# adapter.py, test_adapter.py, README.md
cat Benchmarks/minif2f/README.md | head -30
```

Show pilot results from `runs/minif2f_pilot.md` (if pilot complete by
demo time; if not, show the methodology + adapter + sample
generated Manifest).

> "This is the immediate research roadmap — run full miniF2F + putnam,
> get comparable numbers, study the depth/multi-agent tradeoff."

## Phase 5 — Research questions + ask (2 min)

Open `docs/proposal/proposal.md`. Walk through RQ1-RQ4 (multi-agent
advantage, framework vs model, failure taxonomy, library transfer).

Concrete asks:
- Advisor support
- $3-5k API budget for benchmark runs
- 6-12 months focused execution time

> "If miniF2F numbers come in competitive with DSP-V2 and depth study
> validates graceful degradation, the architectural thesis is proven.
> If not, the negative result tells us where to invest. Either way
> it's publishable."

## Materials to have ready

| Item | Location |
|---|---|
| SG run notes | `runs/sg_run_19.md` |
| SG cascade tree | `Problems/sylvester_gallai/TREE.md` |
| Mermaid graph | `docs/proposal/sg_cascade.md` |
| Comparison table | `docs/proposal/comparison.md` |
| Proposal one-pager | `docs/proposal/proposal.md` |
| miniF2F pilot results | `runs/minif2f_pilot.md` (in progress) |
| Lake build verifier | live `lake build Problems.sylvester_gallai.Root` |
| Axiom check live | gateway script in Phase 3 |
| Framework engineering trace | `git log --oneline` last 30 commits |

## Pre-empt questions

See `docs/proposal/comparison.md` "Pre-empting common questions" section
— SG-in-Mathlib concern, cost, reproducibility, why-not-train-a-model.

## Tone

- **Honest about gaps** — no public benchmarks yet, this is the proposed
  work. Don't oversell.
- **Concrete on artifacts** — every claim verifiable on the spot.
- **Position as architecture research** — not competing with DSP-V2 on
  model training, complementary axis.
