---
problem: Minif2f.mathd_algebra_451
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_451 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_451`.

## Statement
∀ (σ : Equiv ℝ ℝ) (h₀ : σ.2 (-15) = 0) (h₁ : σ.2 0 = 3) (h₂ : σ.2 3 = 9) (h₃ : σ.2 9 = 20), σ.1 (σ.1 9) = 0

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
