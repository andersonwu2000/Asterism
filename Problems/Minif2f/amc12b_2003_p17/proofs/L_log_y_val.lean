import Mathlib
import Problems.Minif2f.amc12b_2003_p17.Defs

namespace Problems.Minif2f.amc12b_2003_p17

-- log_y_val: expand log(x·y³)=1 and log(x²·y)=1 into a 2×2 linear system in log x, log y,
-- then linarith extracts log y = 1/5 (eliminating log x via linear combination).
theorem log_y_val :
    ∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : Real.log (x * y ^ 3) = 1)
      (h₂ : Real.log (x ^ 2 * y) = 1), Real.log y = 1/5 := by
  intro x y h₀ h₁ h₂
  obtain ⟨hx, hy⟩ := h₀
  have hne_x : x ≠ 0 := ne_of_gt hx
  have hne_y : y ≠ 0 := ne_of_gt hy
  have hne_y3 : y ^ 3 ≠ 0 := pow_ne_zero 3 hne_y
  have hne_x2 : x ^ 2 ≠ 0 := pow_ne_zero 2 hne_x
  rw [Real.log_mul hne_x hne_y3, Real.log_pow] at h₁
  rw [Real.log_mul hne_x2 hne_y, Real.log_pow] at h₂
  push_cast at h₁ h₂
  linarith

end Problems.Minif2f.amc12b_2003_p17
