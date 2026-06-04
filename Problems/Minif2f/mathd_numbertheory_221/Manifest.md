---
problem: Minif2f.mathd_numbertheory_221
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_221 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_221`.

## Statement
∀ (S : Finset ℕ) (h₀ : ∀ x : ℕ, x ∈ S ↔ 0 < x ∧ x < 1000 ∧ x.divisors.card = 3), S.card = 11

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
