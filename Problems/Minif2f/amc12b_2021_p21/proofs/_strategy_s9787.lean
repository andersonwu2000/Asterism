import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_four_mul_le_two_pow
import Problems.Minif2f.amc12b_2021_p21.proofs.L_four_pow_eq_sqrt2_four_z

namespace Problems.Minif2f.amc12b_2021_p21

-- Identity (4:ℝ)^z = √2^(4z) reduces the goal to comparing exponents 4z and 2^z
-- under the increasing function √2^·. Sub-goal 1: the algebraic identity (valid for
-- any z, hz threaded for uniform signatures). Sub-goal 2: the exp-vs-poly bound
-- 4z ≤ 2^z on z > 4. Closer: rewrite by h_eq, then Real.rpow_le_rpow_of_exponent_le
-- using 1 ≤ √2 (discharged inline by nlinarith on (√2)^2 = 2) and h_lin.
theorem s9787 :
    ∀ z : ℝ, 4 < z → (4:ℝ) ^ z ≤ Real.sqrt 2 ^ ((2:ℝ) ^ z)  := by
  intro z hz
  have h_eq : (4:ℝ) ^ z = Real.sqrt 2 ^ (4 * z) := four_pow_eq_sqrt2_four_z z hz
  have h_lin : 4 * z ≤ (2:ℝ) ^ z := four_mul_le_two_pow z hz
  rw [h_eq]
  apply Real.rpow_le_rpow_of_exponent_le
  · nlinarith [Real.sq_sqrt (show (0:ℝ) ≤ 2 by norm_num), Real.sqrt_nonneg 2]
  · exact h_lin

end Problems.Minif2f.amc12b_2021_p21
