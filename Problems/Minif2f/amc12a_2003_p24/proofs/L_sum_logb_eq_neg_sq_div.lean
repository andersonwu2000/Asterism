import Mathlib
import Problems.Minif2f.amc12a_2003_p24.Defs

namespace Problems.Minif2f.amc12a_2003_p24

-- sum_logb_eq_neg_sq_div: unfold logb via Real.log_div, then field_simp + ring closes the identity
-- logb a (a/b) = (log a - log b)/log a and logb b (b/a) = (log b - log a)/log b;
-- summing gives -(log a - log b)^2/(log a * log b) by algebra.
theorem sum_logb_eq_neg_sq_div : ∀ a b : ℝ, 1 < b → b ≤ a →
    Real.logb a (a / b) + Real.logb b (b / a) =
    -(Real.log a - Real.log b)^2 / (Real.log a * Real.log b) := by
  intro a b hb hab
  have ha1 : (1 : ℝ) < a := lt_of_lt_of_le hb hab
  have ha_pos : (0 : ℝ) < a := by linarith
  have hb_pos : (0 : ℝ) < b := by linarith
  have hlogb_pos : 0 < Real.log b := Real.log_pos hb
  have hloga_pos : 0 < Real.log a := Real.log_pos ha1
  have hlogb_ne : Real.log b ≠ 0 := ne_of_gt hlogb_pos
  have hloga_ne : Real.log a ≠ 0 := ne_of_gt hloga_pos
  simp only [Real.logb, Real.log_div ha_pos.ne' hb_pos.ne', Real.log_div hb_pos.ne' ha_pos.ne']
  field_simp
  ring

end Problems.Minif2f.amc12a_2003_p24
