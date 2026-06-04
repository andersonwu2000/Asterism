import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_q_pred_two_m_dvd_six_kernel
import Problems.Minif2f.imo_1990_p3.proofs.L_pow_q_pred_eq_one_kernel
import Problems.Minif2f.imo_1990_p3.proofs.L_pow_two_m_eq_one_kernel

namespace Problems.Minif2f.imo_1990_p3

-- Decompose `(2:ZMod q)^6 = 1` via orderOf chain: 2^(q-1)=1 (Fermat) + 2^(2m)=1 (m²∣2^m+1)
-- + gcd(q-1,2m) ∣ 6 (only common prime factors are 2,3 since q is minFac of m/3 with 9∤m, m odd).
-- Combinator: orderOf 2 ∣ q-1, orderOf 2 ∣ 2m ⇒ orderOf 2 ∣ gcd ∣ 6 ⇒ 2^6 = 1.
theorem s9862 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      3 ∣ (Nat.minFac (m / 3) - 1) →
      (2 : ZMod (Nat.minFac (m / 3)))^6 = 1  := by
  intro m hm2 hdvd h3m h9m h7m p hp h5 hp7 hpm h3q
  have h1 := pow_q_pred_eq_one_kernel m hm2 hdvd h3m h9m h7m p hp h5 hp7 hpm h3q
  have h2 := pow_two_m_eq_one_kernel m hm2 hdvd h3m h9m h7m p hp h5 hp7 hpm h3q
  have hgcd := gcd_q_pred_two_m_dvd_six_kernel m hm2 hdvd h3m h9m h7m p hp h5 hp7 hpm h3q


  have ord1 := orderOf_dvd_of_pow_eq_one h1
  have ord2 := orderOf_dvd_of_pow_eq_one h2
  have ord_gcd : orderOf (2 : ZMod (Nat.minFac (m / 3))) ∣ Nat.gcd (Nat.minFac (m / 3) - 1) (2*m) :=
    Nat.dvd_gcd ord1 ord2
  exact orderOf_dvd_iff_pow_eq_one.mp (ord_gcd.trans hgcd)



end Problems.Minif2f.imo_1990_p3
