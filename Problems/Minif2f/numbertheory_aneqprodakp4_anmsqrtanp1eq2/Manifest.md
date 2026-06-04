---
problem: Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2 — imported from miniF2F

Original miniF2F theorem name: `numbertheory_aneqprodakp4_anmsqrtanp1eq2`.

## Statement
∀ (a : ℕ → ℝ) (h₀ : a 0 = 1) (h₁ : ∀ n, a (n + 1) = (∏ k ∈ Finset.range (n + 1), a k) + 4), ∀ n ≥ 1, a n - Real.sqrt (a (n + 1)) = 2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
