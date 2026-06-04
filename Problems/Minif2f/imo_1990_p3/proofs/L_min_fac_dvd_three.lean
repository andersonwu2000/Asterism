-- Decompose via order-of-2 mod p := minFac n: the order divides 2, forcing p ∣ 3.
-- (a) `coprime_n_min_fac_pred`: gcd(n, p-1) = 1 — every prime factor of n is ≥ p
--     while every divisor of p-1 is < p, so they share no common factors. Pure
--     minFac structure, independent of the 2^n+1 hypothesis.
-- (b) `min_fac_dvd_three_with_coprime`: given the coprime fact, FLT + the cyclic
--     order argument (orderOf 2 ∣ 2n and ∣ p-1 ⇒ ∣ 2) yields 2² ≡ 1 mod p, hence p ∣ 3.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9493

namespace Problems.Minif2f.imo_1990_p3

def min_fac_dvd_three := @Problems.Minif2f.imo_1990_p3.s9493

end Problems.Minif2f.imo_1990_p3
