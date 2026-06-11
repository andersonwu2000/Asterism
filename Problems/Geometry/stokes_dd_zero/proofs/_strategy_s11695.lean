import Mathlib
import Problems.Geometry.stokes_dd_zero.Defs
import Problems.Geometry.stokes_dd_zero.proofs.L_ext_deriv_within_congr_chart_target
import Problems.Geometry.stokes_dd_zero.proofs.L_ext_deriv_within_dd_zero_at_base
import Problems.Geometry.stokes_dd_zero.proofs.L_form_in_coord_mext_deriv_eq

open scoped Manifold Bundle ContDiff

namespace Problems.Geometry.stokes_dd_zero

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.MExtDeriv
open scoped Manifold Bundle ContDiff Topology

-- d∘d = 0 by pointwise reduction, a chart-independence bridge, and model-space dd = 0.
-- ContMDiffSection.ext reduces the section equality to mextDerivFun I (mextDeriv I φ) x₀ = 0;
-- unfolding mextDerivFun exposes symmL applied to extDerivWithin of the integrand
-- formInCoord I (mextDeriv I φ) x₀. The bridge (form_in_coord_mext_deriv_eq, from Library's
-- mext_deriv_triv_read) identifies that integrand on (extChartAt I x₀).target with
-- extDerivWithin (formInCoord I φ x₀) (Set.range I); the congr lemma
-- (ext_deriv_within_congr_chart_target) transports this local identification through the outer
-- extDerivWithin; the model-space lemma (ext_deriv_within_dd_zero_at_base, mathlib's
-- extDerivWithin_extDerivWithin_apply + form_in_coord_smooth) kills the double derivative,
-- and ContinuousLinearMap.map_zero finishes.
theorem s11695 : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k),
    mextDeriv I (mextDeriv I φ) = 0  := by
  intro E _ _ H _ I M _ _ _ k φ
  refine ContMDiffSection.ext fun x₀ => ?_
  have h_bridge := form_in_coord_mext_deriv_eq I φ x₀
  change mextDerivFun I (mextDeriv I φ) x₀ = 0
  rw [mextDerivFun, ext_deriv_within_congr_chart_target I x₀ _ _ h_bridge,
    ext_deriv_within_dd_zero_at_base I φ x₀]
  exact ContinuousLinearMap.map_zero _

end Problems.Geometry.stokes_dd_zero
