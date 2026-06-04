-- Direct leaf proof (sorry-free): apply the ordProj_dvd upper-bound recipe at p=3.
-- Chain n ∣ lcm 5! n = 5 * gcd 10! n ∣ 5*10!, then `¬ 3^5 ∣ 5*10!` (by norm_num on
-- 10!'s factorization at 3 = 4) combined with `Nat.pow_dvd_pow` + `ordProj_dvd n 3`
-- via contrapositive yields `n.factorization 3 < 5`, hence ≤ 4.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9799

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_three_le_four := @Problems.Minif2f.amc12a_2020_p21.s9799

end Problems.Minif2f.amc12a_2020_p21
