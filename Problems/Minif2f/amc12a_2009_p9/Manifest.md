---
problem: Minif2f.amc12a_2009_p9
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2009_p9 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2009_p9`.

## Statement
∀ (a b c : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f (x + 3) = 3 * x ^ 2 + 7 * x + 4) (h₁ : ∀ x, f x = a * x ^ 2 + b * x + c), a + b + c = 2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
