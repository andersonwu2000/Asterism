---
problem: Geometry.integral_param
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.integral_param — the multi-chart density transition law

## Statement
For a top `d`-form `g` on a `d`-manifold `N` (modelled on `EuclideanSpace ℝ (Fin d)`), the local
scalar density `localCoeff g x` read in the chart at `x` relates to the density read in the chart
at another point `x₀` by the Jacobian determinant of the chart transition. For `y ∈
(extChartAt I x).target` with `(extChartAt I x).symm y ∈ (chartAt EH x₀).source`:

`localCoeff g x y = det(d(extChartAt x₀ ∘ (extChartAt x).symm)(y)) * localCoeff g x₀ (extChartAt x₀ ((extChartAt x).symm y))`

This is the **hard core of the multi-chart parametrization integral**: how a top-form's density
transforms across overlapping charts (the determinant factor is exactly the change-of-variables
Jacobian). The full "∫_N g via an arbitrary parametrization spanning multiple charts" cites this.

## Setting
Stress-test problem for the Model B knowledge base + target-2 KB retrieval, built on the proved
Stokes-tower Library. **Not** harvested into the Library (`library: false`) — re-proved later
alongside the Library KB. The proof must cite the Library's differential-form chart-transition
law, so it exercises Library-citation plumbing end to end.

## Lemma hints
- `Library.Geometry.Manifold.MExtDerivCoord.form_in_coord_pullback` :
  `formInCoord I φ x y = (formInCoord I φ x₀ (extChartAt I x₀ ((extChartAt I x).symm y))).compContinuousLinearMap (fderivWithin ℝ (↑(extChartAt I x₀) ∘ ↑(extChartAt I x).symm) (Set.range I) y)`
  — the form's coordinate rep at `x` pulled back to `x₀` via the transition derivative. Take
  `topCoeff` of both sides (its hypotheses `hy` / `hy'` are exactly this goal's).
- `Library.Geometry.Manifold.StokesIntegralDefs` : `localCoeff φ x y = topCoeff (formInCoord I φ x y)`
  and `topCoeff α = α (EuclideanSpace.basisFun (Fin d) ℝ)` (both by `rfl`/unfold).
- Determinant step: `topCoeff (α.compContinuousLinearMap L) = L.det * topCoeff α` for a top
  `d`-form `α` — precomposing a top alternating form by a linear map scales the standard-basis
  coefficient by `det L`. Find the Mathlib alternating-map / determinant lemma (via
  `ContinuousAlternatingMap.compContinuousLinearMap` → `AlternatingMap`, or the basis-image
  `Matrix.det` identity).
