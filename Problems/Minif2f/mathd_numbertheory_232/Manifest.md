---
problem: Minif2f.mathd_numbertheory_232
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_232 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_232`.

## Statement
∀ (x y z : ZMod 31) (h₀ : x = 3⁻¹) (h₁ : y = 5⁻¹) (h₂ : z = (x + y)⁻¹), z = 29

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
