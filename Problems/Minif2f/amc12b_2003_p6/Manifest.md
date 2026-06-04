---
problem: Minif2f.amc12b_2003_p6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12b_2003_p6 — imported from miniF2F

Original miniF2F theorem name: `amc12b_2003_p6`.

## Statement
∀ (a r : ℝ) (u : ℕ → ℝ) (h₀ : ∀ k, u k = a * r ^ k) (h₁ : u 1 = 2) (h₂ : u 3 = 6), u 0 = 2 / Real.sqrt 3 ∨ u 0 = -(2 / Real.sqrt 3)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
