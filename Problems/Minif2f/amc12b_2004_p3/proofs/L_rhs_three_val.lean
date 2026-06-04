import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs

namespace Problems.Minif2f.amc12b_2004_p3

-- rhs_three_val: decompose 1296 = 3^4 * 2^4, use padicValNat.mul + pow + self
-- mirrors rhs_two_val proof with p=3; 3∤2^4 closes the coprime factor
theorem rhs_three_val : padicValNat 3 1296 = 4 := by
  have h : (1296 : ℕ) = 3 ^ 4 * 2 ^ 4 := by norm_num
  rw [h, padicValNat.mul (by positivity) (by positivity),
      padicValNat.pow 4 (by norm_num : (3 : ℕ) ≠ 0), padicValNat.self (by norm_num),
      padicValNat.eq_zero_of_not_dvd (by norm_num : ¬ (3 : ℕ) ∣ 2 ^ 4)]

end Problems.Minif2f.amc12b_2004_p3
