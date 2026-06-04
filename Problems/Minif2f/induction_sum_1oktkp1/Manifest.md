---
problem: Minif2f.induction_sum_1oktkp1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.induction_sum_1oktkp1 — imported from miniF2F

Original miniF2F theorem name: `induction_sum_1oktkp1`.

## Statement
∀ (n : ℕ), (∑ k ∈ Finset.range n, (1 : ℝ) / ((k + 1) * (k + 2))) = n / (n + 1)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
