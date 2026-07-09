import Library.Geometry.Manifold.DiffFormBundle          -- DiffForm
import Library.Geometry.Manifold.MExtDerivCoord           -- formInCoord, form_in_coord_pullback
import Library.Geometry.Manifold.StokesIntegralDefs       -- localCoeff, topCoeff
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.MExtDerivCoord
import Library.Geometry.Manifold.StokesIntegralDefs

/-!
# Local coefficient transition law for differential forms

This file establishes how the local coefficient of a top-degree differential form transforms
under a change of chart on a smooth manifold. The central identity is a Jacobian-determinant
scaling law relating `localCoeff g x` to `localCoeff g x₀` via the Fréchet derivative of
the chart transition map.

## Main statements

* `topCoeff_compContinuousLinearMap`: for a continuous alternating map `α` and a continuous
  linear map `L`, `topCoeff (α.compContinuousLinearMap L) = L.det * topCoeff α`.
* `localCoeff_coord_change`: `localCoeff g x y` equals the determinant of the chart
  transition's Fréchet derivative times `localCoeff g x₀` at the corresponding point.

## Implementation notes

`topCoeff_compContinuousLinearMap` is a lightweight standalone reproof of a fact that also
appears in `LocalCoeffDensity`; the latter imports the full Stokes tower, which is excluded
from `Defs.lean`.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.LocalCoeffCoordChange

variable {d : ℕ}

/-- For a top-degree continuous alternating form `α` on `EuclideanSpace ℝ (Fin d)` and a
continuous linear map `L`, the top coefficient satisfies
`topCoeff (α.compContinuousLinearMap L) = L.det * topCoeff α`. -/
theorem topCoeff_compContinuousLinearMap
    (α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ)
    (L : EuclideanSpace ℝ (Fin d) →L[ℝ] EuclideanSpace ℝ (Fin d)) :
    topCoeff (α.compContinuousLinearMap L) = L.det * topCoeff α := by
  simp only [topCoeff, ContinuousAlternatingMap.compContinuousLinearMap_apply]
  have heq : α.toAlternatingMap =
      α ⇑(EuclideanSpace.basisFun (Fin d) ℝ) •
      (EuclideanSpace.basisFun (Fin d) ℝ).toBasis.det :=
    AlternatingMap.eq_smul_basis_det (e := (EuclideanSpace.basisFun (Fin d) ℝ).toBasis)
      α.toAlternatingMap
  have step1 : α (⇑L ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ)) =
      α.toAlternatingMap (⇑L ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ)) := rfl
  rw [step1, heq]
  simp only [AlternatingMap.smul_apply]
  rw [show ⇑L ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ) =
        ⇑L.toLinearMap ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ) from rfl,
      Module.Basis.det_comp,
      ← OrthonormalBasis.coe_toBasis (EuclideanSpace.basisFun (Fin d) ℝ),
      Module.Basis.det_self, mul_one, smul_eq_mul]
  rw [← ContinuousLinearMap.det]
  ring

/-- **Local coefficient chart-transition law**: the local coefficient of a top-degree
differential form $g$ transforms by the Jacobian determinant of the chart transition map
when the reference chart changes from `x` to `x₀`. Proved by unfolding `localCoeff` via
`topCoeff` and `form_in_coord_pullback`, then applying
`topCoeff_compContinuousLinearMap`. -/
theorem localCoeff_coord_change : ∀ {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [ChartedSpace EH N] [IsManifold I ∞ N]
    (g : DiffForm I N d) (x x₀ : N) (y : EuclideanSpace ℝ (Fin d))
    (_hy : y ∈ (extChartAt I x).target)
    (_hy' : (extChartAt I x).symm y ∈ (chartAt EH x₀).source),
    localCoeff g x y
      = (fderivWithin ℝ (↑(extChartAt I x₀) ∘ ↑(extChartAt I x).symm) (Set.range I) y).det
        * localCoeff g x₀ (extChartAt I x₀ ((extChartAt I x).symm y)) := by
  intro d EH _ I N _ _ _ g x x₀ y hy hy'
  simp only [localCoeff]
  rw [form_in_coord_pullback I g x x₀ y hy hy']
  exact topCoeff_compContinuousLinearMap _ _

end Library.Geometry.Manifold.LocalCoeffCoordChange
