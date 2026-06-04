import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs

namespace Problems.Minif2f.aime_1987_p8

-- lt_98_of_lower_bound: cross-multiply 8/15 < 112/(112+y) via div_lt_div_iff₀ to get y < 98
theorem lt_98_of_lower_bound : ∀ y : ℕ, (8 : ℝ) / 15 < (112 : ℝ) / (112 + y) → y < 98 := by
  intro y hy
  have hy_pos : (0 : ℝ) < 112 + y := by positivity
  rw [div_lt_div_iff₀ (by norm_num : (0 : ℝ) < 15) hy_pos] at hy
  have : (y : ℝ) < 98 := by linarith
  exact_mod_cast this

end Problems.Minif2f.aime_1987_p8
