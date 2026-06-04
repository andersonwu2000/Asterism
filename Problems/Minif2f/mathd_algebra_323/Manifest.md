---
problem: Minif2f.mathd_algebra_323
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_323 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_323`.

## Statement
∀ (σ : Equiv ℝ ℝ) (h : ∀ x, σ.1 x = x ^ 3 - 8), σ.2 (σ.1 (σ.2 19)) = 3

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
