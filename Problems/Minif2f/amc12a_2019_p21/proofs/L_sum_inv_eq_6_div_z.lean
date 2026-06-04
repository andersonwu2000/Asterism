-- 3-way decomposition: partition Finset.Icc 1 12 by k mod 4 residue class.
-- Odd k (1,3,5,7,9,11) → k^2 mod 8 = 1, so 1/z^(k^2) = 1/z (sub-sum 6/z).
-- k ≡ 2 mod 4 (2,6,10) → k^2 mod 8 = 4, so 1/z^(k^2) = 1/(-1) = -1 (sub-sum -3).
-- k ≡ 0 mod 4 (4,8,12) → k^2 mod 8 = 0, so 1/z^(k^2) = 1 (sub-sum 3).
-- Closer: 6/z + (-3) + 3 = 6/z.
import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs._strategy_s9636

namespace Problems.Minif2f.amc12a_2019_p21

def sum_inv_eq_6_div_z := @Problems.Minif2f.amc12a_2019_p21.s9636

end Problems.Minif2f.amc12a_2019_p21
