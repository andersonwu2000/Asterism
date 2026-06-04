---
problem: Minif2f.mathd_algebra_185
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_185 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_185`.

## Statement
∀ (s : Finset ℤ) (f : ℤ → ℤ) (h₀ : ∀ x, f x = abs (x + 4)) (h₁ : ∀ x, x ∈ s ↔ f x < 9), s.card = 17

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
