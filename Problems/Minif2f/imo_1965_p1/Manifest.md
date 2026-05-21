---
problem: Minif2f.imo_1965_p1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.imo_1965_p1 — imported from miniF2F

Original miniF2F theorem name: `imo_1965_p1`.

## Statement
∀ (x : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ 2 * π) (h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x)))) (h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2), π / 4 ≤ x ∧ x ≤ 7 * π / 4

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
