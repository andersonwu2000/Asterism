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
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11692

namespace Problems.Geometry.stokes_mextderiv

def mext_deriv_triv_read := @Problems.Geometry.stokes_mextderiv.s11692

end Problems.Geometry.stokes_mextderiv
