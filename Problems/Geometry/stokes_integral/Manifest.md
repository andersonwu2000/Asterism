---
problem: Geometry.stokes_integral
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_integral — the canonical integral operator ∫_N

## Statement
`DiffForm.integral (0 : DiffForm I N d) = 0` — the integral of the zero top-form is
zero. A sanity lemma owning the `∫_N` vocabulary: the general `OrientedManifold`
class, `topCoeff`, `localCoeff`, and `DiffForm.integral` (the partition-of-unity sum).

## Setting
`∫_N` is general over any oriented compact `d`-manifold `N` modelled on
`EuclideanSpace ℝ (Fin d)` — so `∫_M` (M with boundary) and `∫_∂M` (boundaryless ∂M)
are THIS one operator at different `(I, N)`. Cites P4 (`DiffForm`), P5 (`formInCoord`).

## Lemma hints
- `localCoeff (0 : DiffForm I N d) x = topCoeff (formInCoord I 0 x ·)`; `formInCoord`
  of the zero section is the zero map (`ContinuousLinearMap.map_zero` /
  `ContMDiffSection`'s `0` is the zero section), so `topCoeff 0 = 0` and `localCoeff 0 = 0`.
- Each PoU term has factor `localCoeff 0 = 0`, so `∫ … = 0`; `finsum_eq_zero` /
  `MeasureTheory.integral_zero`.
- `ContinuousAlternatingMap.zero_apply`, `EuclideanSpace.basisFun`.
