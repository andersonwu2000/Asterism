-- Transport identity = pullback commutes with extDerivWithin, along the chart
-- transition f := extChartAt I x ∘ (extChartAt I x₀).symm at y₀ := extChartAt I x₀ x.
-- (B) h_fcc: formCoordChange unfolds to precomposition with fderivWithin ℝ f (range I) y₀
--     (formCoordChange def + tangentBundleCore_coordChange_achart) — inline simp.
-- (D) h_loc (sub-goal ext_deriv_locality_pullback): extDerivWithin of formInCoord I φ x₀
--     equals extDerivWithin of the pullback form (locality via sibling form_in_coord_pullback
--     + EventuallyEq.extDerivWithin_eq).
-- (C) h_pull: extDerivWithin_pullback moves extDerivWithin through the pullback; side
--     conditions: h_f transition smoothness (contDiffWithinAt_ext_coord_change, inline),
--     h_ω differentiability of formInCoord (sub-goal form_in_coord_differentiable_within_range),
--     uniqueDiffOn/closure-interior/MapsTo for range I — inline.
-- Chain: rw [h_fcc, h_loc, h_pull, hfy₀] closes the goal.
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11693

namespace Problems.Geometry.stokes_mextderiv

def ext_deriv_coord_change_transport := @Problems.Geometry.stokes_mextderiv.s11693

end Problems.Geometry.stokes_mextderiv
