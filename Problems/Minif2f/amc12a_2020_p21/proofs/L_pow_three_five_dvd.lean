-- Bootstrap divisibility: lift 5 ∣ n to 5^2 ∣ n via the lcm/gcd equation,
-- then lift 5^2 ∣ n to 5^3 ∣ n via the same identity (gcd_mul_lcm + coprime trick).
-- Each lifting step uses 5!·n = lcm(5!,n)·gcd(5!,n) substituted with `hlcm`,
-- giving 24·n = gcd(10!,n)·gcd(5!,n) and a 5-adic valuation bump.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9811

namespace Problems.Minif2f.amc12a_2020_p21

def pow_three_five_dvd := @Problems.Minif2f.amc12a_2020_p21.s9811

end Problems.Minif2f.amc12a_2020_p21
