---
problem: Minif2f.amc12a_2002_p21
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.amc12a_2002_p21 — imported from miniF2F

Original miniF2F theorem name: `amc12a_2002_p21`.

## Statement
∀ (u : ℕ → ℕ) (h₀ : u 0 = 4) (h₁ : u 1 = 7) (h₂ : ∀ n ≥ 2, u (n + 2) = (u n + u (n + 1)) % 10), ∀ n, (∑ k ∈ Finset.range n, u k) > 10000 → 1999 ≤ n

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
