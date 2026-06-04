---
problem: Minif2f.amc12_2000_p11
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12_2000_p11 — imported from miniF2F

Original miniF2F theorem name: `amc12_2000_p11`.

## Statement
∀ (a b : ℝ) (h₀ : a ≠ 0 ∧ b ≠ 0) (h₁ : a * b = a - b), a / b + b / a - a * b = 2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
