-- Witness d = ∏ j ∈ range 330, (660+j)*(1319-j) (a product of factors all
-- in [660,1319], hence < 1979 prime ⇒ coprime); witness n is the
-- corresponding common-denominator numerator. Sub-goals:
--  (A) denom_prod_pos: that product is positive.
--  (B) denom_prod_coprime_1979: that product is coprime to 1979.
--  (C) pair_sum_quotient_exists: ∃ n with sum = n / product (cast to ℝ).
-- Combinator: obtain n from (C); package ⟨n, D, A, B, hsum⟩.
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9447

namespace Problems.Minif2f.imo_1979_p1

def pair_sum_repr := @Problems.Minif2f.imo_1979_p1.s9447

end Problems.Minif2f.imo_1979_p1
