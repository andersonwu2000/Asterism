---
problem: Minif2f.mathd_algebra_480
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_480 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_480`.

## Statement
∀ (f : ℝ → ℝ) (h₀ : ∀ x < 0, f x = -x ^ 2 - 1) (h₁ : ∀ x, 0 ≤ x ∧ x < 4 → f x = 2) (h₂ : ∀ x ≥ 4, f x = Real.sqrt x), f π = 2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
