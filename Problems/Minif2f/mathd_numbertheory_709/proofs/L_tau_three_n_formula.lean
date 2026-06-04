import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- tau_three_n_formula: divisor count of 3*(2^a * 3^b * r) using coprimality splitting
-- Rewrite 3*(2^a*3^b*r) = 2^a*3^(b+1)*r, then split via Nat.Coprime.card_divisors_mul
-- and evaluate prime-power divisor counts with Nat.divisors_prime_pow.
theorem tau_three_n_formula :
    ∀ (a b r : ℕ), Nat.Coprime r 6 → 0 < r →
      Finset.card (Nat.divisors (3 * (2 ^ a * 3 ^ b * r)))
        = (a + 1) * (b + 2) * Finset.card (Nat.divisors r) := by
  intro a b r hcop hr
  have h3 : 3 * (2 ^ a * 3 ^ b * r) = 2 ^ a * 3 ^ (b + 1) * r := by ring
  rw [h3]
  have hcop_2_r : Nat.Coprime (2 ^ a) r := by
    apply Nat.Coprime.symm
    apply Nat.Coprime.pow_right
    exact (Nat.Coprime.coprime_dvd_right (by norm_num : 2 ∣ 6) hcop)
  have hcop_3_r : Nat.Coprime (3 ^ (b + 1)) r := by
    apply Nat.Coprime.symm
    apply Nat.Coprime.pow_right
    exact (Nat.Coprime.coprime_dvd_right (by norm_num : 3 ∣ 6) hcop)
  have hcop_23 : Nat.Coprime (2 ^ a) (3 ^ (b + 1)) := by
    apply Nat.Coprime.pow_left
    apply Nat.Coprime.pow_right
    norm_num
  have hcop_23r : Nat.Coprime (2 ^ a * 3 ^ (b + 1)) r :=
    hcop_2_r.mul_left hcop_3_r
  rw [Nat.Coprime.card_divisors_mul hcop_23r]
  rw [Nat.Coprime.card_divisors_mul hcop_23]
  rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 2)]
  rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 3)]
  simp [Finset.card_map]

end Problems.Minif2f.mathd_numbertheory_709
