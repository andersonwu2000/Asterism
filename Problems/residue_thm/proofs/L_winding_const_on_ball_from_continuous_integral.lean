-- Reduce locally-constant winding on `Metric.ball z r` (off image of γ) to:
-- (A) `integral_eq_two_pi_i_winding_on_ball` (Builder, wrapper for
--     `winding_integral_formula`): at every w in the ball, the parametric
--     integral equals `2πi · windingNumber γ w`.  γ avoids each interior w
--     by triangle inequality on `h_avoid` + `w ∈ ball`.
-- (B) `integer_continuous_const_on_preconnected_ball` (Backward): abstract
--     discrete-image-on-connected-set principle — a continuous `ℂ`-valued
--     function on the open ball whose values lie in `2πi·ℤ` forces the
--     integer label to be constant.  Combines with `h_cts` and the identity
--     from (A) to conclude `windingNumber γ w = windingNumber γ z`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10594

namespace Problems.residue_thm

def winding_const_on_ball_from_continuous_integral := @Problems.residue_thm.s10594

end Problems.residue_thm
