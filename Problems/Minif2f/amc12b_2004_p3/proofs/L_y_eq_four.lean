-- Match 3-adic valuations on both sides of `2^x * 3^y = 1296`.
-- Sub-goal `lhs_three_val`: padicValNat 3 (2^x * 3^y) = y (since 3 ∤ 2).
-- Sub-goal `rhs_three_val`: padicValNat 3 1296 = 4 (decidable arithmetic).
-- Rewriting via h₀ and combining gives y = 4 by omega.
import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs
import Problems.Minif2f.amc12b_2004_p3.proofs._strategy_s9421

namespace Problems.Minif2f.amc12b_2004_p3

def y_eq_four := @Problems.Minif2f.amc12b_2004_p3.s9421

end Problems.Minif2f.amc12b_2004_p3
