import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- quad_le_cube: 3*t^2 ≤ t^3 for t > 3, via t^2*(t-3) ≥ 0 closed by nlinarith
theorem quad_le_cube : ∀ t : ℝ, 3 < t → 3 * t ^ 2 ≤ t ^ 3 := by
  intro t ht
  nlinarith [sq_nonneg t, mul_pos (show (0:ℝ) < t by linarith) (show (0:ℝ) < t by linarith)]

end Problems.Minif2f.amc12b_2021_p21
