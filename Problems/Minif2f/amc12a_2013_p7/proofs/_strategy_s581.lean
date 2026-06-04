import Mathlib
import Problems.Minif2f.amc12a_2013_p7.Defs

namespace Problems.Minif2f.amc12a_2013_p7

-- Direct: instantiate h₀ at 4,5,6,7 to expose the four recurrence
-- equations linking s 4..s 9, then linarith eliminates s 5,6,8 using h₁,h₂.
theorem s581 : ∀ (s : ℕ → ℝ) (h₀ : ∀ n, s (n + 2) = s (n + 1) + s n) (h₁ : s 9 = 110) (h₂ : s 7 = 42), s 4 = 10  := by
  intro s h₀ h₁ h₂
  have e7 : s 9 = s 8 + s 7 := h₀ 7
  have e6 : s 8 = s 7 + s 6 := h₀ 6
  have e5 : s 7 = s 6 + s 5 := h₀ 5
  have e4 : s 6 = s 5 + s 4 := h₀ 4
  linarith

end Problems.Minif2f.amc12a_2013_p7
