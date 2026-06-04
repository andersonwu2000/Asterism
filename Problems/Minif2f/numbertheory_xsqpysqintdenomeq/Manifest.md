---
problem: Minif2f.numbertheory_xsqpysqintdenomeq
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.numbertheory_xsqpysqintdenomeq — imported from miniF2F

Original miniF2F theorem name: `numbertheory_xsqpysqintdenomeq`.

## Statement
∀ (x y : ℚ) (h₀ : (x ^ 2 + y ^ 2).den = 1), x.den = y.den

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
