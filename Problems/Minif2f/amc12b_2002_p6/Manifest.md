---
problem: Minif2f.amc12b_2002_p6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12b_2002_p6 — imported from miniF2F

Original miniF2F theorem name: `amc12b_2002_p6`.

## Statement
∀ (a b : ℝ) (h₀ : a ≠ 0 ∧ b ≠ 0) (h₁ : ∀ x, x ^ 2 + a * x + b = (x - a) * (x - b)), a = 1 ∧ b = -2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
