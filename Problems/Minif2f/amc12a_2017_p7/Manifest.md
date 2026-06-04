---
problem: Minif2f.amc12a_2017_p7
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2017_p7 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2017_p7`.

## Statement
∀ (f : ℕ → ℝ) (h₀ : f 1 = 2) (h₁ : ∀ n, 1 < n ∧ Even n → f n = f (n - 1) + 1) (h₂ : ∀ n, 1 < n ∧ Odd n → f n = f (n - 2) + 2), f 2017 = 2018

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
