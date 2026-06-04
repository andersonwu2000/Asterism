import Mathlib
import Problems.Minif2f.amc12a_2003_p24.Defs

namespace Problems.Minif2f.amc12a_2003_p24

-- zero_in_set: witness a=b=2 gives logb 2 1 + logb 2 1 = 0
theorem zero_in_set :
    ∃ a b : ℝ, 1 < b ∧ b ≤ a ∧ (0 : ℝ) = Real.logb a (a / b) + Real.logb b (b / a) := by
  exact ⟨2, 2, by norm_num, le_refl _, by simp [Real.logb, Real.log_one]⟩

end Problems.Minif2f.amc12a_2003_p24
