---
problem: Minif2f.aime_1997_p11
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aime_1997_p11 — imported from miniF2F

Original miniF2F theorem name: `aime_1997_p11`.

## Statement
∀ (x : ℝ) (h₀ : x = (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) / ∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)), Int.floor (100 * x) = 241

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
