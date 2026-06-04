---
problem: Minif2f.mathd_algebra_421
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_421 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_421`.

## Statement
∀ (a b c d : ℝ) (h₀ : b = a ^ 2 + 4 * a + 6) (h₁ : b = 1 / 2 * a ^ 2 + a + 6) (h₂ : d = c ^ 2 + 4 * c + 6) (h₃ : d = 1 / 2 * c ^ 2 + c + 6) (h₄ : a < c), c - a = 6

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
