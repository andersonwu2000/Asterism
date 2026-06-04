import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_cube_lt_log_sq_dbl_exp
import Problems.Minif2f.amc12b_2021_p21.proofs.L_rhs_factor_form

namespace Problems.Minif2f.amc12b_2021_p21

-- Factor RHS into `(log 2)^2 / 2 * sqrt(2)^(2^t + 2t)` via the identities
-- `log(sqrt 2) = (log 2)/2` and `(2:ℝ)^t = sqrt(2)^(2t)`, then compare cube to
-- the rewritten lower bound. Sub-goal 1 is a pure rpow/log identity (universal
-- in t); sub-goal 2 carries the analytic cube-vs-double-exp content on `t > 3`.
theorem s9824 : ∀ t : ℝ, 3 < t →
    t ^ 3 <
      Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
        ((2 : ℝ) ^ t) * Real.log 2  := by
  intro t ht
  have h_factor := rhs_factor_form t
  have h_main := cube_lt_log_sq_dbl_exp t ht
  rw [h_factor]
  exact h_main

end Problems.Minif2f.amc12b_2021_p21
