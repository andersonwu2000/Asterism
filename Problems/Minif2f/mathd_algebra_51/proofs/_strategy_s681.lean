import Mathlib
import Problems.Minif2f.mathd_algebra_51.Defs

namespace Problems.Minif2f.mathd_algebra_51

-- Direct linarith: a = (2/5)·b and a+b = 35 force b = 25, a = 10, hence b−a = 15.
theorem s681 : ∀ (a b : ℝ) (h₀ : 0 < a ∧ 0 < b) (h₁ : a + b = 35) (h₂ : a = 2 / 5 * b), b - a = 15  := by
  intro a b _ h₁ h₂
  linarith

end Problems.Minif2f.mathd_algebra_51
