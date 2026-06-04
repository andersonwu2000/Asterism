---
problem: Minif2f.induction_ineq_nsqlefactn
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.induction_ineq_nsqlefactn — imported from miniF2F

Original miniF2F theorem name: `induction_ineq_nsqlefactn`.

## Statement
∀ (n : ℕ) (h₀ : 4 ≤ n), n ^ 2 ≤ n !

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
