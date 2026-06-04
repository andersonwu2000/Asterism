---
problem: Minif2f.aime_1991_p1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aime_1991_p1 — imported from miniF2F

Original miniF2F theorem name: `aime_1991_p1`.

## Statement
∀ (x y : ℕ) (h₀ : 0 < x ∧ 0 < y) (h₁ : x * y + (x + y) = 71) (h₂ : x ^ 2 * y + x * y ^ 2 = 880), x ^ 2 + y ^ 2 = 146

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
