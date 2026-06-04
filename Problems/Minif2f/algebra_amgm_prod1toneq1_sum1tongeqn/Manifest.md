---
problem: Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn — imported from miniF2F

Original miniF2F theorem name: `algebra_amgm_prod1toneq1_sum1tongeqn`.

## Statement
∀ (a : ℕ → NNReal) (n : ℕ) (h₀ : Finset.prod (Finset.range n) a = 1), Finset.sum (Finset.range n) a ≥ n

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
