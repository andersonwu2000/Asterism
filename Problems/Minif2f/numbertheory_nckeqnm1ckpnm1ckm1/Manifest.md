---
problem: Minif2f.numbertheory_nckeqnm1ckpnm1ckm1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.numbertheory_nckeqnm1ckpnm1ckm1 — imported from miniF2F

Original miniF2F theorem name: `numbertheory_nckeqnm1ckpnm1ckm1`.

## Statement
∀ (n k : ℕ) (h₀ : 0 < n ∧ 0 < k) (h₁ : k ≤ n), Nat.choose n k = Nat.choose (n - 1) k + Nat.choose (n - 1) (k - 1)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
