---
problem: Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva — imported from miniF2F

Original miniF2F theorem name: `algebra_amgm_sumasqdivbsqgeqsumbdiva`.

## Statement
∀ (a b c : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c), a ^ 2 / b ^ 2 + b ^ 2 / c ^ 2 + c ^ 2 / a ^ 2 ≥ b / a + c / b + a / c

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
