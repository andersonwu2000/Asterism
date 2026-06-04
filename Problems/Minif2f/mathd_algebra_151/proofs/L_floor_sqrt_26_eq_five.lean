import Mathlib
import Problems.Minif2f.mathd_algebra_151.Defs

namespace Problems.Minif2f.mathd_algebra_151

-- floor_sqrt_26_eq_five: bound sqrt(26) in [5,6) via sqrt monotonicity, close with Int.floor_eq_iff
theorem floor_sqrt_26_eq_five : Int.floor (Real.sqrt 26) = 5 := by
  have h1 : (5 : ℝ) ≤ Real.sqrt 26 := by
    rw [show (5 : ℝ) = Real.sqrt 25 by
      rw [show (25 : ℝ) = 5^2 by norm_num]
      rw [Real.sqrt_sq (by norm_num : (5:ℝ) ≥ 0)]]
    apply Real.sqrt_le_sqrt
    norm_num
  have h2 : Real.sqrt 26 < 6 := by
    rw [show (6 : ℝ) = Real.sqrt 36 by
      rw [show (36 : ℝ) = 6^2 by norm_num]
      rw [Real.sqrt_sq (by norm_num : (6:ℝ) ≥ 0)]]
    apply Real.sqrt_lt_sqrt (by norm_num)
    norm_num
  rw [Int.floor_eq_iff]
  constructor
  · exact_mod_cast h1
  · push_cast
    linarith

end Problems.Minif2f.mathd_algebra_151
