---
problem: Minif2f.mathd_algebra_15
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_15 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_15`.

## Statement
∀ (s : ℕ → ℕ → ℕ) (h₀ : ∀ a b, 0 < a ∧ 0 < b → s a b = a ^ (b : ℕ) + b ^ (a : ℕ)), s 2 6 = 100

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
