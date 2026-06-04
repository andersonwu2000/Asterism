---
problem: Minif2f.mathd_algebra_616
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_616 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_616`.

## Statement
∀ (f g : ℝ → ℝ) (h₀ : ∀ x, f x = x ^ 3 + 2 * x + 1) (h₁ : ∀ x, g x = x - 1), f (g 1) = 1

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
