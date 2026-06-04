import Mathlib
import Problems.Minif2f.mathd_algebra_37.Defs

namespace Problems.Minif2f.mathd_algebra_37

-- Direct proof: h₀, h₁ pin x = 19, y = -12; then x² - y² = 217 by norm_num.
theorem s664 : ∀ (x y : ℝ) (h₀ : x + y = 7) (h₁ : 3 * x + y = 45), x ^ 2 - y ^ 2 = 217  := by
  intro x y h₀ h₁
  have hx : x = 19 := by linarith [h₀, h₁]
  have hy : y = -12 := by linarith [h₀, h₁]
  subst hx
  subst hy
  norm_num

end Problems.Minif2f.mathd_algebra_37
