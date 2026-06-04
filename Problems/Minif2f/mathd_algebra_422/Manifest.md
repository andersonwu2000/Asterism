---
problem: Minif2f.mathd_algebra_422
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_422 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_422`.

## Statement
∀ (x : ℝ) (σ : Equiv ℝ ℝ) (h₀ : ∀ x, σ.1 x = 5 * x - 12) (h₁ : σ.1 (x + 1) = σ.2 x), x = 47 / 24

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
