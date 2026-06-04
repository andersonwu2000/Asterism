import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_cube_lt_twelve_four_pow
import Problems.Minif2f.amc12b_2021_p21.proofs.L_twelve_four_pow_le_six_dbl_exp

namespace Problems.Minif2f.amc12b_2021_p21

-- Sandwich via 12 * 4^t: 25t³ < 12·4^t (poly-vs-exp, tight at t=3 with margin 93)
-- and 12·4^t ≤ 6·√2^(2^t+2t) (factor 2 absorbed via √2² and 2t+2 ≤ 2^t exponent bound).
theorem s9837 :
    ∀ t : ℝ, 3 < t →
      25 * t^3 < 6 * Real.sqrt 2 ^ ((2:ℝ)^t + 2*t)  := by
  intro t ht
  have h_cube_lt_twelve_four_pow := cube_lt_twelve_four_pow t ht
  have h_twelve_four_pow_le_six_dbl_exp := twelve_four_pow_le_six_dbl_exp t ht
  exact lt_of_lt_of_le h_cube_lt_twelve_four_pow h_twelve_four_pow_le_six_dbl_exp

end Problems.Minif2f.amc12b_2021_p21
