---
problem: Minif2f.mathd_numbertheory_156
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_156 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_156`.

## Statement
∀ (n : ℕ) (h₀ : 0 < n), Nat.gcd (n + 7) (2 * n + 1) ≤ 13

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
