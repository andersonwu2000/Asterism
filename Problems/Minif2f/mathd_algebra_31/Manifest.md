---
problem: Minif2f.mathd_algebra_31
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_algebra_31 — imported from miniF2F

Original miniF2F theorem name: `mathd_algebra_31`.

## Statement
∀ (x : NNReal) (u : ℕ → NNReal) (h₀ : ∀ n, u (n + 1) = NNReal.sqrt (x + u n)) (h₁ : Filter.Tendsto u Filter.atTop (𝓝 9)), 9 = NNReal.sqrt (x + 9)

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
