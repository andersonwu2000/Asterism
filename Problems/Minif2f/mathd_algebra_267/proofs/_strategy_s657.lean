import Mathlib
import Problems.Minif2f.mathd_algebra_267.Defs

namespace Problems.Minif2f.mathd_algebra_267

-- Direct proof: x≠1, x≠-2 give nonzero denominators; field_simp turns
-- the equation into the polynomial identity (x+1)(x+2) = (x-2)(x-1),
-- which simplifies to 6x = 0, closed by linarith.
theorem s657 : ∀ (x : ℝ) (h₀ : x ≠ 1) (h₁ : x ≠ -2) (h₂ : (x + 1) / (x - 1) = (x - 2) / (x + 2)), x = 0  := by
  intro x h₀ h₁ h₂
  have hx1 : x - 1 ≠ 0 := sub_ne_zero.mpr h₀
  have hx2 : x + 2 ≠ 0 := by intro h; apply h₁; linarith
  field_simp at h₂
  linarith

end Problems.Minif2f.mathd_algebra_267
