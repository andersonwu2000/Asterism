---
problem: Minif2f.amc12a_2010_p11
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2010_p11 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2010_p11`.

## Statement
∀ (x b : ℝ) (h₀ : 0 < b) (h₁ : (7 : ℝ) ^ (x + 7) = 8 ^ x) (h₂ : x = Real.logb b (7 ^ 7)), b = 8 / 7

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
