import Mathlib
import Problems.Minif2f.mathd_numbertheory_458.Defs

namespace Problems.Minif2f.mathd_numbertheory_458

-- Direct: n % 8 = 7 ⇒ n % 4 = (n % 8) % 4 = 7 % 4 = 3, dispatched by `omega`.
theorem s732 : ∀ (n : ℕ) (h₀ : n % 8 = 7), n % 4 = 3  := by
  intro n h₀
  omega

end Problems.Minif2f.mathd_numbertheory_458
