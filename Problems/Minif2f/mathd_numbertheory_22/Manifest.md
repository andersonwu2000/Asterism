---
problem: Minif2f.mathd_numbertheory_22
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_22 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_22`.

## Statement
∀ (b : ℕ) (h₀ : b < 10) (h₁ : Nat.sqrt (10 * b + 6) * Nat.sqrt (10 * b + 6) = 10 * b + 6), b = 3 ∨ b = 1

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
