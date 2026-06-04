import Mathlib
import Problems.Minif2f.amc12a_2013_p8.Defs

namespace Problems.Minif2f.amc12a_2013_p8

-- Direct algebraic proof: clear denominators in h₃ to derive (x-y)*(x*y-2) = 0,
-- then dispatch on x ≠ y to conclude x*y = 2.
theorem s582 : ∀ (x y : ℝ) (h₀ : x ≠ 0) (h₁ : y ≠ 0) (h₂ : x ≠ y)
    (h₃ : x + 2 / x = y + 2 / y), x * y = 2 := by
  intro x y h₀ h₁ h₂ h₃
  have hxy : x * y ≠ 0 := mul_ne_zero h₀ h₁
  have hxy_diff : x - y ≠ 0 := sub_ne_zero.mpr h₂
  field_simp at h₃
  have key : (x - y) * (x * y - 2) = 0 := by nlinarith [h₃, sq_nonneg (x - y)]
  rcases mul_eq_zero.mp key with h | h
  · exact absurd h hxy_diff
  · linarith

end Problems.Minif2f.amc12a_2013_p8
