import Mathlib
import Problems.Geometry.stokes_dd_zero.Defs

open scoped Manifold Bundle ContDiff
open Library.Geometry.Manifold.MExtDeriv

namespace Problems.Geometry.stokes_dd_zero

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open scoped Manifold Bundle ContDiff Topology

-- ext_deriv_within_dd_zero_at_base: model-space d∘d=0 via extDerivWithin_extDerivWithin_apply
-- Uses form_in_coord_smooth, I.uniqueDiffOn, I.range_subset_closure_interior.
theorem ext_deriv_within_dd_zero_at_base {E : Type*} [NormedAddCommGroup E]
    [NormedSpace ℝ E] {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    extDerivWithin (extDerivWithin (formInCoord I φ x₀) (Set.range I))
      (Set.range I) (extChartAt I x₀ x₀) = 0 := by
  apply extDerivWithin_extDerivWithin_apply
  · -- ContDiffWithinAt on Set.range I: use form_in_coord_smooth + mono_of_mem_nhdsWithin
    exact ((form_in_coord_smooth I φ x₀).contDiffWithinAt
      (mem_extChartAt_target x₀)).mono_of_mem_nhdsWithin
      (extChartAt_target_mem_nhdsWithin x₀)
  · -- minSmoothness ℝ 2 ≤ ∞
    norm_num [minSmoothness]; exact WithTop.coe_le_coe.mpr le_top
  · exact I.uniqueDiffOn
  · exact I.range_subset_closure_interior
      (extChartAt_target_subset_range x₀ (mem_extChartAt_target x₀))
  · exact extChartAt_target_subset_range x₀ (mem_extChartAt_target x₀)

end Problems.Geometry.stokes_dd_zero
