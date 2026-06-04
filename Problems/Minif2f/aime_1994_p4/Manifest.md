---
problem: Minif2f.aime_1994_p4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aime_1994_p4 — imported from miniF2F

Original miniF2F theorem name: `aime_1994_p4`.

## Statement
∀ (n : ℕ) (h₀ : 0 < n) (h₀ : (∑ k ∈ Finset.Icc 1 n, Int.floor (Real.logb 2 k)) = 1994), n = 312

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
