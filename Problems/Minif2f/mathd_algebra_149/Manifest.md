---
problem: Minif2f.mathd_algebra_149
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_149 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_149`.

## Statement
∀ (f : ℝ → ℝ) (h₀ : ∀ x < -5, f x = x ^ 2 + 5) (h₁ : ∀ x ≥ -5, f x = 3 * x - 8) (h₂ : Fintype (f ⁻¹' {10})), (∑ k ∈ (f ⁻¹' {10}).toFinset, k) = 6

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
