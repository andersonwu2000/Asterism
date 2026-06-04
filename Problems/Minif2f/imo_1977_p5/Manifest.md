---
problem: Minif2f.imo_1977_p5
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.imo_1977_p5 — imported from miniF2F

Original miniF2F theorem name: `imo_1977_p5`.

## Statement
∀ (a b q r : ℕ) (h₀ : r < a + b) (h₁ : a ^ 2 + b ^ 2 = (a + b) * q + r) (h₂ : q ^ 2 + r = 1977), abs ((a : ℤ) - 22) = 15 ∧ abs ((b : ℤ) - 22) = 28 ∨ abs ((a : ℤ) - 22) = 28 ∧ abs ((b : ℤ) - 22) = 15

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
