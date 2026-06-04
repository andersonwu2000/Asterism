---
problem: Minif2f.aimeII_2020_p6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aimeII_2020_p6 — imported from miniF2F

Original miniF2F theorem name: `aimeII_2020_p6`.

## Statement
∀ (t : ℕ → ℚ) (h₀ : t 1 = 20) (h₁ : t 2 = 21) (h₂ : ∀ n ≥ 3, t n = (5 * t (n - 1) + 1) / (25 * t (n - 2))), ↑(t 2020).den + (t 2020).num = 626

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
