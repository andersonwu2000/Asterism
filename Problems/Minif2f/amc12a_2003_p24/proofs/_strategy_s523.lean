import Mathlib
import Problems.Minif2f.amc12a_2003_p24.Defs
import Problems.Minif2f.amc12a_2003_p24.proofs.L_logb_sum_le_zero
import Problems.Minif2f.amc12a_2003_p24.proofs.L_zero_in_set

namespace Problems.Minif2f.amc12a_2003_p24

-- Split `IsGreatest S 0` into membership witness + universal upper bound.
-- h_zero_in_set: take `a = b = 2` ⇒ each logb argument is 1, both terms 0.
-- h_logb_sum_le_zero: set `x = logb b a ≥ 1`; sum = `-(x-1)²/x ≤ 0`.
theorem s523 : IsGreatest { y : ℝ | ∃ a b : ℝ, 1 < b ∧ b ≤ a ∧ y = Real.logb a (a / b) + Real.logb b (b / a) } 0  := by
  have h_zero_in_set := zero_in_set
  have h_logb_sum_le_zero := logb_sum_le_zero
  refine ⟨h_zero_in_set, ?_⟩
  rintro y ⟨a, b, hb, hba, hy⟩
  rw [hy]
  exact h_logb_sum_le_zero a b hb hba

end Problems.Minif2f.amc12a_2003_p24
