import Mathlib
import Problems.Minif2f.amc12b_2020_p5.Defs

namespace Problems.Minif2f.amc12b_2020_p5

-- Direct: linarith on the two ℚ-equations gives (a:ℚ) = 42; cast back to ℕ.
theorem s600 : ∀ (a b : ℕ) (h₀ : (5 : ℚ) / 8 * b = 2 / 3 * a + 7) (h₁ : (b : ℚ) - 5 / 8 * b = a - 2 / 3 * a + 7), a = 42  := by
  intro a b h₀ h₁
  have ha : (a : ℚ) = 42 := by linarith
  exact_mod_cast ha

end Problems.Minif2f.amc12b_2020_p5
