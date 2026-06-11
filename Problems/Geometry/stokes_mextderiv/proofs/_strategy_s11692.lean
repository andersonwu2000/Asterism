import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_ext_deriv_coord_change_transport
import Problems.Geometry.stokes_mextderiv.proofs.L_triv_read_mext_deriv_eq_coord_change

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange

-- Split the trivialized read of mextDerivFun into bookkeeping + transport.
-- (1) triv_read_mext_deriv_eq_coord_change: unfold mextDerivFun (symmL at x's own
--     trivialization cancels by formCoordChange_self / coordChange_self, indexAt = achart),
--     so the x₀-trivialization read is formCoordChange (achart x) (achart x₀) x applied to
--     the model-space extDerivWithin at x's chart — pure definitional bundle bookkeeping.
-- (2) ext_deriv_coord_change_transport: the analytic heart — formCoordChange is
--     precomposition by the tangent transition derivative (tangentBundleCore_coordChange_achart),
--     so the identity is extDerivWithin_pullback applied to the chart transition, with
--     formInCoord I φ x rewritten as the pullback of formInCoord I φ x₀ via the open
--     sibling form_in_coord_pullback (locality: EventuallyEq.extDerivWithin_eq on range I).
-- Chain (1).trans (2) closes the goal.
theorem s11692
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ x : M)
    (hx : x ∈ (chartAt H x₀).source) :
    ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
        (formBundleCore (M := M) I (k + 1)).Fiber x₀) ⟨x, mextDerivFun I φ x⟩).2
      = extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)  := by
  have h_read := triv_read_mext_deriv_eq_coord_change I φ x₀ x
  have h_transport := ext_deriv_coord_change_transport I φ x₀ x hx
  exact h_read.trans h_transport

end Problems.Geometry.stokes_mextderiv

