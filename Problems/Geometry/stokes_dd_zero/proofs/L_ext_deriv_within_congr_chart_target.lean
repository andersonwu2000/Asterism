import Mathlib
import Problems.Geometry.stokes_dd_zero.Defs

open scoped Manifold Bundle ContDiff
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.MExtDeriv

namespace Problems.Geometry.stokes_dd_zero

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open scoped Manifold Bundle ContDiff Topology

-- ext_deriv_within_congr_chart_target: congr for extDerivWithin at base point
-- using equality on (extChartAt I x₀).target, promoted via extChartAt_target_mem_nhdsWithin.
-- Uses extChartAt_target_mem_nhdsWithin to promote local EqOn to nhdsWithin filter equality,
-- then applies Filter.EventuallyEq.extDerivWithin_eq.
theorem ext_deriv_within_congr_chart_target {E : Type*} [NormedAddCommGroup E]
    [NormedSpace ℝ E] {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    (x₀ : M) {m : ℕ} (f g : E → (E [⋀^Fin m]→L[ℝ] ℝ))
    (h : ∀ y ∈ (extChartAt I x₀).target, f y = g y) :
    extDerivWithin f (Set.range I) (extChartAt I x₀ x₀)
      = extDerivWithin g (Set.range I) (extChartAt I x₀ x₀) := by
  apply Filter.EventuallyEq.extDerivWithin_eq _ (h _ (mem_extChartAt_target x₀))
  apply Filter.eventually_of_mem (extChartAt_target_mem_nhdsWithin x₀)
  exact h

end Problems.Geometry.stokes_dd_zero
