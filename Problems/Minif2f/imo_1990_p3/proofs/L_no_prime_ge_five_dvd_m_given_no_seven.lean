-- Case-split on whether the candidate prime equals 7.
-- The p = 7 case contradicts ¬ 7 ∣ m directly via h7.
-- Otherwise, defer to a Backward sub-goal that carries the explicit p ≠ 7
-- hypothesis, letting the eventual derivation pivot to q := Nat.minFac (m / 3)
-- (the smallest prime factor of m strictly above 3) instead of running the
-- gcd / order argument on the arbitrary p (which is the dead `s9848` shape).
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9852

namespace Problems.Minif2f.imo_1990_p3

def no_prime_ge_five_dvd_m_given_no_seven := @Problems.Minif2f.imo_1990_p3.s9852

end Problems.Minif2f.imo_1990_p3
