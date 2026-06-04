-- 3-way: partition Finset.Icc 1 12 by k mod 4 residue class.
-- Odd k (1,3,5,7,9,11) → k^2 ≡ 1 (mod 8), z^(k^2) = z, sub-sum = 6z.
-- k ≡ 2 mod 4 (2,6,10) → k^2 ≡ 4 (mod 8), z^(k^2) = z^4 = -1, sub-sum = -3.
-- k ≡ 0 mod 4 (4,8,12) → k^2 ≡ 0 (mod 8), z^(k^2) = 1, sub-sum = 3.
-- Closer: rewrite the Icc as the disjoint union; sub-sums combine via ring (6z + (-3) + 3 = 6z).
import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs._strategy_s9681

namespace Problems.Minif2f.amc12a_2019_p21

def sum_eq_6z_using_z8 := @Problems.Minif2f.amc12a_2019_p21.s9681

end Problems.Minif2f.amc12a_2019_p21
