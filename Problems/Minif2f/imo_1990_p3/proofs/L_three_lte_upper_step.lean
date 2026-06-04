-- Cube-lift the contrapositive of the LTE-3 step. With a := 2^(3^k*m), reduce
-- 2^(3^(k+1)*m) to a^3 (exp_cube_succ), supply the lower bound 3^(k+1) ∣ a+1 from
-- three_lte_lifting, then apply cube_lte_upper (dual of lifting_three_pow:
-- given 3^(k+1) ∣ a+1 and ¬ 3^(k+2) ∣ a+1, conclude ¬ 3^(k+3) ∣ a^3+1).
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9805

namespace Problems.Minif2f.imo_1990_p3

def three_lte_upper_step := @Problems.Minif2f.imo_1990_p3.s9805

end Problems.Minif2f.imo_1990_p3
