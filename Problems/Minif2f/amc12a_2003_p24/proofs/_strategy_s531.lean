import Mathlib
import Problems.Minif2f.amc12a_2003_p24.Defs
import Problems.Minif2f.amc12a_2003_p24.proofs.L_neg_sq_div_log_prod_nonpos
import Problems.Minif2f.amc12a_2003_p24.proofs.L_sum_logb_eq_neg_sq_div

namespace Problems.Minif2f.amc12a_2003_p24

-- Rewrite the sum via the algebraic identity
--   logb a (a/b) + logb b (b/a) = -(log a - log b)² / (log a * log b),
-- then bound by 0: numerator is the negation of a square, denominator
-- positive since a ≥ b > 1 ⇒ log a, log b > 0. Each sub-goal is a
-- single-shot leaf (field_simp / ring for identity; positivity for sign).
theorem s531 :
    ∀ a b : ℝ, 1 < b → b ≤ a → Real.logb a (a / b) + Real.logb b (b / a) ≤ 0  := by
  intro a b hb hba
  have h_eq := sum_logb_eq_neg_sq_div a b hb hba
  have h_le := neg_sq_div_log_prod_nonpos a b hb hba
  rw [h_eq]; exact h_le

end Problems.Minif2f.amc12a_2003_p24
