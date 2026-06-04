import Mathlib
import Problems.Minif2f.amc12_2000_p11.Defs

namespace Problems.Minif2f.amc12_2000_p11

-- Direct proof: clear denominators with field_simp using a≠0, b≠0, then close
-- via linear_combination from h₁ : a*b = a-b. No decomposition needed.
theorem s778 : ∀ (a b : ℝ) (h₀ : a ≠ 0 ∧ b ≠ 0) (h₁ : a * b = a - b),
    a / b + b / a - a * b = 2  := by
  intro a b ⟨ha, hb⟩ h₁
  field_simp
  linear_combination (-(a - b + a*b)) * h₁

end Problems.Minif2f.amc12_2000_p11
