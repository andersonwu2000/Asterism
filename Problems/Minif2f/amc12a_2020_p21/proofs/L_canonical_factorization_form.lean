-- Decomposition: split the canonical form into (1) support confined to
-- {2,3,5,7}, giving `n = 2^a · 3^b · 5^(n.fact 5) · 7^d`, and
-- (2) the exponent at 5 is exactly 3; rewrite (2) into (1) to close.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9759

namespace Problems.Minif2f.amc12a_2020_p21

def canonical_factorization_form := @Problems.Minif2f.amc12a_2020_p21.s9759

end Problems.Minif2f.amc12a_2020_p21
