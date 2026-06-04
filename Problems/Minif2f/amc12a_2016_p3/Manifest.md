---
problem: Minif2f.amc12a_2016_p3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2016_p3 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2016_p3`.

## Statement
∀ (f : ℝ → ℝ → ℝ) (h₀ : ∀ x, ∀ (y) (_ : y ≠ 0), f x y = x - y * Int.floor (x / y)), f (3 / 8) (-(2 / 5)) = -(1 / 40)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
