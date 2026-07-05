-- Leaf-bypass: unfold `ofSmoothForm` to `integralAgainstBilinCLM B μ w`, then
-- `integralAgainstBilinCLM_eq_integral hw` rewrites the CLM application at the
-- test form `φ` to `∫ x, B (φ x) (w x) ∂μ`, discharging its `LocallyIntegrableOn`
-- side condition with `hw`. No decomposition needed.
import Mathlib
import Problems.Geometry.currents_smooth_form.Defs
import Problems.Geometry.currents_smooth_form.proofs._strategy_s17780

namespace Problems.Geometry.currents_smooth_form

def main := @Problems.Geometry.currents_smooth_form.s17780

end Problems.Geometry.currents_smooth_form
