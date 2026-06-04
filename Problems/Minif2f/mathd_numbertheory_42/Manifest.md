---
problem: Minif2f.mathd_numbertheory_42
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_42 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_42`.

## Statement
∀ (S : Set ℕ) (u v : ℕ) (h₀ : ∀ a : ℕ, a ∈ S ↔ 0 < a ∧ 27 * a % 40 = 17) (h₁ : IsLeast S u) (h₂ : IsLeast (S \ {u}) v), u + v = 62

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
