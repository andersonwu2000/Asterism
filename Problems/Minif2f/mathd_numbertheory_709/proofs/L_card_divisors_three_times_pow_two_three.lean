import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- card_divisors_three_times_pow_two_three: rewrite 3·2^a·3^b = 2^a·3^(b+1), split by
-- Nat.Coprime.card_divisors_mul, then count each prime-power factor via
-- Nat.divisors_prime_pow; coprimeness from Nat.pow_gcd_pow_of_gcd_eq_one.
theorem card_divisors_three_times_pow_two_three :
    ∀ (a b : ℕ),
      Finset.card (Nat.divisors (3 * (2 ^ a * 3 ^ b))) = (a + 1) * (b + 2) := by
  intro a b
  have h1 : 3 * (2 ^ a * 3 ^ b) = 2 ^ a * 3 ^ (b + 1) := by ring
  rw [h1]
  rw [Nat.Coprime.card_divisors_mul]
  · rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 2) a]
    rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 3) (b + 1)]
    simp
  · exact Nat.pow_gcd_pow_of_gcd_eq_one rfl

end Problems.Minif2f.mathd_numbertheory_709
