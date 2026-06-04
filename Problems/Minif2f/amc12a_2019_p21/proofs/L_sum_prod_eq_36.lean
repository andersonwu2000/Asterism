-- 2-way decomposition: collapse each Σ_{k=1..12} z^(k^2) using k^2 mod 8 ∈ {1,4,0}
-- with multiplicities (6,3,3) and z^4=-1 ⇒ z^8=1: ∑ z^(k^2) = 6z and ∑ 1/z^(k^2) = 6/z.
-- Closer: (6z)*(6/z) = 36 via field_simp (uses z≠0).
import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs._strategy_s9465

namespace Problems.Minif2f.amc12a_2019_p21

def sum_prod_eq_36 := @Problems.Minif2f.amc12a_2019_p21.s9465

end Problems.Minif2f.amc12a_2019_p21
