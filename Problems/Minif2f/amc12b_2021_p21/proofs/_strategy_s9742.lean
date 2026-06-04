import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_exponent_bound
import Problems.Minif2f.amc12b_2021_p21.proofs.L_poly_lt_dbl_exp

namespace Problems.Minif2f.amc12b_2021_p21

-- Sandwich: bound LHS by z^3 via exponent comparison (2^√2 < 3), then show z^3
-- is still beaten by the double-exponential RHS. Splits a polynomial-vs-
-- double-exp gap into a clean numeric exponent bound and the analytic content.
theorem s9742 :
    ∀ z : ℝ, 4 < z → z ^ (2 : ℝ) ^ Real.sqrt 2 < Real.sqrt 2 ^ (2 : ℝ) ^ z := by
  intro z hz
  have h_exp_bound := exponent_bound z hz
  have h_poly_lt := poly_lt_dbl_exp z hz
  exact lt_of_le_of_lt h_exp_bound h_poly_lt

end Problems.Minif2f.amc12b_2021_p21
