import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_parametric_winding_integral_continuous_on_ball
import Problems.residue_thm.proofs.L_winding_const_on_ball_from_continuous_integral

namespace Problems.residue_thm

-- Decompose locally-constant winding on `Metric.ball z r` (off image of γ) via:
-- (A) `parametric_winding_integral_continuous_on_ball` (Backward): the parametric
--     integral `w ↦ ∫₀¹ deriv γ t / (γ t - w)` is continuous on `Metric.ball z r`.
-- (B) `winding_const_on_ball_from_continuous_integral` (Backward): continuity of
--     that parametric integral on a preconnected open ball, combined with γ
--     avoiding the ball (so each value is `2πi · windingNumber γ w` by
--     `exists_winding_integer`), forces windingNumber γ to be constant on the
--     ball — discrete-image-on-connected-set principle.
theorem s10581
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, r < dist (γ t) z) :
    ∀ w ∈ Metric.ball z r, Complex.windingNumber γ w = Complex.windingNumber γ z  := by
  have h_cts := parametric_winding_integral_continuous_on_ball hγ hr h_avoid
  exact winding_const_on_ball_from_continuous_integral hγ hclosed hr h_avoid h_cts

end Problems.residue_thm
