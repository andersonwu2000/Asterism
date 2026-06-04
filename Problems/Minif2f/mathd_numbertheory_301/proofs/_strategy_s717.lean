import Mathlib
import Problems.Minif2f.mathd_numbertheory_301.Defs

namespace Problems.Minif2f.mathd_numbertheory_301

-- Direct: 3*(7j+3) = 21j+9 ≡ 9 ≡ 2 (mod 7); omega closes via linear arithmetic on ℕ mod.
theorem s717 : ∀ (j : ℕ) (h₀ : 0 < j), 3 * (7 * ↑j + 3) % 7 = 2  := by
  intro j _h₀
  omega

end Problems.Minif2f.mathd_numbertheory_301
