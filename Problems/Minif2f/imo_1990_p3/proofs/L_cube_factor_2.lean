import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- cube_factor_2: ℕ factorization a^3+1=(a+1)*(a^2-a+1) via zify+ring (needs a≤a^2 for subtraction)
theorem cube_factor_2 : ∀ (a : ℕ), 1 ≤ a → a^3 + 1 = (a + 1) * (a^2 - a + 1) := by
  intro a ha
  zify [show a ≤ a ^ 2 from by nlinarith]
  ring

end Problems.Minif2f.imo_1990_p3
