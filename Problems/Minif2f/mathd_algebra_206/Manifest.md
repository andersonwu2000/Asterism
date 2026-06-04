---
problem: Minif2f.mathd_algebra_206
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_206 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_206`.

## Statement
∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = x ^ 2 + a * x + b) (h₁ : 2 * a ≠ b) (h₂ : f (2 * a) = 0) (h₃ : f b = 0), a + b = -1

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
