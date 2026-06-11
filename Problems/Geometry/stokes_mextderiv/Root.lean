-- Fix x₀; reduce to the trivialized read via contMDiffAt_section_iff at x₀'s trivialization.
-- Near x₀ the read equals the fixed-chart function x ↦ extDerivWithin (formInCoord I φ x₀)
-- (range I) (extChartAt I x₀ x) [sub-goal mext_deriv_triv_read, fed by the chart-transition
-- pullback identity form_in_coord_pullback]; that fixed-chart function is ContMDiffAt
-- [sub-goal ext_deriv_fixed_chart_contmdiff_at, from form_in_coord_smooth +
-- ext_deriv_within_smooth]. Glue by ContMDiffAt.congr_of_eventuallyEq on chart source.
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11688

namespace Problems.Geometry.stokes_mextderiv

def main := @Problems.Geometry.stokes_mextderiv.s11688

end Problems.Geometry.stokes_mextderiv
