-- Classical IMO 1978 P5: split into a prefix-sum bound from injectivity
-- and an Abel-summation inequality that consumes that bound.
-- (1) `prefix_sum_lower_bound`: `a 1..a m` are `m` distinct positive naturals
--     (since `a` is injective and `a 0 = 0`), so
--     `∑_{k=1..m} a k ≥ ∑_{k=1..m} k`.
-- (2) `abel_inequality_from_prefix_bound`: pure Abel summation against weights
--     `c(k) = 1/k²` (`c k - c (k+1) ≥ 0`), folding the prefix bound into the
--     weighted-sum conclusion. Independent of `a` being injective.
-- Combinator is direct application of (2) to (1).
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9291

namespace Problems.Minif2f.imo_1978_p5

def main := @Problems.Minif2f.imo_1978_p5.s9291

end Problems.Minif2f.imo_1978_p5
