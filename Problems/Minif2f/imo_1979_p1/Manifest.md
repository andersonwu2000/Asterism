---
problem: Minif2f.imo_1979_p1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.imo_1979_p1 — imported from miniF2F

Original miniF2F theorem name: `imo_1979_p1`.

## Statement
∀ (p q : ℕ) (h₀ : 0 < q) (h₁ : (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1) ^ (k + 1) * ((1 : ℝ) / k)) = p / q), 1979 ∣ p

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
