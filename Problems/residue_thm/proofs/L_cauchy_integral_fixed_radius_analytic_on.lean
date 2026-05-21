-- Direct application of Mathlib's `hasFPowerSeriesOn_cauchy_integral`.
-- Lift `r` to `ℝ≥0`, establish `CircleIntegrable f z₀ r` from analyticity on
-- the punctured ball (sphere of radius `r` lies in `ball z₀ R \ {z₀}`), then
-- the lemma yields `HasFPowerSeriesOnBall` in smul-form on `Metric.eball z₀ ↑r`;
-- `analyticOnNhd.analyticOn` lands `AnalyticOn`, and `AnalyticOn.congr` rewrites
-- the smul-kernel to the goal's `f w / (w - z)` form (pointwise `smul_eq_mul`
-- + `mul_comm` + `div_eq_mul_inv`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10424

namespace Problems.residue_thm

def cauchy_integral_fixed_radius_analytic_on := @Problems.residue_thm.s10424

end Problems.residue_thm
