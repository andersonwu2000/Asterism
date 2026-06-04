---
problem: Minif2f.induction_sum_odd
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.induction_sum_odd — imported from miniF2F

Original miniF2F theorem name: `induction_sum_odd`.

## Statement
∀ (n : ℕ), (∑ k ∈ Finset.range n, (2 * k + 1)) = n ^ 2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
