import Mathlib
import Problems.Minif2f.mathd_numbertheory_48.Defs

namespace Problems.Minif2f.mathd_numbertheory_48

-- Direct proof: bound b ≤ 4 via nlinarith from h₁ (since 3b² grows fast),
-- then interval_cases on b discharges all five cases (0 killed by h₀,
-- 1/2/3 by h₁ arithmetic, 4 by rfl) via omega.
theorem s9312 : ∀ (b : ℕ) (h₀ : 0 < b) (h₁ : 3 * b ^ 2 + 2 * b + 1 = 57), b = 4  := by
  intro b h₀ h₁
  have hb : b ≤ 4 := by nlinarith
  interval_cases b <;> omega

end Problems.Minif2f.mathd_numbertheory_48
