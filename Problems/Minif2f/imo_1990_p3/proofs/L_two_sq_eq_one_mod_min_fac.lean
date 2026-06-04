-- Decompose via order-of-2 in `ZMod p` where `p = Nat.minFac n`.
-- (A) `two_pow_two_n_eq_one_mod_min_fac` : `(2:ZMod p)^(2n) = 1`
--     — from `p ∣ n ∣ n^2 ∣ 2^n+1` so `2^n ≡ -1 (mod p)` and squaring.
-- (B) `two_pow_min_fac_pred_eq_one` : `(2:ZMod p)^(p-1) = 1`
--     — Fermat's little theorem (needs `p ≠ 2`, available since `n` is odd).
-- (C) `gcd_two_n_min_fac_pred_dvd_two` : `gcd(2n, p-1) ∣ 2`
--     — pure number theory from `Coprime n (p-1)`.
-- Combiner: A & B ⇒ `orderOf 2 ∣ gcd(2n, p-1)` by `Nat.dvd_gcd`, then C
-- gives `orderOf 2 ∣ 2`, closing the goal via `orderOf_dvd_iff_pow_eq_one`.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9691

namespace Problems.Minif2f.imo_1990_p3

def two_sq_eq_one_mod_min_fac := @Problems.Minif2f.imo_1990_p3.s9691

end Problems.Minif2f.imo_1990_p3
