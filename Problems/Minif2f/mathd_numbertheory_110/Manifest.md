---
problem: Minif2f.mathd_numbertheory_110
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_110 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_110`.

## Statement
∀ (a b : ℕ) (h₀ : 0 < a ∧ 0 < b ∧ b ≤ a) (h₁ : (a + b) % 10 = 2) (h₂ : (2 * a + b) % 10 = 1), (a - b) % 10 = 6

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
