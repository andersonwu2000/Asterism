import Library.Geometry.Manifold.DiffFormBundle    -- DiffForm
import Library.Geometry.Manifold.MExtDerivCoord     -- formInCoord
import Library.Geometry.Manifold.StokesIntegralDefs
import Mathlib.Algebra.BigOperators.Finprod
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Mathlib.Geometry.Manifold.VectorBundle.SmoothSection
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Topology.Algebra.Module.Alternating.Basic

/-!
# Stokes Integral of the Zero Form

This file proves that the Stokes integral of the zero differential form on a compact
oriented manifold is zero. The argument factors through the pointwise vanishing of
the local scalar coefficient of the zero form.

## Main statements

- `localCoeff_zero`: the local scalar coefficient of the zero `DiffForm` vanishes identically.
- `integral_zero_of_localCoeff_zero`: if `localCoeff φ x y = 0` for all `x` and `y`,
  then `DiffForm.integral φ = 0`.
- `integral_zero`: `DiffForm.integral (0 : DiffForm I N d) = 0`.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.StokesIntegral

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N]

/-- The local scalar coefficient of the zero differential form vanishes identically.
Follows by unfolding `localCoeff`, `topCoeff`, and `formInCoord`, then applying
`map_zero` and `ContinuousAlternatingMap.coe_zero`. -/
theorem localCoeff_zero (x : N) (y : EuclideanSpace ℝ (Fin d)) :
    localCoeff (0 : DiffForm I N d) x y = 0 := by
  simp only [localCoeff, topCoeff, formInCoord,
             ContMDiffSection.coe_zero, Pi.zero_apply, map_zero,
             ContinuousAlternatingMap.coe_zero]

/-- If the local scalar coefficient of a differential form `φ` vanishes identically,
then its Stokes integral is zero. Each summand in the partition-of-unity decomposition
of `DiffForm.integral` contains the vanishing factor as its integrand. -/
theorem integral_zero_of_localCoeff_zero [OrientedManifold I N] (φ : DiffForm I N d)
    (hzero : ∀ (x : N) (y : EuclideanSpace ℝ (Fin d)), localCoeff φ x y = 0) :
    DiffForm.integral φ = 0 := by
  simp only [DiffForm.integral]
  apply finsum_eq_zero_of_forall_eq_zero
  intro i
  conv_lhs => arg 2; ext y; rw [show localCoeff φ _ y = 0 from hzero _ y]
  simp [mul_zero]

/-- The Stokes integral of the zero differential form on a compact oriented manifold
is zero. -/
theorem integral_zero [OrientedManifold I N] : DiffForm.integral (0 : DiffForm I N d) = 0 :=
  integral_zero_of_localCoeff_zero 0 (fun x y ↦ localCoeff_zero x y)

end Library.Geometry.Manifold.StokesIntegral
