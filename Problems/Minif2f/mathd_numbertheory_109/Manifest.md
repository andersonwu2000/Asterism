---
problem: Minif2f.mathd_numbertheory_109
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_109 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_109`.

## Statement
∀ (v : ℕ → ℕ) (h₀ : ∀ n, v n = 2 * n - 1), (∑ k ∈ Finset.Icc 1 100, v k) % 7 = 4

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
