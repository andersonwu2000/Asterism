---
problem: Minif2f.imo_1967_p3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.imo_1967_p3 — imported from miniF2F

Original miniF2F theorem name: `imo_1967_p3`.

## Statement
∀ (k m n : ℕ) (c : ℕ → ℕ) (h₀ : 0 < k ∧ 0 < m ∧ 0 < n) (h₁ : ∀ s, c s = s * (s + 1)) (h₂ : Nat.Prime (k + m + 1)) (h₃ : n + 1 < k + m + 1), (∏ i ∈ Finset.Icc 1 n, c i) ∣ ∏ i ∈ Finset.Icc 1 n, c (m + i) - c k

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
