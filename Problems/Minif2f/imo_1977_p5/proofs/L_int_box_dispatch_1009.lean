-- Reduce ℤ-box dispatch to a square-value dichotomy + two abs-from-square lemmas.
-- sq_dichotomy_1009 carries the bounds and the equation and dispatches on which
-- variable holds the 225-square vs the 784-square (the heavy interval-cases part);
-- abs_eq_15_of_sq_225 and abs_eq_28_of_sq_784 are abstract algebraic facts that
-- recover |z| from z^2 without bounds.
import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs._strategy_s9686

namespace Problems.Minif2f.imo_1977_p5

def int_box_dispatch_1009 := @Problems.Minif2f.imo_1977_p5.s9686

end Problems.Minif2f.imo_1977_p5
