---
problem: Minif2f.amc12a_2008_p8
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2008_p8 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2008_p8`.

## Statement
∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : y ^ 3 = 1) (h₂ : 6 * x ^ 2 = 2 * (6 * y ^ 2)), x ^ 3 = 2 * Real.sqrt 2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
