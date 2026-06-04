---
problem: Minif2f.numbertheory_sumkmulnckeqnmul2pownm1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.numbertheory_sumkmulnckeqnmul2pownm1 — imported from miniF2F

Original miniF2F theorem name: `numbertheory_sumkmulnckeqnmul2pownm1`.

## Statement
∀ (n : ℕ) (h₀ : 0 < n), (∑ k ∈ Finset.Icc 1 n, k * Nat.choose n k) = n * 2 ^ (n - 1)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
