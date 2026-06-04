import Mathlib
import Problems.Minif2f.numbertheory_2dvd4expn.Defs

namespace Problems.Minif2f.numbertheory_2dvd4expn

-- Direct leaf: 2 ∣ 4 by `decide`, lift to 4^n via `dvd_pow` using h₀ : n ≠ 0.
theorem s750 : ∀ (n : ℕ) (h₀ : n ≠ 0), 2 ∣ 4 ^ n  := by
  intro n h₀
  exact dvd_pow (by decide : (2:ℕ) ∣ 4) h₀

end Problems.Minif2f.numbertheory_2dvd4expn
