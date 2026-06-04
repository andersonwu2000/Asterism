-- Identity (4:ℝ)^z = √2^(4z) reduces the goal to comparing exponents 4z and 2^z
-- under the increasing function √2^·. Sub-goal 1: the algebraic identity (valid for
-- any z, hz threaded for uniform signatures). Sub-goal 2: the exp-vs-poly bound
-- 4z ≤ 2^z on z > 4. Closer: rewrite by h_eq, then Real.rpow_le_rpow_of_exponent_le
-- using 1 ≤ √2 (discharged inline by nlinarith on (√2)^2 = 2) and h_lin.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9787

namespace Problems.Minif2f.amc12b_2021_p21

def four_pow_le_sqrt2_dbl_exp := @Problems.Minif2f.amc12b_2021_p21.s9787

end Problems.Minif2f.amc12b_2021_p21
