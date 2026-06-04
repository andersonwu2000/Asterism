import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs

namespace Problems.Minif2f.amc12b_2004_p3

-- rhs_two_val: decompose 1296 = 2^4 * 3^4, use padicValNat.mul + pow + self
theorem rhs_two_val : padicValNat 2 1296 = 4 := by
  have h : (1296 : ℕ) = 2^4 * 3^4 := by norm_num
  rw [h, padicValNat.mul (by positivity) (by positivity),
      padicValNat.pow 4 (by norm_num : 2 ≠ 0), padicValNat.self (by norm_num),
      padicValNat.eq_zero_of_not_dvd (by norm_num : ¬ 2 ∣ 3^4)]

end Problems.Minif2f.amc12b_2004_p3
