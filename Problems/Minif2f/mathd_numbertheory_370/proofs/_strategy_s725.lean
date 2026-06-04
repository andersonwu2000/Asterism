import Mathlib
import Problems.Minif2f.mathd_numbertheory_370.Defs

namespace Problems.Minif2f.mathd_numbertheory_370

-- Direct decision procedure: `omega` discharges linear arithmetic over ℕ with mod.
-- Given `n % 7 = 3`, we have `2 * n + 1 ≡ 2 * 3 + 1 = 7 ≡ 0 (mod 7)`; omega handles
-- the mod-7 case-split and closes the goal without sub-goals.
theorem s725 : ∀ (n : ℕ) (h₀ : n % 7 = 3), (2 * n + 1) % 7 = 0  := by
  intro n h₀
  omega

end Problems.Minif2f.mathd_numbertheory_370
