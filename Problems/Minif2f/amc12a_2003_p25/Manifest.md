---
problem: Minif2f.amc12a_2003_p25
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2003_p25 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2003_p25`.

## Statement
∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : 0 < b) (h₁ : ∀ x, f x = Real.sqrt (a * x ^ 2 + b * x)) (h₂ : { x | 0 ≤ f x } = f '' { x | 0 ≤ f x }), a = 0 ∨ a = -4

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
