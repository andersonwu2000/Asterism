-- The integral of the zero top-form is zero: a basic sanity lemma that pins down the
-- `∫_N` vocabulary (`OrientedManifold`, `topCoeff`, `localCoeff`, `DiffForm.integral`).
-- `localCoeff 0 = topCoeff (formInCoord 0) = topCoeff 0 = 0`, so every PoU term is 0
-- and the finsum vanishes.
import Mathlib
import Problems.Geometry.stokes_integral.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open MeasureTheory
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord

namespace Problems.Geometry.stokes_integral

theorem main : ∀ {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N],
    DiffForm.integral (0 : DiffForm I N d) = 0 := by
  sorry

end Problems.Geometry.stokes_integral
