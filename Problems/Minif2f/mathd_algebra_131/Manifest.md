---
problem: Minif2f.mathd_algebra_131
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_131 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_131`.

## Statement
∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = 2 * x ^ 2 - 7 * x + 2) (h₁ : f a = 0) (h₂ : f b = 0) (h₃ : a ≠ b), 1 / (a - 1) + 1 / (b - 1) = -1

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
