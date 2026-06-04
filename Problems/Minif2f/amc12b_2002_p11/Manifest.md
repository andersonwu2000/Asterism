---
problem: Minif2f.amc12b_2002_p11
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12b_2002_p11 — imported from miniF2F

Original miniF2F theorem name: `amc12b_2002_p11`.

## Statement
∀ (a b : ℕ) (h₀ : Nat.Prime a) (h₁ : Nat.Prime b) (h₂ : Nat.Prime (a + b)) (h₃ : Nat.Prime (a - b)), Nat.Prime (a + b + (a - b + (a + b)))

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
