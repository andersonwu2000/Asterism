---
problem: Minif2f.amc12a_2013_p7
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2013_p7 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2013_p7`.

## Statement
∀ (s : ℕ → ℝ) (h₀ : ∀ n, s (n + 2) = s (n + 1) + s n) (h₁ : s 9 = 110) (h₂ : s 7 = 42), s 4 = 10

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
