import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- base_change_id: rpow base-change via sqrt_eq_rpow + rpow_mul closes the identity
-- LHS: 4^t = (2^2)^t = 2^(2t). RHS: (√2)^(4t+2) = (2^½)^(4t+2) = 2^(2t+1).
-- Equality 12·2^(2t) = 6·2^(2t+1) follows from rpow_add + ring.
theorem base_change_id :
    ∀ t : ℝ, 3 < t → 12 * (4:ℝ)^t = 6 * Real.sqrt 2 ^ (4*t + 2) := by
  intro t _ht
  have h4 : (4:ℝ)^t = (2:ℝ)^(2*t) := by
    have : (4:ℝ) = (2:ℝ)^(2:ℝ) := by norm_num
    rw [this, ← Real.rpow_mul (by norm_num : (0:ℝ) ≤ 2)]
  have hsqrt : Real.sqrt 2 ^ (4*t + 2) = (2:ℝ)^(2*t + 1) := by
    rw [Real.sqrt_eq_rpow, ← Real.rpow_mul (by norm_num : (0:ℝ) ≤ 2)]
    congr 1; ring
  rw [h4, hsqrt, Real.rpow_add (by norm_num : (0:ℝ) < 2), Real.rpow_one]
  ring

end Problems.Minif2f.amc12b_2021_p21
