---
problem: Minif2f.amc12b_2003_p17
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12b_2003_p17 — imported from miniF2F

Original miniF2F theorem name: `amc12b_2003_p17`.

## Statement
∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : Real.log (x * y ^ 3) = 1) (h₂ : Real.log (x ^ 2 * y) = 1), Real.log (x * y) = 3 / 5

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
