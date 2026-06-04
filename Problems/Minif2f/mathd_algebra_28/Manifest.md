---
problem: Minif2f.mathd_algebra_28
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_28 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_28`.

## Statement
∀ (c : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = 2 * x ^ 2 + 5 * x + c) (h₁ : ∃ x, f x ≤ 0), c ≤ 25 / 8

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
