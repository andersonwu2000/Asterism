---
problem: Minif2f.amc12a_2020_p21
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2020_p21 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2020_p21`.

## Statement
∀ (S : Finset ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ 5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n), S.card = 48

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
