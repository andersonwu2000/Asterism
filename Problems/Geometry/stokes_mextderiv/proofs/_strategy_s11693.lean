import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_ext_deriv_locality_pullback
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_differentiable_within_range

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange

-- Transport identity = pullback commutes with extDerivWithin, along the chart
-- transition f := extChartAt I x ∘ (extChartAt I x₀).symm at y₀ := extChartAt I x₀ x.
-- (B) h_fcc: formCoordChange unfolds to precomposition with fderivWithin ℝ f (range I) y₀
--     (formCoordChange def + tangentBundleCore_coordChange_achart) — inline simp.
-- (D) h_loc (sub-goal ext_deriv_locality_pullback): extDerivWithin of formInCoord I φ x₀
--     equals extDerivWithin of the pullback form (locality via sibling form_in_coord_pullback
--     + EventuallyEq.extDerivWithin_eq).
-- (C) h_pull: extDerivWithin_pullback moves extDerivWithin through the pullback; side
--     conditions: h_f transition smoothness (contDiffWithinAt_ext_coord_change, inline),
--     h_ω differentiability of formInCoord (sub-goal form_in_coord_differentiable_within_range),
--     uniqueDiffOn/closure-interior/MapsTo for range I — inline.
-- Chain: rw [h_fcc, h_loc, h_pull, hfy₀] closes the goal.
theorem s11693
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ x : M)
    (hx : x ∈ (chartAt H x₀).source) :
    formCoordChange I (k + 1) (achart H x) (achart H x₀) x
        (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))
      = extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)  := by
  have hx' : x ∈ (extChartAt I x₀).source := by
    simpa only [extChartAt_source] using hx
  have hfy₀ : (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (extChartAt I x₀ x)
      = extChartAt I x x :=
    congrArg (extChartAt I x) ((extChartAt I x₀).left_inv hx')
  -- (B) formCoordChange = precomposition with the transition fderiv
  have h_fcc : formCoordChange I (k + 1) (achart H x) (achart H x₀) x
      (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))
    = (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x)).compContinuousLinearMap
        (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I)
          (extChartAt I x₀ x)) := by
    simp only [formCoordChange, ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
      tangentBundleCore_coordChange_achart]
  -- transition map smoothness within range I: direct Mathlib cite
  have h_f : ContDiffWithinAt ℝ ∞ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm)
      (Set.range I) (extChartAt I x₀ x) := by
    refine contDiffWithinAt_ext_coord_change x x₀ ?_
    rw [PartialEquiv.trans_source]
    refine ⟨(extChartAt I x₀).map_source hx', ?_⟩
    simp only [Set.mem_preimage, (extChartAt I x₀).left_inv hx']
    exact mem_extChartAt_source x
  -- (sub-goal) differentiability of formInCoord within range I
  have h_ω : DifferentiableWithinAt ℝ (formInCoord I φ x) (Set.range I) (extChartAt I x x) :=
    form_in_coord_differentiable_within_range I φ x
  -- (sub-goal) locality: x₀-coordinate form agrees with the pullback form near the point
  have h_loc : extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)
      = extDerivWithin
          (fun y => (formInCoord I φ x
              ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) y)).compContinuousLinearMap
            (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I) y))
          (Set.range I) (extChartAt I x₀ x) :=
    ext_deriv_locality_pullback I φ x₀ x hx
  -- (C) pullback commutes with extDerivWithin
  have h_pull : extDerivWithin
        (fun y => (formInCoord I φ x
            ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) y)).compContinuousLinearMap
          (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I) y))
        (Set.range I) (extChartAt I x₀ x)
      = (extDerivWithin (formInCoord I φ x) (Set.range I)
            ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm)
              (extChartAt I x₀ x))).compContinuousLinearMap
          (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I)
            (extChartAt I x₀ x)) := by
    apply extDerivWithin_pullback (r := ∞) (hfy₀ ▸ h_ω) h_f ?_ I.uniqueDiffOn ?_ ?_ ?_
    · simp only [minSmoothness_of_isRCLikeNormedField]
      exact ENat.LEInfty.out
    · exact I.range_subset_closure_interior (Set.mem_range_self _)
    · exact Set.mem_range_self _
    · intro y _
      exact ⟨chartAt H x ((extChartAt I x₀).symm y), rfl⟩
  rw [h_fcc, h_loc, h_pull, hfy₀]

end Problems.Geometry.stokes_mextderiv
