---
problem: Minif2f.amc12a_2002_p1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2002_p1 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2002_p1`.

## Statement
∀ (f : ℂ → ℂ) (h₀ : ∀ x, f x = (2 * x + 3) * (x - 4) + (2 * x + 3) * (x - 6)) (h₁ : Fintype (f ⁻¹' {0})), (∑ y ∈ (f ⁻¹' {0}).toFinset, y) = 7 / 2

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
