import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_smooth
import Problems.Geometry.stokes_mextderiv.proofs.L_ext_deriv_within_smooth
import Problems.Geometry.stokes_mextderiv.proofs.L_ext_deriv_within_eq_of_mem_nhds_within


namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle

-- Bridge extDerivWithin from (range I) to (extChartAt I x₀).target by set-locality
-- [sub-goal ext_deriv_within_eq_of_mem_nhds_within], get ContDiffOn on target from
-- form_in_coord_smooth + ext_deriv_within_smooth + uniqueDiffOn_extChartAt_target,
-- then compose with the smooth chart map and localize at x₀.
theorem s11691
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ContMDiffAt I 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (fun x => extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x))
      x₀  := by
  have h_form : ContDiffOn ℝ ∞ (formInCoord I φ x₀) ((extChartAt I x₀).target) :=
    form_in_coord_smooth I φ x₀
  have h_target : ContDiffOn ℝ ∞
      (extDerivWithin (formInCoord I φ x₀) ((extChartAt I x₀).target))
      ((extChartAt I x₀).target) :=
    ext_deriv_within_smooth h_form (uniqueDiffOn_extChartAt_target x₀)
  have h_eqon : Set.EqOn (extDerivWithin (formInCoord I φ x₀) (Set.range I))
      (extDerivWithin (formInCoord I φ x₀) ((extChartAt I x₀).target))
      ((extChartAt I x₀).target) := by
    intro y hy
    exact ext_deriv_within_eq_of_mem_nhds_within
      (extChartAt_target_mem_nhdsWithin_of_mem hy)
      (I.uniqueDiffOn _ ((extChartAt_target_subset_range x₀) hy))
      ((h_form y hy).differentiableWithinAt (by simp))

  have h_range : ContDiffOn ℝ ∞
      (extDerivWithin (formInCoord I φ x₀) (Set.range I)) ((extChartAt I x₀).target) :=
    h_target.congr h_eqon
  have h_outer : ContMDiffOn 𝓘(ℝ, E) 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (extDerivWithin (formInCoord I φ x₀) (Set.range I)) ((extChartAt I x₀).target) :=
    contMDiffOn_iff_contDiffOn.mpr h_range
  have h_chart : ContMDiffOn I 𝓘(ℝ, E) ∞ (extChartAt I x₀) ((chartAt H x₀).source) :=
    contMDiffOn_extChartAt
  have h_maps : Set.MapsTo (extChartAt I x₀) ((chartAt H x₀).source)
      ((extChartAt I x₀).target) := by
    intro x hx
    exact (extChartAt I x₀).map_source (by simpa [extChartAt_source] using hx)
  have h_comp : ContMDiffOn I 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (fun x => extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x))
      ((chartAt H x₀).source) :=
    h_outer.comp h_chart h_maps
  exact h_comp.contMDiffAt
    ((chartAt H x₀).open_source.mem_nhds (mem_chart_source H x₀))

end Problems.Geometry.stokes_mextderiv

