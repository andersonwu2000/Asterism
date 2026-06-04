-- IMO 1979 P1 pairing trick: rewrite alternating sum into 1979 × pair-sum.
-- (1) `alt_eq_tail`: alternating sum = tail sum ∑_{k=660}^{1319} 1/k
-- (2) `tail_eq_pair_sum`: tail sum = 1979 × ∑_{j<330} 1/((660+j)(1319-j))
-- Combine by transitivity.
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9446

namespace Problems.Minif2f.imo_1979_p1

def alt_sum_paired := @Problems.Minif2f.imo_1979_p1.s9446

end Problems.Minif2f.imo_1979_p1
