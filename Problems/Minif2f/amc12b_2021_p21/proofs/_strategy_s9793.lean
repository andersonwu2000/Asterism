import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_lhs_poly_bound
import Problems.Minif2f.amc12b_2021_p21.proofs.L_poly_lt_log_dbl_exp

namespace Problems.Minif2f.amc12b_2021_p21

-- Split the strict negativity into two transitivity steps via the polynomial bridge `3 * t^2`:
-- h_lhs_le — the rpow-polynomial LHS `2^√2 * t^(2^√2-1)` is bounded by `3 * t^2`
--   (uses 2^√2 ≤ 3 and exponent monotonicity since 2^√2 - 1 ≤ 2 and t > 1).
-- h_poly_lt — `3 * t^2 < √2^(2^t) * log√2 * 2^t * log 2` is the doubly-exponential
--   dominance of the second term over a quadratic polynomial for t > 3.
-- Combine via `linarith`: A ≤ B and B < C give A - C < 0.
theorem s9793 :
    ∀ t : ℝ, 3 < t →
      (2 : ℝ) ^ Real.sqrt 2 * t ^ ((2 : ℝ) ^ Real.sqrt 2 - 1)
        - Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
          ((2 : ℝ) ^ t) * Real.log 2 < 0  := by
  intro t ht
  have h_lhs_le := lhs_poly_bound t ht
  have h_poly_lt := poly_lt_log_dbl_exp t ht
  linarith

end Problems.Minif2f.amc12b_2021_p21
