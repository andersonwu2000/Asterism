import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integer_continuous_const_on_preconnected_ball
import Problems.residue_thm.proofs.L_integral_eq_two_pi_i_winding_on_ball

namespace Problems.residue_thm

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
theorem s10594
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, r < dist (γ t) z)
    (h_cts : ContinuousOn (fun w => ∫ t in (0:ℝ)..1, deriv γ t / (γ t - w))
              (Metric.ball z r)) :
    ∀ w ∈ Metric.ball z r, Complex.windingNumber γ w = Complex.windingNumber γ z  := by
  have h_eq := integral_eq_two_pi_i_winding_on_ball hγ hclosed hr h_avoid
  exact integer_continuous_const_on_preconnected_ball hr h_cts h_eq

end Problems.residue_thm
