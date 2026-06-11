import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_triv_section_contmdiff_on

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle

namespace Problems.Geometry.stokes_mextderiv

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
-- formInCoord is the trivialized section (p ↦ continuousLinearMapAt at x₀'s triv of φ p)
-- precomposed with (extChartAt I x₀).symm. Sub-goal: that trivialized section is
-- ContMDiffOn on (chartAt H x₀).source. Combine with mathlib's contMDiffOn_extChartAt_symm
-- (chart inverse smooth on target, mapping into the chart source) via ContMDiffOn.comp,
-- then bridge to ContDiffOn with contMDiffOn_iff_contDiffOn (both sides vector spaces).
theorem s11685 {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ContDiffOn ℝ ∞ (formInCoord I φ x₀) ((extChartAt I x₀).target)  := by
  have h_triv : ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun p ↦ Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x₀) p (φ p))
      ((chartAt H x₀).source) := triv_section_contmdiff_on I φ x₀
  have h_symm : ContMDiffOn 𝓘(ℝ, E) I ∞ (extChartAt I x₀).symm (extChartAt I x₀).target :=
    contMDiffOn_extChartAt_symm x₀
  have h_maps : Set.MapsTo (extChartAt I x₀).symm (extChartAt I x₀).target
      ((chartAt H x₀).source) := by
    intro y hy
    simpa [extChartAt_source] using (extChartAt I x₀).map_target hy
  exact contMDiffOn_iff_contDiffOn.mp (h_triv.comp h_symm h_maps)



end Problems.Geometry.stokes_mextderiv
