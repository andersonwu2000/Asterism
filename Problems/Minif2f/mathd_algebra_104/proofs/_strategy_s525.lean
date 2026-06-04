import Mathlib
import Problems.Minif2f.mathd_algebra_104.Defs

namespace Problems.Minif2f.mathd_algebra_104

-- Direct: `linarith` solves the linear equation 125/8 = x/12 ⟹ x = 375/2.
theorem s525 : ∀ (x : ℝ) (h₀ : 125 / 8 = x / 12), x = 375 / 2  := by
  intro x h₀
  linarith

end Problems.Minif2f.mathd_algebra_104
