import Mathlib
namespace Problems.Minif2f.aime_1987_p8

-- gt_96_of_upper_bound: clear denominator via div_lt_div_iff₀, then omega-style linarith
theorem gt_96_of_upper_bound : ∀ y : ℕ, (112 : ℝ) / (112 + y) < 7 / 13 → 96 < y := by
  intro y h
  have hy_pos : (0 : ℝ) < 112 + y := by positivity
  rw [div_lt_div_iff₀ hy_pos (by norm_num : (0:ℝ) < 13)] at h
  have : (112 : ℝ) * 13 < 7 * (112 + y) := h
  have : (1456 : ℝ) < 784 + 7 * y := by linarith
  have : (672 : ℝ) < 7 * y := by linarith
  have : (96 : ℝ) < y := by linarith
  exact_mod_cast this

end Problems.Minif2f.aime_1987_p8
