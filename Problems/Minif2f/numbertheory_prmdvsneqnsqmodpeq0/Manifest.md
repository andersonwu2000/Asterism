---
problem: Minif2f.numbertheory_prmdvsneqnsqmodpeq0
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.numbertheory_prmdvsneqnsqmodpeq0 — imported from miniF2F

Original miniF2F theorem name: `numbertheory_prmdvsneqnsqmodpeq0`.

## Statement
∀ (n : ℤ) (p : ℕ) (h₀ : Nat.Prime p), ↑p ∣ n ↔ n ^ 2 % p = 0

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
