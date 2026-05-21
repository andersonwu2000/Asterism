-- Decompose locally-constant winding on `Metric.ball z r` (off image of γ) via:
-- (A) `parametric_winding_integral_continuous_on_ball` (Backward): the parametric
--     integral `w ↦ ∫₀¹ deriv γ t / (γ t - w)` is continuous on `Metric.ball z r`.
-- (B) `winding_const_on_ball_from_continuous_integral` (Backward): continuity of
--     that parametric integral on a preconnected open ball, combined with γ
--     avoiding the ball (so each value is `2πi · windingNumber γ w` by
--     `exists_winding_integer`), forces windingNumber γ to be constant on the
--     ball — discrete-image-on-connected-set principle.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10581

namespace Problems.residue_thm

def winding_const_on_open_ball_off_image := @Problems.residue_thm.s10581

end Problems.residue_thm
