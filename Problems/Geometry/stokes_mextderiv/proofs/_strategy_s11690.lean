import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_eq_coord_change

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange

-- Both sides reduce to formCoordChange reads via the proved brick
-- form_in_coord_eq_coord_change (at x via right_inv hy, at x₀ via hy'); the residue is
-- the tangentBundleCore cocycle coordChange_comp with the (x→x₀) leg rewritten to the
-- fderivWithin transition by tangentBundleCore_coordChange_achart.
theorem s11690
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x x₀ : M) (y : E)
    (hy : y ∈ (extChartAt I x).target)
    (hy' : (extChartAt I x).symm y ∈ (chartAt H x₀).source) :
    formInCoord I φ x y =
      (formInCoord I φ x₀ (extChartAt I x₀ ((extChartAt I x).symm y))).compContinuousLinearMap
        (fderivWithin ℝ (↑(extChartAt I x₀) ∘ ↑(extChartAt I x).symm) (Set.range I) y)  := by
  have hy_src : (extChartAt I x).symm y ∈ (extChartAt I x).source :=
    (extChartAt I x).map_target hy
  set p := (extChartAt I x).symm y with hp_def
  have hp_x : p ∈ (chartAt H x).source := by simpa only [extChartAt_source] using hy_src
  have h_y : extChartAt I x p = y := (extChartAt I x).right_inv hy
  have hL : formInCoord I φ x y = formCoordChange I k (achart H p) (achart H x) p (φ p) := by
    rw [← h_y]
    exact form_in_coord_eq_coord_change I φ x hp_x
  have hR : formInCoord I φ x₀ (extChartAt I x₀ p)
      = formCoordChange I k (achart H p) (achart H x₀) p (φ p) :=
    form_in_coord_eq_coord_change I φ x₀ hy'
  rw [hL, hR]
  have hD : (tangentBundleCore I M).coordChange (achart H x) (achart H x₀) p
      = fderivWithin ℝ (↑(extChartAt I x₀) ∘ ↑(extChartAt I x).symm) (Set.range I) y := by
    rw [← h_y]
    exact tangentBundleCore_coordChange_achart x x₀ p
  rw [← hD]
  simp only [formCoordChange, ContinuousAlternatingMap.compContinuousLinearMapCLM_apply]
  ext m
  simp only [ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1
  funext i
  exact ((tangentBundleCore I M).coordChange_comp (achart H x) (achart H x₀) (achart H p) p
    ⟨⟨hp_x, hy'⟩, mem_chart_source H p⟩ (m i)).symm

end Problems.Geometry.stokes_mextderiv
