---
problem: Minif2f.mathd_numbertheory_412
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_412 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_412`.

## Statement
∀ (x y : ℤ) (h₀ : x % 19 = 4) (h₁ : y % 19 = 7), (x + 1) ^ 2 * (y + 5) ^ 3 % 19 = 13

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
