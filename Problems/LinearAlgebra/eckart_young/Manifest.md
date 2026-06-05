---
problem: LinearAlgebra.eckart_young
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.eckart_young — Eckart–Young (best low-rank approximation)

## Statement
∀ {𝕜} [RCLike 𝕜] {E F} [inner product spaces, finite-dim] (T : E →ₗ[𝕜] F) (k : ℕ),
  IsLeast
    {r : ℝ | ∃ S : E →ₗ[𝕜] F, Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
       r = ‖toContinuousLinearMap (T - S)‖}
    (T.singularValues k)

## Setting
- `T.singularValues` (mathlib `LinearMap.singularValues`,
  `Analysis/InnerProductSpace/SingularValues.lean`): the singular values,
  **antitone** (σ₀ ≥ σ₁ ≥ …), 0-indexed; `σ_i = 0` for `i ≥ finrank E`.
- Operator (spectral) norm via `LinearMap.toContinuousLinearMap` (finite-dim ⇒
  continuous), `‖·‖` = `ContinuousLinearMap.opNorm`.
- Conclusion (**Eckart–Young**): over all `S` of rank `≤ k`, the minimum
  operator-norm distance `‖T − S‖` is exactly `σ_k`, and it is attained (by the
  truncated SVD). `IsLeast` packages both the lower bound and attainment.
  (k=0 recovers `‖T‖ = σ₀`.)

## Route

Two parts (IsLeast = membership ∧ lower bound).

1. **Attainment (∈).** Build the rank-`k` truncated SVD `T_k`: cite the SVD
   Library (#38, `Library.LinearAlgebra.SVD.Basic.main` / `svd_complete_from_eigenbasis`)
   for orthonormal bases `b_E, b_F` diagonalizing `T`; let `T_k` keep the top-`k`
   singular triples and zero the rest. Then `finrank (range T_k) ≤ k` and
   `‖T − T_k‖ = σ_k` (the largest remaining singular value), so `σ_k` is in the set.
2. **Lower bound (∀ S, rank ≤ k ⇒ ‖T − S‖ ≥ σ_k).** Dimension pigeonhole:
   `ker S` has `finrank ≥ n − k`; intersect it with the span of the top `k+1`
   right-singular vectors (dim `k+1`) — by `(n−k) + (k+1) > n` the intersection has
   a nonzero `x` (**reuse `Library.LinearAlgebra.CourantFischer.SubmoduleLemmas.
   subspace_inter_nonzero_of_finrank`, #97**). For that `x`, `S x = 0` so
   `‖(T−S) x‖ = ‖T x‖ ≥ σ_k ‖x‖`, hence `‖T − S‖ ≥ σ_k`.

## Lemma hints

Library (cite, do not reconstruct):
- `Library.LinearAlgebra.SVD.*` (#38) — the diagonalizing orthonormal bases +
  `singularValues` diagonal form. Read `Library/INDEX.md` for decl names
  (`SVD.Basic.main`, `SVD.SingularValues.*`, `SVD.BasisConstruction.*`).
- `Library.LinearAlgebra.CourantFischer.SubmoduleLemmas.subspace_inter_nonzero_of_finrank`
  (#97) — the dimension-pigeonhole intersection lemma (reuse it).

Mathlib (cite, foundational):
- `LinearMap.singularValues`, `…singularValues_antitone`, `…singularValues_fin`,
  `…singularValues_of_finrank_le`, `…card_support_singularValues`.
- `LinearMap.toContinuousLinearMap`, `ContinuousLinearMap.opNorm`,
  `ContinuousLinearMap.le_opNorm` / `opNorm_le_bound`.
- `LinearMap.range`, `Module.finrank`, `Submodule.finrank_le`, `IsLeast`,
  `lowerBounds`.

## R1 — search before reconstructing (hard rule)

Before any new `lemma`/`def`: `Grep` mathlib + `loogle`; reuse + thin bridge.
Do NOT rebuild SVD (Library #38), the singular-value API (mathlib), or the
dimension-pigeonhole lemma (Library #97). New Forwards must open with
`## Forward rationale — Grep + Loogle confirmed missing: <keywords>`.

## Forbidden angles
- Searching mathlib for a ready-made Eckart–Young / best-low-rank — confirmed
  missing. (If you find it, `RequestUserAmend`.)
- Re-deriving SVD or the singular-value machinery instead of citing #38 / mathlib.
