---
problem: Minif2f.mathd_numbertheory_13
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_13 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_13`.

## Statement
∀ (u v : ℕ) (S : Set ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46) (h₁ : IsLeast S u) (h₂ : IsLeast (S \ {u}) v), (u + v : ℚ) / 2 = 64

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
