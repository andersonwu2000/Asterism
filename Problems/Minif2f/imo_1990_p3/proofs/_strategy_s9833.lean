import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_two_m_p_sub_one_eq_two
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_p_sub_one_eq_one
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_two_m_eq_one_mod_p

namespace Problems.Minif2f.imo_1990_p3

-- Combine three sub-claims via orderOf chain:
-- 2^(2m)=1 (from m²∣2^m+1 + p∣m) and 2^(p-1)=1 (Fermat) give orderOf 2 ∣ gcd(2m,p-1);
-- with gcd=2 (needing ¬7∣m to kill the p=7 case), conclude orderOf 2 ∣ 2 ⇒ 2^2 = 1.
theorem s9833 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → (2 : ZMod p) ^ 2 = 1  := by
  intro m hm hdvd h3 h9 h7 p hp hge hpm
  have h_two_pow_two_m := two_pow_two_m_eq_one_mod_p m hm hdvd h3 h9 h7 p hp hge hpm
  have h_two_pow_p_sub := two_pow_p_sub_one_eq_one m hm hdvd h3 h9 h7 p hp hge hpm
  have h_gcd := gcd_two_m_p_sub_one_eq_two m hm hdvd h3 h9 h7 p hp hge hpm
  have hord1 : orderOf (2 : ZMod p) ∣ 2 * m := orderOf_dvd_of_pow_eq_one h_two_pow_two_m
  have hord2 : orderOf (2 : ZMod p) ∣ p - 1 := orderOf_dvd_of_pow_eq_one h_two_pow_p_sub
  have hord_gcd : orderOf (2 : ZMod p) ∣ 2 := h_gcd ▸ Nat.dvd_gcd hord1 hord2
  exact orderOf_dvd_iff_pow_eq_one.mp hord_gcd

end Problems.Minif2f.imo_1990_p3
