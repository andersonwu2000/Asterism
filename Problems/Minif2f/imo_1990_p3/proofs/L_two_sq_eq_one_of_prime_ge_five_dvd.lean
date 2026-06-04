import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- entry_kind: Backward
theorem two_sq_eq_one_of_prime_ge_five_dvd :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ n → (2 : ZMod p)^2 = 1 := by sorry

end Problems.Minif2f.imo_1990_p3
