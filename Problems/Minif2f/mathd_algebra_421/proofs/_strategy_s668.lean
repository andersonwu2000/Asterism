import Mathlib
import Problems.Minif2f.mathd_algebra_421.Defs

namespace Problems.Minif2f.mathd_algebra_421

-- Direct proof: from h₀=h₁ derive a(a+6)=0, from h₂=h₃ derive c(c+6)=0.
-- Each factors into a ∈ {0,-6} and c ∈ {0,-6}; only a=-6, c=0 satisfies a<c.
theorem s668 : ∀ (a b c d : ℝ) (h₀ : b = a ^ 2 + 4 * a + 6) (h₁ : b = 1 / 2 * a ^ 2 + a + 6) (h₂ : d = c ^ 2 + 4 * c + 6) (h₃ : d = 1 / 2 * c ^ 2 + c + 6) (h₄ : a < c), c - a = 6  := by
  intro a b c d h₀ h₁ h₂ h₃ h₄
  have ha : a * (a + 6) = 0 := by nlinarith
  have hc : c * (c + 6) = 0 := by nlinarith
  have ha2 : a = 0 ∨ a = -6 := by
    rcases mul_eq_zero.mp ha with h | h
    · left; exact h
    · right; linarith
  have hc2 : c = 0 ∨ c = -6 := by
    rcases mul_eq_zero.mp hc with h | h
    · left; exact h
    · right; linarith
  rcases ha2 with rfl | rfl <;> rcases hc2 with rfl | rfl <;> linarith

end Problems.Minif2f.mathd_algebra_421
