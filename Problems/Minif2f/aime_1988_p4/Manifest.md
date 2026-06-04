---
problem: Minif2f.aime_1988_p4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.aime_1988_p4 — imported from miniF2F

Original miniF2F theorem name: `aime_1988_p4`.

## Statement
∀ (n : ℕ) (a : ℕ → ℝ) (h₀ : ∀ n, abs (a n) < 1) (h₁ : (∑ k ∈ Finset.range n, abs (a k)) = 19 + abs (∑ k ∈ Finset.range n, a k)), 20 ≤ n

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
