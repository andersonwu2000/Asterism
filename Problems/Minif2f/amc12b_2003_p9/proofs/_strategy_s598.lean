import Mathlib
import Problems.Minif2f.amc12b_2003_p9.Defs

namespace Problems.Minif2f.amc12b_2003_p9

-- Direct: unfold f via h₀, then linarith closes (4a = 12 ⇒ 10a = 30).
theorem s598 : ∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = a * x + b) (h₁ : f 6 - f 2 = 12), f 12 - f 2 = 30  := by
  intro a b f h₀ h₁
  simp only [h₀] at h₁ ⊢
  linarith

end Problems.Minif2f.amc12b_2003_p9
