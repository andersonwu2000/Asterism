-- cos x - sin x = √2 · sin(π/4 - x), so ∑ (cos(nπ/180) - sin(nπ/180)) = √2 · ∑ sin((45-n)π/180).
-- (1) cos_minus_sin_eq_sqrt2_sin_complement: pointwise identity cos α - sin α = √2 sin(π/4-α).
-- (2) sum_reindex_complement: the involution n ↦ 45-n permutes Icc 1 44, so sin-sums match.
-- Combine via Finset.sum_sub_distrib + Finset.mul_sum, then linarith to (1+√2)·S_s.
import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs
import Problems.Minif2f.aime_1997_p11.proofs._strategy_s9684

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

def cos_sum_eq_one_plus_sqrt_two_mul_sin_sum := @Problems.Minif2f.aime_1997_p11.s9684

end Problems.Minif2f.aime_1997_p11
