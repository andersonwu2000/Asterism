-- Two-step LTE-style decomposition.
-- (A) `lte_three_step`: 3-adic valuation identity v_3(2^n+1) = 1 + v_3(n) for odd n with 3 ∣ n.
-- (B) `factorization_sq_le`: from n² ∣ 2^n+1, get 2·v_3(n) ≤ v_3(2^n+1)
--     (squared-divisibility bound on the 3-adic valuation).
-- Combine: 9 ∣ n forces v_3(n) ≥ 2, but (A)+(B) give 2·v_3(n) ≤ 1 + v_3(n), so v_3(n) ≤ 1. omega.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9646

namespace Problems.Minif2f.imo_1990_p3

def nine_not_dvd_of_odd := @Problems.Minif2f.imo_1990_p3.s9646

end Problems.Minif2f.imo_1990_p3
