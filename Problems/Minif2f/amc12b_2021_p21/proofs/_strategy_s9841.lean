import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_base_change_id
import Problems.Minif2f.amc12b_2021_p21.proofs.L_exp_lower_bound

namespace Problems.Minif2f.amc12b_2021_p21

-- Sandwich via `6 * sqrt 2 ^ (4*t + 2)`: rewrite LHS using `sqrt 2 ^ 2 = 2`
-- and `(sqrt 2)^4 = 4`, then use monotonicity of `sqrt 2 ^ ·` (since `1 ≤ sqrt 2`)
-- with the exponent bound `4*t + 2 ≤ 2^t + 2*t` (the actual content; tight at t=3).
theorem s9841 :
    ∀ t : ℝ, 3 < t → 12 * (4:ℝ)^t ≤ 6 * Real.sqrt 2 ^ ((2:ℝ)^t + 2*t)  := by
  intro t ht
  have h_base : 12 * (4:ℝ)^t = 6 * Real.sqrt 2 ^ (4*t + 2) :=
    base_change_id t ht
  have h_exp : 4*t + 2 ≤ (2:ℝ)^t + 2*t :=
    exp_lower_bound t ht
  rw [h_base]
  apply mul_le_mul_of_nonneg_left _ (by norm_num : (0:ℝ) ≤ 6)
  apply Real.rpow_le_rpow_of_exponent_le
  · rw [show (1:ℝ) = Real.sqrt 1 from Real.sqrt_one.symm]
    exact Real.sqrt_le_sqrt (by norm_num)
  · exact h_exp

end Problems.Minif2f.amc12b_2021_p21
