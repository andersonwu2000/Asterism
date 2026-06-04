import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs

namespace Problems.Minif2f.amc12b_2004_p3

-- lhs_three_val: padicValNat.mul + padicValNat.pow/self split; 3∤2^x via Prime.dvd_of_dvd_pow
theorem lhs_three_val (x y : ℕ) : padicValNat 3 (2 ^ x * 3 ^ y) = y := by
  rw [padicValNat.mul (pow_ne_zero x (by norm_num)) (pow_ne_zero y (by norm_num)),
      padicValNat.pow y (by norm_num : (3:ℕ) ≠ 0), padicValNat.self (by norm_num : 1 < 3)]
  simp only [mul_one, Nat.add_eq_right, padicValNat.eq_zero_iff, OfNat.ofNat_ne_one,
             Nat.pow_eq_zero, OfNat.ofNat_ne_zero, ne_eq, false_and, false_or]
  exact fun h => absurd (Nat.Prime.dvd_of_dvd_pow (by norm_num : Nat.Prime 3) h) (by norm_num)

end Problems.Minif2f.amc12b_2004_p3
