-- Closed numerical fact: 20! = 2^18·3^8·5^4·…, 200000 = 2^6·5^5,
-- so gcd = 2^6·5^4 = 40000. `decide` reduces via the Euclidean
-- algorithm on Nat (no axioms; native_decide introduces rogue ax).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_169.Defs
import Problems.Minif2f.mathd_numbertheory_169.proofs._strategy_s9263

namespace Problems.Minif2f.mathd_numbertheory_169

def main := @Problems.Minif2f.mathd_numbertheory_169.s9263

end Problems.Minif2f.mathd_numbertheory_169
