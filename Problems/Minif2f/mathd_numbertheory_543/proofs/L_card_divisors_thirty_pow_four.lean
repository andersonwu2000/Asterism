import Mathlib
import Problems.Minif2f.mathd_numbertheory_543.Defs

namespace Problems.Minif2f.mathd_numbertheory_543

-- card_divisors_thirty_pow_four: τ(30^4)=125 via Coprime.card_divisors_mul + prime-power card
-- 30^4 = 2^4·3^4·5^4; coprimality splits divisors multiplicatively; each factor has 4+1=5 divisors.
theorem card_divisors_thirty_pow_four : (Nat.divisors (30 ^ 4)).card = 125 := by
  have h1 : (30 : ℕ)^4 = 2^4 * 3^4 * 5^4 := by norm_num
  have h2 : Nat.Coprime (2^4 * 3^4) (5^4) := by norm_num
  have h3 : Nat.Coprime (2^4) (3^4) := by norm_num
  rw [h1, h2.card_divisors_mul, h3.card_divisors_mul]
  have ha : (Nat.divisors (2^4)).card = 5 := by
    rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 2)]; simp
  have hb : (Nat.divisors (3^4)).card = 5 := by
    rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 3)]; simp
  have hc : (Nat.divisors (5^4)).card = 5 := by
    rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 5)]; simp
  rw [ha, hb, hc]

end Problems.Minif2f.mathd_numbertheory_543
