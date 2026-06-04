-- Match 2-adic valuations on both sides of `2^x * 3^y = 1296`.
-- Sub-goal `lhs_two_val`: padicValNat 2 (2^x * 3^y) = x (since 2 ∤ 3).
-- Sub-goal `rhs_two_val`: padicValNat 2 1296 = 4 (decidable arithmetic).
-- Rewriting via h₀ and combining gives x = 4 by omega.
import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs
import Problems.Minif2f.amc12b_2004_p3.proofs._strategy_s9345

namespace Problems.Minif2f.amc12b_2004_p3

def x_eq_four := @Problems.Minif2f.amc12b_2004_p3.s9345

end Problems.Minif2f.amc12b_2004_p3
