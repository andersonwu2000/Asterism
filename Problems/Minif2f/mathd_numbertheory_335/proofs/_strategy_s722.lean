import Mathlib
import Problems.Minif2f.mathd_numbertheory_335.Defs

namespace Problems.Minif2f.mathd_numbertheory_335

-- Direct: modular arithmetic — 5 * n % 7 = 5 * (n % 7) % 7 = 5*5 % 7 = 4.
theorem s722 : ∀ (n : ℕ) (h₀ : n % 7 = 5), 5 * n % 7 = 4  := by
  intro n h₀
  rw [Nat.mul_mod, h₀]

end Problems.Minif2f.mathd_numbertheory_335
