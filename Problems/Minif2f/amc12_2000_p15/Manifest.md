---
problem: Minif2f.amc12_2000_p15
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12_2000_p15 — imported from miniF2F

Original miniF2F theorem name: `amc12_2000_p15`.

## Statement
∀ (f : ℂ → ℂ) (h₀ : ∀ x, f (x / 3) = x ^ 2 + x + 1) (h₁ : Fintype (f ⁻¹' {7})), (∑ y ∈ (f ⁻¹' {7}).toFinset, y / 3) = -1 / 9

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
