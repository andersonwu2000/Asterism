import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- four_pow_eq_sqrt2_four_z: rewrite √2 = 2^(1/2) then collapse via rpow_mul twice
theorem four_pow_eq_sqrt2_four_z :
    ∀ z : ℝ, 4 < z → (4:ℝ) ^ z = Real.sqrt 2 ^ (4 * z) := by
  intro z _hz
  rw [Real.sqrt_eq_rpow, ← Real.rpow_mul (by norm_num : (0:ℝ) ≤ 2),
      show (4:ℝ) = (2:ℝ) ^ (2:ℝ) from by norm_num,
      ← Real.rpow_mul (by norm_num : (0:ℝ) ≤ 2)]
  ring_nf

end Problems.Minif2f.amc12b_2021_p21
