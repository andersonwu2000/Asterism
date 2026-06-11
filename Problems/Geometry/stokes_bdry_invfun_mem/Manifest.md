---
problem: Geometry.stokes_bdry_invfun_mem
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_bdry_invfun_mem — the boundary chart's inverse lands in ∂M

## Statement
For a boundary point `p : Bdry n M` and `z` with `faceEmbed z ∈ (extChartAt (𝓡∂ (n+1)) p.val).target`,
the inverse `(extChartAt (𝓡∂ (n+1)) p.val).symm (faceEmbed z)` lies in
`(𝓡∂ (n+1)).boundary M`. (Prerequisite for the boundary chart's guarded `invFun`.)

## Setting
`Bdry` is cited from `Library.Geometry.ManifoldBoundary.CompactBdry`. `faceEmbed`
places `z` in coordinates `1..n`, so `(faceEmbed z) 0 = 0` — i.e. `faceEmbed z`
lies on the model boundary `{x₀ = 0}`. On the chart target, `extChartAt`'s symm is
the genuine inverse and carries a boundary point of the model to a boundary point
of `M` (boundary is preserved by charts).

## Lemma hints
- `Mathlib/Geometry/Manifold/InteriorBoundary.lean` — `ModelWithCorners.boundary`,
  membership criteria; the chart/`extChartAt` ↔ boundary compatibility lemmas
  (`extChartAt_target`, boundary-preimage characterizations).
- `Mathlib/Geometry/Manifold/Instances/Real.lean` — `EuclideanHalfSpace`,
  `𝓡∂`, the boundary of the half-space is `{x | x 0 = 0}`.
- `faceEmbed z` has `0`-th coordinate `0`: from the `Fin.succ` indexing in the sum
  (no `e₀` term), `EuclideanSpace.basisFun … i.succ 0 = 0`.
- Strategy: show `faceEmbed z` is in the model boundary (`x 0 = 0`), transfer along
  `extChartAt`'s symm using the on-target hypothesis.
