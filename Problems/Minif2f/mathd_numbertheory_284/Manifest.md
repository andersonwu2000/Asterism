---
problem: Minif2f.mathd_numbertheory_284
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_284 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_284`.

## Statement
∀ (a b : ℕ) (h₀ : 1 ≤ a ∧ a ≤ 9 ∧ b ≤ 9) (h₁ : 10 * a + b = 2 * (a + b)), 10 * a + b = 18

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
