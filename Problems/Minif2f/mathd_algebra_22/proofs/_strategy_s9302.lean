import Mathlib
import Problems.Minif2f.mathd_algebra_22.Defs

namespace Problems.Minif2f.mathd_algebra_22

-- Direct proof. Rewrite 5^4 = (5^2)^2, then `Real.logb_pow` pulls the
-- exponent 2 out as a factor, and `Real.logb_self_eq_one` reduces the
-- remaining `logb (5^2) (5^2)` to 1; `norm_num` closes the arithmetic.
theorem s9302 : Real.logb (5 ^ 2) (5 ^ 4) = 2  := by
  have h : ((5:ℝ)^4) = ((5:ℝ)^2)^2 := by ring
  rw [h, Real.logb_pow, Real.logb_self_eq_one] <;> norm_num

end Problems.Minif2f.mathd_algebra_22
