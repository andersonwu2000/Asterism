import Mathlib
import Problems.Geometry.stokes_dd_zero.Defs

open scoped Manifold Bundle ContDiff Topology
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.MExtDeriv

namespace Problems.Geometry.stokes_dd_zero

-- Direct proof from Library's mext_deriv_triv_read: unfold formInCoord at
-- p := (extChartAt I x₀).symm y, rewrite the trivialization read via
-- continuousLinearMapAt_apply_of_mem, apply mext_deriv_triv_read, and close
-- with (extChartAt I x₀).right_inv hy.

theorem s11696 {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ∀ y ∈ (extChartAt I x₀).target,
      formInCoord I (mextDeriv I φ) x₀ y
        = extDerivWithin (formInCoord I φ x₀) (Set.range I) y  := by
  intro y hy
  have hp_src : (extChartAt I x₀).symm y ∈ (extChartAt I x₀).source :=
    (extChartAt I x₀).map_target hy
  have hp : (extChartAt I x₀).symm y ∈ (chartAt H x₀).source := by
    simpa only [extChartAt_source] using hp_src
  have h_rinv : extChartAt I x₀ ((extChartAt I x₀).symm y) = y :=
    (extChartAt I x₀).right_inv hy
  have h_read := mext_deriv_triv_read I φ x₀ ((extChartAt I x₀).symm y) hp
  have h_lhs : formInCoord I (mextDeriv I φ) x₀ y
      = ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
          (formBundleCore (M := M) I (k + 1)).Fiber x₀)
          ⟨(extChartAt I x₀).symm y,
            mextDerivFun I φ ((extChartAt I x₀).symm y)⟩).2 := by
    simp only [formInCoord]
    rw [Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hp]
    rfl
  rw [h_lhs, h_read, h_rinv]

end Problems.Geometry.stokes_dd_zero

