import Mathlib
import Problems.Minif2f.amc12a_2009_p9.Defs

namespace Problems.Minif2f.amc12a_2009_p9

-- Direct: instantiate h₀ at x=-2 (giving f 1 = 2) and h₁ at x=1 (giving f 1 = a+b+c).
-- linarith combines them after norm_num clears the arithmetic on both sides.
theorem s576 : ∀ (a b c : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f (x + 3) = 3 * x ^ 2 + 7 * x + 4) (h₁ : ∀ x, f x = a * x ^ 2 + b * x + c), a + b + c = 2  := by
  intro a b c f h₀ h₁
  have h2 := h₀ (-2)
  have h3 := h₁ 1
  norm_num at h2 h3
  linarith

end Problems.Minif2f.amc12a_2009_p9
