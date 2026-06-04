import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_two_m_p_sub_one_dvd_two_2
import Problems.Minif2f.imo_1990_p3.proofs.L_pow_p_sub_one_eq_one
import Problems.Minif2f.imo_1990_p3.proofs.L_pow_two_m_eq_one

namespace Problems.Minif2f.imo_1990_p3

-- Lift to orderOf via gcd-collapse: (2:ZMod p)^(2m)=1 from p∣m and m²∣2^m+1,
-- (2:ZMod p)^(p-1)=1 from Fermat, gcd(2m,p-1)∣2 from the 7-free hypothesis;
-- combine via orderOf_dvd_of_pow_eq_one + Nat.dvd_gcd to get orderOf(2) ∣ 2.
theorem s9849 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → (2 : ZMod p) ^ 2 = 1  := by
  intro m hm hpow h3 h9 h7 p hp h5 hpm
  have h_pow_2m : (2 : ZMod p) ^ (2 * m) = 1 :=
    pow_two_m_eq_one m hm hpow h3 h9 h7 p hp h5 hpm
  have h_pow_p1 : (2 : ZMod p) ^ (p - 1) = 1 :=
    pow_p_sub_one_eq_one m hm hpow h3 h9 h7 p hp h5 hpm
  have h_gcd_dvd : Nat.gcd (2 * m) (p - 1) ∣ 2 :=
    gcd_two_m_p_sub_one_dvd_two_2 m hm hpow h3 h9 h7 p hp h5 hpm
  have hord_2m : orderOf (2 : ZMod p) ∣ 2 * m := orderOf_dvd_of_pow_eq_one h_pow_2m
  have hord_p1 : orderOf (2 : ZMod p) ∣ p - 1 := orderOf_dvd_of_pow_eq_one h_pow_p1
  have hord_gcd : orderOf (2 : ZMod p) ∣ Nat.gcd (2 * m) (p - 1) := Nat.dvd_gcd hord_2m hord_p1
  have hord_2 : orderOf (2 : ZMod p) ∣ 2 := hord_gcd.trans h_gcd_dvd
  exact orderOf_dvd_iff_pow_eq_one.mp hord_2

end Problems.Minif2f.imo_1990_p3
