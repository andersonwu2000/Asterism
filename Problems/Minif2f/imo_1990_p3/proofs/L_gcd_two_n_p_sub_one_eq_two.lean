import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- entry_kind: Backward
theorem gcd_two_n_p_sub_one_eq_two :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ n → Nat.gcd (2 * n) (p - 1) = 2 := by sorry

end Problems.Minif2f.imo_1990_p3
