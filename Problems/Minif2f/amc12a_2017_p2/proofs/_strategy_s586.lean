import Mathlib
import Problems.Minif2f.amc12a_2017_p2.Defs

namespace Problems.Minif2f.amc12a_2017_p2

-- Direct: clear denominators via field_simp (uses x≠0, y≠0), reducing
-- 1/x + 1/y = 4 to y + x = 4*(x*y); linarith closes against h₂.
theorem s586 : ∀ (x y : ℝ) (h₀ : x ≠ 0) (h₁ : y ≠ 0) (h₂ : x + y = 4 * (x * y)), 1 / x + 1 / y = 4  := by
  intro x y h₀ h₁ h₂
  field_simp
  linarith

end Problems.Minif2f.amc12a_2017_p2
