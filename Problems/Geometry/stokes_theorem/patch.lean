import Mathlib
import Problems.Geometry.stokes_theorem.Defs
import Problems.Geometry.stokes_theorem.proofs.L_smul_form
import Problems.Geometry.stokes_theorem.proofs.L_chart_stokes_core

open Bundle
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.ManifoldBdry.BdryIsManifold

namespace Problems.Geometry.stokes_theorem

open scoped Manifold Bundle ContDiff
open Bundle MeasureTheory
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBoundary.CompactBdry

-- Repaired single-chart Stokes leg: localize via the TSUPPORT-instantiated chart collapse,
-- then close with the chart-level analytic core.
-- (1) `lhs_integral_localized_tsupp`: `DiffForm.integral (d(g•φ))` collapses to the signed
--     coordinate integral over chart-`c`'s target — instantiated at this very form (NOT the
--     poisoned generic `integral_localized_single_chart`), so its subtree can use the proved
--     tsupport-level `localcoeff_integrableon_tsupp` (htψ from `hsupp`).
-- (2) `chart_stokes_core` (open sibling, cited directly): the remaining FTC heart equates that
--     signed coordinate integral to `∫_∂M ι*(g•φ)`.
theorem s11832 {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (g : M → ℝ)
    (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c : M)
    (hsupp : tsupport g ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c).source) :
    DiffForm.integral (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) =
      DiffForm.integral (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ))  := by
  have h_loc := lhs_integral_localized_tsupp φ g hg c hsupp
  rw [h_loc]
  exact chart_stokes_core φ g hg c hsupp

end Problems.Geometry.stokes_theorem
