-- Both sides reduce to formCoordChange reads via the proved brick
-- form_in_coord_eq_coord_change (at x via right_inv hy, at x₀ via hy'); the residue is
-- the tangentBundleCore cocycle coordChange_comp with the (x→x₀) leg rewritten to the
-- fderivWithin transition by tangentBundleCore_coordChange_achart.
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11690

namespace Problems.Geometry.stokes_mextderiv

def form_in_coord_pullback := @Problems.Geometry.stokes_mextderiv.s11690

end Problems.Geometry.stokes_mextderiv
