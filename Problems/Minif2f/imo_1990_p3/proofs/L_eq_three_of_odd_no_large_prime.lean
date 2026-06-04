-- Reduce `m = 3` to: (a) `m` is a pure power of 3, and (b) the 3-adic valuation is exactly 1.
-- (a) `m_eq_three_pow_factorization`: every prime factor of `m` must be 3 (Odd ⇒ no 2;
--     hypothesis ⇒ no prime ≥ 5; 3 is the only prime in [3,5)), so `m = 3 ^ v₃(m)`.
-- (b) `factorization_three_eq_one`: `3 ∣ m` gives `1 ≤ v₃(m)`; `¬ 9 ∣ m` gives `v₃(m) < 2`.
-- Substituting (b) into (a) yields `m = 3 ^ 1 = 3`.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9692

namespace Problems.Minif2f.imo_1990_p3

def eq_three_of_odd_no_large_prime := @Problems.Minif2f.imo_1990_p3.s9692

end Problems.Minif2f.imo_1990_p3
