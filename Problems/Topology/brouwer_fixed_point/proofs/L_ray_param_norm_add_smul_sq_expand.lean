import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- ray_param_norm_add_smul_sq_expand: norm_add_sq_real + inner_smul_right + sq_abs closes
theorem ray_param_norm_add_smul_sq_expand
    {n : ℕ}
    (x : EuclideanSpace ℝ (Fin n))
    (w : EuclideanSpace ℝ (Fin n))
    (s : ℝ) :
    ‖x + s • w‖^2 = ‖x‖^2 + 2 * s * (@inner ℝ _ _ x w) + s^2 * ‖w‖^2 := by
  rw [norm_add_sq_real, inner_smul_right, norm_smul]
  ring_nf
  rw [Real.norm_eq_abs, sq_abs]

end Problems.Topology.brouwer_fixed_point
