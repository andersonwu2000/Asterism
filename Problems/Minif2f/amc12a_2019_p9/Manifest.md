---
problem: Minif2f.amc12a_2019_p9
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2019_p9 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2019_p9`.

## Statement
∀ (a : ℕ → ℚ) (h₀ : a 1 = 1) (h₁ : a 2 = 3 / 7) (h₂ : ∀ n, a (n + 2) = a n * a (n + 1) / (2 * a n - a (n + 1))), ↑(a 2019).den + (a 2019).num = 8078

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
