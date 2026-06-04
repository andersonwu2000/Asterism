import Mathlib
import Problems.Minif2f.mathd_algebra_455.Defs

namespace Problems.Minif2f.mathd_algebra_455

-- Direct: hypothesis is 16·x = 48 (linear), so linarith closes.
theorem s674 : ∀ (x : ℝ) (h₀ : 2 * (2 * (2 * (2 * x))) = 48), x = 3  := by
  intro x h₀
  linarith

end Problems.Minif2f.mathd_algebra_455
