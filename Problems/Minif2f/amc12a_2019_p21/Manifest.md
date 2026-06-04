---
problem: Minif2f.amc12a_2019_p21
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2019_p21 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2019_p21`.

## Statement
∀ (z : ℂ) (h₀ : z = (1 + Complex.I) / Real.sqrt 2), ((∑ k ∈ Finset.Icc 1 12, z ^ k ^ 2) * (∑ k ∈ Finset.Icc 1 12, 1 / z ^ k ^ 2)) = 36

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
