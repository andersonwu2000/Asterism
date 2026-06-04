import Mathlib
import Problems.Minif2f.mathd_algebra_119.Defs

namespace Problems.Minif2f.mathd_algebra_119

-- Direct: the two linear hypotheses uniquely determine e = 2 over ℝ.
-- 2d = 17e - 8 and 2e = d - 9 give 4e + 18 = 17e - 8 ⇒ 13e = 26 ⇒ e = 2; linarith closes it.
theorem s632 : ∀ (d e : ℝ) (h₀ : 2 * d = 17 * e - 8) (h₁ : 2 * e = d - 9), e = 2  := by
  intro d e h₀ h₁
  linarith

end Problems.Minif2f.mathd_algebra_119
