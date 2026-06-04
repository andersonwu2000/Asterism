import Mathlib
import Problems.Minif2f.mathd_algebra_96.Defs

namespace Problems.Minif2f.mathd_algebra_96

-- Direct: summing h₁ + h₂ + h₃ telescopes log-terms ⇒ a + 15 + (-7) = 0 ⇒ a = -8.
-- linarith handles the linear combination over ℝ.
theorem s694 : ∀ (x y z a : ℝ) (h₀ : 0 < x ∧ 0 < y ∧ 0 < z) (h₁ : Real.log x - Real.log y = a) (h₂ : Real.log y - Real.log z = 15) (h₃ : Real.log z - Real.log x = -7), a = -8  := by
  intro x y z a h₀ h₁ h₂ h₃
  linarith

end Problems.Minif2f.mathd_algebra_96
