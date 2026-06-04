import Mathlib
import Problems.Minif2f.amc12b_2003_p17.Defs
import Problems.Minif2f.amc12b_2003_p17.proofs.L_log_x_val
import Problems.Minif2f.amc12b_2003_p17.proofs.L_log_y_val

namespace Problems.Minif2f.amc12b_2003_p17

-- Solve the linear system in log-space for log x and log y, then
-- expand log (x*y) via Real.log_mul and substitute. Each sub-goal
-- pins down a single variable's log value (strictly smaller than
-- both equations + the product expansion combined).
theorem s596 : ∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : Real.log (x * y ^ 3) = 1)
    (h₂ : Real.log (x ^ 2 * y) = 1), Real.log (x * y) = 3 / 5 := by
  intro x y h₀ h₁ h₂
  have hx := h₀.1
  have hy := h₀.2
  have h_log_x_val := log_x_val x y h₀ h₁ h₂
  have h_log_y_val := log_y_val x y h₀ h₁ h₂
  rw [Real.log_mul hx.ne' hy.ne', h_log_x_val, h_log_y_val]
  norm_num

end Problems.Minif2f.amc12b_2003_p17
