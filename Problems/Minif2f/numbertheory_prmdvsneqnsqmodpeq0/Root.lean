-- Direct proof: rewrite `n^2 % p = 0` as `↑p ∣ n^2`, then split the iff.
-- Forward uses `dvd_pow`; backward uses primality via `Prime.dvd_of_dvd_pow`.
import Mathlib
import Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0.Defs
import Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0.proofs._strategy_s753

namespace Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0

def main := @Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0.s753

end Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0
