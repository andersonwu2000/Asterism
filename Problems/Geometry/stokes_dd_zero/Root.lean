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
import Mathlib
import Problems.Geometry.stokes_dd_zero.Defs
import Problems.Geometry.stokes_dd_zero.proofs._strategy_s11695

namespace Problems.Geometry.stokes_dd_zero

def main := @Problems.Geometry.stokes_dd_zero.s11695

end Problems.Geometry.stokes_dd_zero
