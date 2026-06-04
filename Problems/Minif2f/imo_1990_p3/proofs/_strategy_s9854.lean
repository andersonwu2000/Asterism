import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_two_m_eq_one_mod_p
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_p_sub_one_eq_one
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_two_m_q_sub_one_dvd_two
import Problems.Minif2f.imo_1990_p3.proofs.L_q_prime_and_ge_five

namespace Problems.Minif2f.imo_1990_p3

-- Pivot to q := Nat.minFac (m/3) and run the orderOf-gcd argument.
-- Sub-goals: (1) q is prime ≥ 5, (2) gcd(2m, q-1) ∣ 2 (the hard piece — uses
-- minimality of q together with ¬7∣m to collapse odd part of the gcd to 1).
-- Combined with the already-proved 2^(2m) = 1 and Fermat 2^(q-1) = 1 lemmas,
-- orderOf 2 ∣ 2 in ZMod q gives 2^2 = 1.
theorem s9854 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      (2 : ZMod (Nat.minFac (m / 3))) ^ 2 = 1  := by
  intro m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have h_prime_ge :=
    q_prime_and_ge_five m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  obtain ⟨hq_prime, hq_ge⟩ := h_prime_ge
  have hq_dvd_m : Nat.minFac (m / 3) ∣ m :=
    (Nat.minFac_dvd (m / 3)).trans (Nat.div_dvd_of_dvd h3)
  have h_two_pow_two_m : (2 : ZMod (Nat.minFac (m / 3))) ^ (2 * m) = 1 :=
    two_pow_two_m_eq_one_mod_p m hm hpow h3 h9 h7 _ hq_prime hq_ge hq_dvd_m
  have h_two_pow_q_sub : (2 : ZMod (Nat.minFac (m / 3))) ^ (Nat.minFac (m / 3) - 1) = 1 :=
    two_pow_p_sub_one_eq_one m hm hpow h3 h9 h7 _ hq_prime hq_ge hq_dvd_m
  have h_gcd_dvd :=
    gcd_two_m_q_sub_one_dvd_two m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have hord1 : orderOf (2 : ZMod (Nat.minFac (m / 3))) ∣ 2 * m :=
    orderOf_dvd_of_pow_eq_one h_two_pow_two_m
  have hord2 : orderOf (2 : ZMod (Nat.minFac (m / 3))) ∣ Nat.minFac (m / 3) - 1 :=
    orderOf_dvd_of_pow_eq_one h_two_pow_q_sub
  have hord_gcd : orderOf (2 : ZMod (Nat.minFac (m / 3))) ∣ 2 :=
    (Nat.dvd_gcd hord1 hord2).trans h_gcd_dvd
  exact orderOf_dvd_iff_pow_eq_one.mp hord_gcd

end Problems.Minif2f.imo_1990_p3
