-- Decomposition: extract an explicit witness Finset T with card = 48 satisfying the
-- same membership predicate; close the parent by Finset.ext (any S with the predicate
-- equals T) plus rewriting S.card to T.card.
-- Sub-goal `witness_finset_card_48` does the arithmetic (n forced to 2^a · 3^b · 5^3 · 7^d
-- with a ∈ [3,8], b ∈ [1,4], d ∈ [0,1], giving 6·4·1·2 = 48); combinator below is mechanical.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9365

namespace Problems.Minif2f.amc12a_2020_p21

def main := @Problems.Minif2f.amc12a_2020_p21.s9365

end Problems.Minif2f.amc12a_2020_p21
