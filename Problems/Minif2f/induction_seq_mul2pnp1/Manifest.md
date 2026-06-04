---
problem: Minif2f.induction_seq_mul2pnp1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.induction_seq_mul2pnp1 — imported from miniF2F

Original miniF2F theorem name: `induction_seq_mul2pnp1`.

## Statement
∀ (n : ℕ) (u : ℕ → ℕ) (h₀ : u 0 = 0) (h₁ : ∀ n, u (n + 1) = 2 * u n + (n + 1)), u n = 2 ^ (n + 1) - (n + 2)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
