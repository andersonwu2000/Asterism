import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_smooth

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange

-- form_in_coord_differentiable_within_range: DifferentiableWithinAt on range I follows from
-- ContDiffOn on (extChartAt I x).target (form_in_coord_smooth) via ContDiffWithinAt +
-- DifferentiableWithinAt.mono_of_mem_nhdsWithin using extChartAt_target_mem_nhdsWithin.
theorem form_in_coord_differentiable_within_range
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x : M) :
    DifferentiableWithinAt ℝ (formInCoord I φ x) (Set.range I) (extChartAt I x x) := by
  have h1 : ContDiffOn ℝ ∞ (formInCoord I φ x) (extChartAt I x).target :=
    form_in_coord_smooth I φ x
  have hmem : extChartAt I x x ∈ (extChartAt I x).target := mem_extChartAt_target x
  have h2 : DifferentiableWithinAt ℝ (formInCoord I φ x) (extChartAt I x).target
      (extChartAt I x x) :=
    (h1 (extChartAt I x x) hmem).differentiableWithinAt (by norm_num)
  exact h2.mono_of_mem_nhdsWithin (extChartAt_target_mem_nhdsWithin x)

end Problems.Geometry.stokes_mextderiv
