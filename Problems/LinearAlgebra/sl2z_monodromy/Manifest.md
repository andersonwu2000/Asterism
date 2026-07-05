---
problem: LinearAlgebra.sl2z_monodromy
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
paper: 1d60ef74ee5d
---

# LinearAlgebra.sl2z_monodromy — trace dichotomy for torus-bundle monodromies

## Statement

The bound paper (geo3, §2.8 p.19 and §3.2 p.20) classifies torus bundles
over S¹ by the trace of the monodromy matrix `A ∈ SL(2,ℤ)`: finite-order
monodromy gives Euclidean geometry, `|tr A| > 2` (Anosov) gives Sol.
Formalize the algebraic core of that trichotomy, for
`A : Matrix.SpecialLinearGroup (Fin 2) ℤ`:

### Deliverables

`MarkDeliverable` each; then `Ingest`:

- `sl2z_small_trace_finite_order` — if `|tr A| < 2` then `A ^ 12 = 1`.
- `sl2z_large_trace_infinite_order` — if `|tr A| > 2` then
  `A ^ n ≠ 1` for every `n > 0`.

Consult the paper for the intended geometric meaning when in doubt
about statement shape; the paper is the authority on the trichotomy's
boundaries (the `|tr A| = 2` reducible case is deliberately NOT in
scope).

### Proof shape

- Small trace: `tr A ∈ {-1, 0, 1}`; Cayley–Hamilton in SL(2,ℤ) gives
  `A² = (tr A)·A - 1`, so each case yields `A⁴ = 1`, `A⁶ = 1`, or
  `A³ = 1` — all divide 12.
- Large trace: let `tₙ = tr (Aⁿ)`; the recurrence
  `tₙ₊₁ = (tr A)·tₙ - tₙ₋₁` with `t₀ = 2, t₁ = tr A` gives
  `|tₙ₊₁| > |tₙ| ≥ 2` by integer induction, so `tr (Aⁿ) ≠ 2 = tr 1`.

ALWAYS search mathlib first (`Matrix.SpecialLinearGroup`,
`ModularGroup`, `Matrix.trace`) — cite what exists. Do NOT introduce
axioms or `sorry`-bearing shortcuts.
