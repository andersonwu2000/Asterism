import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_four_pow_le_sqrt2_dbl_exp
import Problems.Minif2f.amc12b_2021_p21.proofs.L_poly_lt_four_pow

namespace Problems.Minif2f.amc12b_2021_p21

-- Sandwich via 4^z: z^3 < 4^z (polynomial-vs-exponential at z>4) and
-- 4^z ≤ √2^(2^z) (since √2^(4z) = 4^z and 4z ≤ 2^z for z ≥ 4).
-- Splits the polynomial-vs-double-exponential gap into a polynomial-vs-
-- single-exponential bound and a clean exponent comparison.
theorem s9770 : ∀ z : ℝ, 4 < z → z ^ (3:ℝ) < Real.sqrt 2 ^ ((2:ℝ) ^ z)  := by
  intro z hz
  have h1 := poly_lt_four_pow z hz
  have h2 := four_pow_le_sqrt2_dbl_exp z hz
  exact lt_of_lt_of_le h1 h2

end Problems.Minif2f.amc12b_2021_p21
