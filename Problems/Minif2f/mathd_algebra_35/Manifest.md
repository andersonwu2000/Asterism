---
problem: Minif2f.mathd_algebra_35
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_35 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_35`.

## Statement
∀ (p q : ℝ → ℝ) (h₀ : ∀ x, p x = 2 - x ^ 2) (h₁ : ∀ x : ℝ, x ≠ 0 → q x = 6 / x), p (q 2) = -7

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
