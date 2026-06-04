---
problem: Minif2f.mathd_numbertheory_780
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_780 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_780`.

## Statement
∀ (m x : ℤ) (h₀ : 0 ≤ x) (h₁ : 10 ≤ m ∧ m ≤ 99) (h₂ : 6 * x % m = 1) (h₃ : (x - 6 ^ 2) % m = 0), m = 43

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
