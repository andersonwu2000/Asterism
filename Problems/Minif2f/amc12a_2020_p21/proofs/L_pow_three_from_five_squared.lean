-- Direct proof: lift 5²∣n to 5³∣n using gcd_mul_lcm + hlcm.
-- gcd(5!,n)·(5·gcd(10!,n)) = 120·n, then 5|gcd(5!,n), 5²|gcd(10!,n), 5²|n
-- gives 625·a·b = 3000·c → 5·a·b = 24·c → 5∣c → n = 25·c = 125·d.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9831

namespace Problems.Minif2f.amc12a_2020_p21

def pow_three_from_five_squared := @Problems.Minif2f.amc12a_2020_p21.s9831

end Problems.Minif2f.amc12a_2020_p21
