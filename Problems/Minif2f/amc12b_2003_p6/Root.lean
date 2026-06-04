-- Decompose: `u 0 = a` (from `h₀ 0`), then `a = ±2/√3` (from system `a*r=2`, `a*r^3=6`).
-- Combine: rewrite `u 0` to `a` and discharge with the disjunction on `a`.
-- u_zero_eq_a is a one-line `simp`/`ring` from `h₀ 0`; a_eq_pm_two_div_sqrt_three carries
-- the system-solve and is the real arithmetic content of the problem.
import Mathlib
import Problems.Minif2f.amc12b_2003_p6.Defs
import Problems.Minif2f.amc12b_2003_p6.proofs._strategy_s9286

namespace Problems.Minif2f.amc12b_2003_p6

def main := @Problems.Minif2f.amc12b_2003_p6.s9286

end Problems.Minif2f.amc12b_2003_p6
