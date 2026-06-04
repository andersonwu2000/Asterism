---
problem: Minif2f.mathd_algebra_96
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_96 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_96`.

## Statement
∀ (x y z a : ℝ) (h₀ : 0 < x ∧ 0 < y ∧ 0 < z) (h₁ : Real.log x - Real.log y = a) (h₂ : Real.log y - Real.log z = 15) (h₃ : Real.log z - Real.log x = -7), a = -8

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
