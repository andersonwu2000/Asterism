-- Direct proof: 2^3 = 8 ∣ 5! = 120, so 8 ∣ lcm(5!,n) = 5·gcd(10!,n); coprimality
-- 8 ⊥ 5 gives 8 ∣ gcd(10!,n) ∣ n (mirrors `three_dvd_n` recipe at prime 2^3).
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9812

namespace Problems.Minif2f.amc12a_2020_p21

def pow_three_two_dvd := @Problems.Minif2f.amc12a_2020_p21.s9812

end Problems.Minif2f.amc12a_2020_p21
