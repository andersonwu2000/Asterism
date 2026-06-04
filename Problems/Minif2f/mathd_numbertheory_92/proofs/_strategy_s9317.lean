import Mathlib
import Problems.Minif2f.mathd_numbertheory_92.Defs

namespace Problems.Minif2f.mathd_numbertheory_92

-- Direct closure: modular linear arithmetic.
-- 5 * 7 ≡ 1 (mod 17), so n ≡ 7 * 8 = 56 ≡ 5 (mod 17); omega handles this natively.
theorem s9317 : ∀ (n : ℕ) (h₀ : 5 * n % 17 = 8), n % 17 = 5  := by
  intro n h₀
  omega

end Problems.Minif2f.mathd_numbertheory_92
