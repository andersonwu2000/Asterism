-- Pin v_3(2^n+1) exactly via a two-sided pow-divisibility sandwich.
-- Lower: 3^(1+v_3(n)) ∣ 2^n+1.  Upper: ¬ 3^(2+v_3(n)) ∣ 2^n+1.
-- Combine via `Nat.Prime.pow_dvd_iff_le_factorization` (for p=3, n≠0):
--   lower gives 1+v_3(n) ≤ v_3(2^n+1); upper rules out ≥ 2+v_3(n);
--   omega closes equality.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9690

namespace Problems.Minif2f.imo_1990_p3

def lte_three_step := @Problems.Minif2f.imo_1990_p3.s9690

end Problems.Minif2f.imo_1990_p3
