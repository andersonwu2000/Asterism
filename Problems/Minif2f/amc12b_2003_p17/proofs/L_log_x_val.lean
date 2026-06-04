import Mathlib
import Problems.Minif2f.amc12b_2003_p17.Defs

namespace Problems.Minif2f.amc12b_2003_p17

-- log_x_val: expand log via log_mul/log_pow, reduce to linear system a+3b=1,
-- 2a+b=1 in log-space, then linarith extracts a=2/5.
theorem log_x_val :
    ∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : Real.log (x * y ^ 3) = 1)
      (h₂ : Real.log (x ^ 2 * y) = 1), Real.log x = 2/5 := by
  intro x y ⟨hx, hy⟩ h₁ h₂
  have hx' : x ≠ 0 := hx.ne'
  have hy' : y ≠ 0 := hy.ne'
  rw [Real.log_mul hx' (pow_ne_zero 3 hy'), Real.log_pow] at h₁
  rw [Real.log_mul (pow_ne_zero 2 hx') hy', Real.log_pow] at h₂
  push_cast at h₁ h₂
  linarith

end Problems.Minif2f.amc12b_2003_p17
