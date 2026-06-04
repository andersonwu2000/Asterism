import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_709

-- dvd_pow_two_three_coprime_six_eq_one: any divisor of 2^a*3^b coprime to 6 must be 1,
-- via Nat.Coprime.dvd_of_dvd_mul_left stripping the 2^a factor, then gcd collapse on 3^b.
theorem dvd_pow_two_three_coprime_six_eq_one :
    ∀ (a b m : ℕ), m ∣ 2 ^ a * 3 ^ b → Nat.Coprime m 6 → m = 1 := by
  intro a b m hdvd hcop
  have hcop2 : Nat.Coprime m 2 := hcop.coprime_dvd_right (by norm_num)
  have hcop3 : Nat.Coprime m 3 := hcop.coprime_dvd_right (by norm_num)
  have hcop2a : Nat.Coprime m (2 ^ a) := hcop2.pow_right a
  have hdvd3 : m ∣ 3 ^ b := hcop2a.dvd_of_dvd_mul_left hdvd
  have hcop3b : Nat.Coprime m (3 ^ b) := hcop3.pow_right b
  have hm_dvd_gcd : m ∣ Nat.gcd m (3 ^ b) := Nat.dvd_gcd (dvd_refl m) hdvd3
  have hm_eq : m = Nat.gcd m (3 ^ b) :=
    Nat.dvd_antisymm hm_dvd_gcd (Nat.gcd_dvd_left m (3 ^ b))
  rw [hm_eq]
  exact hcop3b

end Problems.Minif2f.mathd_numbertheory_709
