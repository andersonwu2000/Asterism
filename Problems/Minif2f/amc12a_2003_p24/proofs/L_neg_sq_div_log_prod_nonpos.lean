import Mathlib
import Problems.Minif2f.amc12a_2003_p24.Defs

namespace Problems.Minif2f.amc12a_2003_p24

-- neg_sq_div_log_prod_nonpos: nonneg denominator (log a * log b > 0) makes neg-square quotient ≤ 0
theorem neg_sq_div_log_prod_nonpos : ∀ a b : ℝ, 1 < b → b ≤ a →
    -(Real.log a - Real.log b)^2 / (Real.log a * Real.log b) ≤ 0 := by
  intro a b hb hab
  have hlogb : 0 < Real.log b := Real.log_pos hb
  have hloga : 0 < Real.log a := Real.log_pos (lt_of_lt_of_le hb hab)
  have hprod : 0 < Real.log a * Real.log b := mul_pos hloga hlogb
  apply div_nonpos_of_nonpos_of_nonneg
  · linarith [sq_nonneg (Real.log a - Real.log b)]
  · linarith

end Problems.Minif2f.amc12a_2003_p24
