import Mathlib
import Problems.Minif2f.mathd_algebra_510.Defs

namespace Problems.Minif2f.mathd_algebra_510

-- Direct: x² + y² = (x+y)² - 2xy = 169 - 48 = 121, then √121 = √(11²) = 11.
theorem s682 : ∀ (x y : ℝ) (h₀ : x + y = 13) (h₁ : x * y = 24),
    Real.sqrt (x ^ 2 + y ^ 2) = 11  := by
  intro x y h₀ h₁
  have hsq : x ^ 2 + y ^ 2 = 121 := by nlinarith [h₀, h₁, sq_nonneg (x + y)]
  rw [hsq, show (121 : ℝ) = 11 ^ 2 by norm_num]
  exact Real.sqrt_sq (by norm_num)

end Problems.Minif2f.mathd_algebra_510
