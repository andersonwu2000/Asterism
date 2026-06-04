---
problem: Minif2f.mathd_numbertheory_709
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_709 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_709`.

## Statement
∀ (n : ℕ) (h₀ : 0 < n) (h₁ : Finset.card (Nat.divisors (2 * n)) = 28) (h₂ : Finset.card (Nat.divisors (3 * n)) = 30), Finset.card (Nat.divisors (6 * n)) = 35

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
