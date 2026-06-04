import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_strict_lt_on_one_sqrt2

namespace Problems.Minif2f.amc12b_2021_p21

-- Refine ≠ to strict <: on [1, √2), LHS = y^(2^√2) < √2^(2^y) = RHS.
-- The strict inequality is the hard analytic content (parallels
-- `strict_gt_on_sqrt2_three` for the (√2, 3] side); `ne_of_lt` closes.
theorem s9772 : ∀ y : ℝ, 0 < y → y < Real.sqrt 2 → 1 ≤ y →
    y ^ (2 : ℝ) ^ Real.sqrt 2 ≠ Real.sqrt 2 ^ (2 : ℝ) ^ y  := by
  intro y hy_pos hy_lt hy_ge
  have h_lt : y ^ (2 : ℝ) ^ Real.sqrt 2 < Real.sqrt 2 ^ (2 : ℝ) ^ y :=
    strict_lt_on_one_sqrt2 y hy_pos hy_lt hy_ge
  exact ne_of_lt h_lt

end Problems.Minif2f.amc12b_2021_p21
