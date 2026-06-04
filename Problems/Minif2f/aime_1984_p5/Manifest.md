---
problem: Minif2f.aime_1984_p5
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aime_1984_p5 — imported from miniF2F

Original miniF2F theorem name: `aime_1984_p5`.

## Statement
∀ (a b : ℝ) (h₀ : Real.logb 8 a + Real.logb 4 (b ^ 2) = 5) (h₁ : Real.logb 8 b + Real.logb 4 (a ^ 2) = 7), a * b = 512

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
