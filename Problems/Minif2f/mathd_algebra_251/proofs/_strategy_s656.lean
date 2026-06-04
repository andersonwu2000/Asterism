import Mathlib
import Problems.Minif2f.mathd_algebra_251.Defs

namespace Problems.Minif2f.mathd_algebra_251

-- Direct: clear `1/x` and `7/x` by `field_simp` using `h₀`, then `linarith` on `3*x + 1 = 7`.
theorem s656 : ∀ (x : ℝ) (h₀ : x ≠ 0) (h₁ : 3 + 1 / x = 7 / x), x = 2  := by
  intro x h₀ h₁
  field_simp at h₁
  linarith

end Problems.Minif2f.mathd_algebra_251
