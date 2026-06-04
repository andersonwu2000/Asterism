import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_a_lt
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_b_lt
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_c_lt
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_d_lt

namespace Problems.Minif2f.imo_1974_p5

-- Bound each fraction below by the same numerator over the full sum a+b+c+d.
-- Since dropping one positive term from the denominator strictly increases the
-- fraction, each frac_X_lt sub-goal gives a strict inequality; summing the
-- four and using (a+b+c+d)/(a+b+c+d) = 1 yields 1 < LHS.
theorem s9488 : ∀ (a b c d : ℝ), 0 < a → 0 < b → 0 < c → 0 < d →
    1 < a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)  := by
  intro a b c d ha hb hc hd
  have h_frac_a := frac_a_lt a b c d ha hb hc hd
  have h_frac_b := frac_b_lt a b c d ha hb hc hd
  have h_frac_c := frac_c_lt a b c d ha hb hc hd
  have h_frac_d := frac_d_lt a b c d ha hb hc hd
  have hS : a + b + c + d ≠ 0 := by positivity
  have h_sum_eq_one :
      a / (a + b + c + d) + b / (a + b + c + d)
        + c / (a + b + c + d) + d / (a + b + c + d) = 1 := by
    field_simp
  linarith

end Problems.Minif2f.imo_1974_p5
