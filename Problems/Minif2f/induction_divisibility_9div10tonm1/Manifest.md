---
problem: Minif2f.induction_divisibility_9div10tonm1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.induction_divisibility_9div10tonm1 — imported from miniF2F

Original miniF2F theorem name: `induction_divisibility_9div10tonm1`.

## Statement
∀ (n : ℕ) (h₀ : 0 < n), 9 ∣ 10 ^ n - 1

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
