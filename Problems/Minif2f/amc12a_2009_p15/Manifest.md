---
problem: Minif2f.amc12a_2009_p15
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2009_p15 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2009_p15`.

## Statement
∀ (n : ℕ) (h₀ : 0 < n) (h₁ : (∑ k ∈ Finset.Icc 1 n, ↑k * Complex.I ^ k) = 48 + 49 * Complex.I), n = 97

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
