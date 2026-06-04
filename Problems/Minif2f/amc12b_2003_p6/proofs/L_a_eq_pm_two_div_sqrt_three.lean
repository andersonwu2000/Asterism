-- Decompose: square the system: from `a*r=2`, `a*r^3=6` derive `a^2 = 4/3`;
-- then the disjunction follows from `(2/√3)^2 = 4/3` and `x^2 = y^2 → x = ±y`.
-- a_sq_eq_four_thirds is pure polynomial arithmetic; disj_of_a_sq_eq_four_thirds
-- is the sqrt/√3 algebraic step, both strictly simpler than the parent.
import Mathlib
import Problems.Minif2f.amc12b_2003_p6.Defs
import Problems.Minif2f.amc12b_2003_p6.proofs._strategy_s9363

namespace Problems.Minif2f.amc12b_2003_p6

def a_eq_pm_two_div_sqrt_three := @Problems.Minif2f.amc12b_2003_p6.s9363

end Problems.Minif2f.amc12b_2003_p6
