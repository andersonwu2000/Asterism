---
problem: Minif2f.mathd_numbertheory_461
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_461 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_461`.

## Statement
∀ (n : ℕ) (h₀ : n = Finset.card (Finset.filter (fun x => Nat.gcd x 8 = 1) (Finset.Icc 1 7))), 3 ^ n % 8 = 1

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
