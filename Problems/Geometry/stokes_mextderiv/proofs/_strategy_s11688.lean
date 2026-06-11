import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_ext_deriv_fixed_chart_contmdiff_at
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_pullback
import Problems.Geometry.stokes_mextderiv.proofs.L_mext_deriv_triv_read

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle

-- Fix x₀; reduce to the trivialized read via contMDiffAt_section_iff at x₀'s trivialization.
-- Near x₀ the read equals the fixed-chart function x ↦ extDerivWithin (formInCoord I φ x₀)
-- (range I) (extChartAt I x₀ x) [sub-goal mext_deriv_triv_read, fed by the chart-transition
-- pullback identity form_in_coord_pullback]; that fixed-chart function is ContMDiffAt
-- [sub-goal ext_deriv_fixed_chart_contmdiff_at, from form_in_coord_smooth +
-- ext_deriv_within_smooth]. Glue by ContMDiffAt.congr_of_eventuallyEq on chart source.
theorem s11688 : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k),
    ContMDiff I (I.prod 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ)) ∞
      (fun x => Bundle.TotalSpace.mk'
        (E := fun y => (formBundleCore (M := M) I (k + 1)).Fiber y)
        (E [⋀^Fin (k + 1)]→L[ℝ] ℝ) x (mextDerivFun I φ x))  := by
  intro E _ _ H _ I M _ _ _ k φ x₀
  have hx₀ : x₀ ∈ (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
      (formBundleCore (M := M) I (k + 1)).Fiber x₀).baseSet :=
    FiberBundle.mem_baseSet_trivializationAt' x₀
  rw [Bundle.Trivialization.contMDiffAt_section_iff _ hx₀]
  have h_smooth : ContMDiffAt I 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (fun x => extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)) x₀ :=
    ext_deriv_fixed_chart_contmdiff_at I φ x₀
  refine h_smooth.congr_of_eventuallyEq ?_
  filter_upwards [(chartAt H x₀).open_source.mem_nhds (mem_chart_source H x₀)] with x hx
  exact mext_deriv_triv_read I φ x₀ x hx

end Problems.Geometry.stokes_mextderiv
