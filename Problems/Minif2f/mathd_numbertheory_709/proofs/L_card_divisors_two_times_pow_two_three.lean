import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- card_divisors_two_times_pow_two_three: uses Nat.Coprime.card_divisors_mul +
-- Nat.divisors_prime_pow to factor τ(2·2^a·3^b) = (a+2)(b+1) combinatorially
theorem card_divisors_two_times_pow_two_three :
    ∀ (a b : ℕ),
      Finset.card (Nat.divisors (2 * (2 ^ a * 3 ^ b))) = (a + 2) * (b + 1) := by
  intro a b
  have h2 : 2 * (2 ^ a * 3 ^ b) = 2 ^ (a + 1) * 3 ^ b := by ring
  rw [h2]
  have hcop : Nat.Coprime (2 ^ (a + 1)) (3 ^ b) := by
    apply Nat.Coprime.pow_left
    apply Nat.Coprime.pow_right
    norm_num
  rw [Nat.Coprime.card_divisors_mul hcop]
  have h2card : (2 ^ (a + 1)).divisors.card = a + 2 := by
    rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 2)]
    simp
  have h3card : (3 ^ b).divisors.card = b + 1 := by
    rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 3)]
    simp
  rw [h2card, h3card]

end Problems.Minif2f.mathd_numbertheory_709
