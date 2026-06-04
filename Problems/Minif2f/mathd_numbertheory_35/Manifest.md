---
problem: Minif2f.mathd_numbertheory_35
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_35 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_35`.

## Statement
∀ (S : Finset ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ n ∣ Nat.sqrt 196), (∑ k ∈ S, k) = 24

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
