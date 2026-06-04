import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_two_n_min_fac_pred_dvd_two
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_min_fac_pred_eq_one
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_two_n_eq_one_mod_min_fac

namespace Problems.Minif2f.imo_1990_p3

-- Decompose via order-of-2 in `ZMod p` where `p = Nat.minFac n`.
-- (A) `two_pow_two_n_eq_one_mod_min_fac` : `(2:ZMod p)^(2n) = 1`
--     — from `p ∣ n ∣ n^2 ∣ 2^n+1` so `2^n ≡ -1 (mod p)` and squaring.
-- (B) `two_pow_min_fac_pred_eq_one` : `(2:ZMod p)^(p-1) = 1`
--     — Fermat's little theorem (needs `p ≠ 2`, available since `n` is odd).
-- (C) `gcd_two_n_min_fac_pred_dvd_two` : `gcd(2n, p-1) ∣ 2`
--     — pure number theory from `Coprime n (p-1)`.
-- Combiner: A & B ⇒ `orderOf 2 ∣ gcd(2n, p-1)` by `Nat.dvd_gcd`, then C
-- gives `orderOf 2 ∣ 2`, closing the goal via `orderOf_dvd_iff_pow_eq_one`.
theorem s9691 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 →
      Nat.Coprime n (Nat.minFac n - 1) →
      (2 : ZMod (Nat.minFac n))^2 = 1  := by
  intro n hn hdvd hcop
  have h2n := two_pow_two_n_eq_one_mod_min_fac n hn hdvd hcop
  have hp1 := two_pow_min_fac_pred_eq_one n hn hdvd hcop
  have hgcd := gcd_two_n_min_fac_pred_dvd_two n hn hdvd hcop
  have hord1 : orderOf (2 : ZMod (Nat.minFac n)) ∣ 2*n :=
    orderOf_dvd_of_pow_eq_one h2n
  have hord2 : orderOf (2 : ZMod (Nat.minFac n)) ∣ Nat.minFac n - 1 :=
    orderOf_dvd_of_pow_eq_one hp1
  have hordg : orderOf (2 : ZMod (Nat.minFac n)) ∣ Nat.gcd (2*n) (Nat.minFac n - 1) :=
    Nat.dvd_gcd hord1 hord2
  have hord2' : orderOf (2 : ZMod (Nat.minFac n)) ∣ 2 := hordg.trans hgcd
  exact orderOf_dvd_iff_pow_eq_one.mp hord2'

end Problems.Minif2f.imo_1990_p3
