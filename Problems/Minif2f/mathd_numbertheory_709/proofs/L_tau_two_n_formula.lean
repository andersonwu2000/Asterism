import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_709

-- tau_two_n_formula: multiplicativity of τ via Nat.Coprime.card_divisors_mul and
-- Nat.divisors_prime_pow; rewrite 2*(2^a*3^b*r) = 2^(a+1)*(3^b*r), split coprime
-- pairs, then collapse prime-power divisor counts to (a+2)*(b+1)*τ(r).
theorem tau_two_n_formula :
    ∀ (a b r : ℕ), Nat.Coprime r 6 → 0 < r →
      Finset.card (Nat.divisors (2 * (2 ^ a * 3 ^ b * r)))
        = (a + 2) * (b + 1) * Finset.card (Nat.divisors r) := by
  intro a b r hcop hr
  have h1 : 2 * (2 ^ a * 3 ^ b * r) = 2 ^ (a + 1) * (3 ^ b * r) := by ring
  rw [h1]
  have hcop2 : Nat.Coprime r 2 := hcop.coprime_dvd_right (by norm_num)
  have hcop3 : Nat.Coprime r 3 := hcop.coprime_dvd_right (by norm_num)
  have hcop23 : Nat.Coprime (2 ^ (a + 1)) (3 ^ b * r) := by
    apply Nat.Coprime.mul_right
    · apply Nat.Coprime.pow_left; apply Nat.Coprime.pow_right; norm_num
    · apply Nat.Coprime.pow_left; exact hcop2.symm
  rw [Nat.Coprime.card_divisors_mul hcop23]
  have hcop3b : Nat.Coprime (3 ^ b) r := by
    apply Nat.Coprime.pow_left; exact hcop3.symm
  rw [Nat.Coprime.card_divisors_mul hcop3b]
  rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 2)]
  rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime 3)]
  simp
  ring

end Problems.Minif2f.mathd_numbertheory_709
