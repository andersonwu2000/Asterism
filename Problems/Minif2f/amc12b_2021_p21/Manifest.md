---
problem: Minif2f.amc12b_2021_p21
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12b_2021_p21 — imported from miniF2F

Original miniF2F theorem name: `amc12b_2021_p21`.

## Statement
∀ (S : Finset ℝ) (h₀ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), (↑2 ≤ ∑ k ∈ S, k) ∧ (∑ k ∈ S, k) < 6

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
