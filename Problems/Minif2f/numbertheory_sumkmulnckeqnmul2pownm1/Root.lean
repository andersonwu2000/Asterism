-- Decompose ∑_{k=1}^{n} k * C(n,k) = n * 2^(n-1) into:
--   sum_range_id_mul_choose: same identity over Finset.range (m+1) (abstracts away h₀ via Nat sub).
--   icc_eq_range_sum_id_choose: the k=0 term vanishes, converting Icc 1 n to range (n+1).
-- Combine by rewriting LHS to range form then applying the main identity.
import Mathlib
import Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.Defs
import Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.proofs._strategy_s756

namespace Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1

def main := @Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.s756

end Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1
