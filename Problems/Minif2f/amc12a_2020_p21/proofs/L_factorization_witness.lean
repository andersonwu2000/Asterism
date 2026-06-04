-- Decomposition: pick the canonical witness `(a,b,d) = (n.factorization 2,
-- n.factorization 3, n.factorization 7)` and split into (1) prime-exponent
-- bounds at 2/3/7 derived from the lcm/gcd identity, and (2) the canonical
-- product form (no other primes + exponent at 5 is forced to 3).
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9715

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_witness := @Problems.Minif2f.amc12a_2020_p21.s9715

end Problems.Minif2f.amc12a_2020_p21
