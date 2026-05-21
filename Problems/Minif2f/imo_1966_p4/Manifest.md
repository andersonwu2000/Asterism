---
problem: Minif2f.imo_1966_p4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.imo_1966_p4 — imported from miniF2F

Original miniF2F theorem name: `imo_1966_p4`.

## Statement
∀ (n : ℕ) (x : ℝ) (h₀ : ∀ k : ℕ, 0 < k → ∀ m : ℤ, x ≠ m * π / 2 ^ k) (h₁ : 0 < n), (∑ k ∈ Finset.Icc 1 n, 1 / Real.sin (2 ^ k * x)) = 1 / Real.tan x - 1 / Real.tan (2 ^ n * x)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
