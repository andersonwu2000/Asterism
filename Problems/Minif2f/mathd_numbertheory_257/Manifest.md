---
problem: Minif2f.mathd_numbertheory_257
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_257 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_257`.

## Statement
∀ (x : ℕ) (h₀ : 1 ≤ x ∧ x ≤ 100) (h₁ : 77 ∣ (∑ k ∈ Finset.range 101, k) - x), x = 45

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
