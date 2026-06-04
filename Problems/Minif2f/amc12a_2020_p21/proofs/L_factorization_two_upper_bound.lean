-- Direct upper-bound recipe at p = 2 (parallels seven_factorization_le_one):
-- chain n ∣ Nat.lcm 5! n = 5·gcd 10! n ∣ 5·10!, then since ¬ 2^9 ∣ 5·10!
-- (norm_num on Nat.factorial), `ordProj_dvd n 2` + `Nat.pow_dvd_pow` force
-- `n.factorization 2 < 9`. No sub-goals — leaf-bypass ships this directly.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9801

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_two_upper_bound := @Problems.Minif2f.amc12a_2020_p21.s9801

end Problems.Minif2f.amc12a_2020_p21
