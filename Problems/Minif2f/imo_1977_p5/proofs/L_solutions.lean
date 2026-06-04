-- Reduce to integer sum-of-squares Diophantine: (a-22)^2 + (b-22)^2 = 1009
-- sum_sq_diophantine derives the equation from hypotheses; int_sum_sq_1009 dispatches
-- the abstract Diophantine x^2+y^2=1009 over ℤ into |x|,|y| ∈ {15,28} cases.
import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs._strategy_s9482

namespace Problems.Minif2f.imo_1977_p5

def solutions := @Problems.Minif2f.imo_1977_p5.s9482

end Problems.Minif2f.imo_1977_p5
