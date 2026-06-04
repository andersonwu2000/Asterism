---
problem: Minif2f.aime_1988_p3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aime_1988_p3 — imported from miniF2F

Original miniF2F theorem name: `aime_1988_p3`.

## Statement
∀ (x : ℝ) (h₀ : 0 < x) (h₁ : Real.logb 2 (Real.logb 8 x) = Real.logb 8 (Real.logb 2 x)), Real.logb 2 x ^ 2 = 27

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
