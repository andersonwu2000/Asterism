---
problem: Minif2f.aime_1983_p9
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aime_1983_p9 — imported from miniF2F

Original miniF2F theorem name: `aime_1983_p9`.

## Statement
∀ (x : ℝ) (h₀ : 0 < x ∧ x < Real.pi), 12 ≤ (9 * (x ^ 2 * Real.sin x ^ 2) + 4) / (x * Real.sin x)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
