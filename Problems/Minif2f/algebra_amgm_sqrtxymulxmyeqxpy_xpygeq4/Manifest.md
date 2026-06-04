---
problem: Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4 — imported from miniF2F

Original miniF2F theorem name: `algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4`.

## Statement
∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : y ≤ x) (h₂ : Real.sqrt (x * y) * (x - y) = x + y), x + y ≥ 4

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
