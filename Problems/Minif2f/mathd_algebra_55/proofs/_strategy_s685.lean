import Mathlib
import Problems.Minif2f.mathd_algebra_55.Defs

namespace Problems.Minif2f.mathd_algebra_55

-- Direct closure: substitute q, p with their literal sums; norm_num evaluates 8/12 = 2/3.
theorem s685 : ∀ (q p : ℝ) (h₀ : q = 2 - 4 + 6 - 8 + 10 - 12 + 14) (h₁ : p = 3 - 6 + 9 - 12 + 15 - 18 + 21), q / p = 2 / 3  := by
  intro q p h₀ h₁
  subst h₀ h₁
  norm_num

end Problems.Minif2f.mathd_algebra_55
