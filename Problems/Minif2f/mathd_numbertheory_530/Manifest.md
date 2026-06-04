---
problem: Minif2f.mathd_numbertheory_530
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_530 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_530`.

## Statement
∀ (n k : ℕ) (h₀ : 0 < n ∧ 0 < k) (h₀ : (n : ℝ) / k < 6) (h₁ : (5 : ℝ) < n / k), 22 ≤ Nat.lcm n k / Nat.gcd n k

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
