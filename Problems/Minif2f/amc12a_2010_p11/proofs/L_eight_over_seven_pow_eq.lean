import Mathlib
import Problems.Minif2f.amc12a_2010_p11.Defs

namespace Problems.Minif2f.amc12a_2010_p11

-- eight_over_seven_pow_eq: split 7^(x+7) via rpow_add, then div_rpow closes (8/7)^x = 7^7
theorem eight_over_seven_pow_eq :
    ∀ (x : ℝ), (7 : ℝ) ^ (x + 7) = 8 ^ x → (8 / 7 : ℝ) ^ x = 7 ^ 7 := by
  intro x h
  have h7pos : (0 : ℝ) < 7 := by norm_num
  have h8pos : (0 : ℝ) < 8 := by norm_num
  have h7xpos : (0 : ℝ) < (7 : ℝ) ^ x := Real.rpow_pos_of_pos h7pos x
  rw [Real.rpow_add h7pos] at h
  rw [Real.div_rpow (le_of_lt h8pos) (le_of_lt h7pos)]
  rw [← Real.rpow_natCast 7 7]
  rw [← h]
  field_simp
  ring

end Problems.Minif2f.amc12a_2010_p11
