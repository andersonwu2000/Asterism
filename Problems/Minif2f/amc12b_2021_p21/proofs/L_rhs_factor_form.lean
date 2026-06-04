import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- rhs_factor_form: rpow/log identity using log_sqrt and rpow_add to factor RHS
theorem rhs_factor_form : ∀ t : ℝ,
    Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
        ((2 : ℝ) ^ t) * Real.log 2 =
      (Real.log 2)^2 / 2 * Real.sqrt 2 ^ ((2 : ℝ) ^ t + 2 * t) := by
  intro t
  have h_log : Real.log (Real.sqrt 2) = Real.log 2 / 2 :=
    Real.log_sqrt (by norm_num)
  have h_2t : (2:ℝ)^t = Real.sqrt 2 ^ (2 * t) := by
    rw [Real.sqrt_eq_rpow, ← Real.rpow_mul (by norm_num : (0:ℝ) ≤ 2)]
    congr 1; ring
  have h_add : Real.sqrt 2 ^ ((2:ℝ)^t + 2 * t) =
      Real.sqrt 2 ^ (2:ℝ)^t * Real.sqrt 2 ^ (2 * t) :=
    Real.rpow_add (Real.sqrt_pos.mpr (by norm_num : (0:ℝ) < 2)) ((2:ℝ)^t) (2 * t)
  rw [h_log, h_add, ← h_2t]
  ring

end Problems.Minif2f.amc12b_2021_p21
