import Mathlib
import Problems.Minif2f.mathd_algebra_109.Defs

namespace Problems.Minif2f.mathd_algebra_109

-- Direct linear arithmetic: substituting a=4 into 3a+2b=12 yields 2b=0, hence b=0.
-- One-step `linarith` after introducing all binders; no decomposition needed.
theorem s526 : ∀ (a b : ℝ) (h₀ : 3 * a + 2 * b = 12) (h₁ : a = 4), b = 0  := by
  intro a b h₀ h₁
  linarith

end Problems.Minif2f.mathd_algebra_109
