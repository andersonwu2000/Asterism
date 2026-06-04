-- Bound each fraction below by the same numerator over the full sum a+b+c+d.
-- Since dropping one positive term from the denominator strictly increases the
-- fraction, each frac_X_lt sub-goal gives a strict inequality; summing the
-- four and using (a+b+c+d)/(a+b+c+d) = 1 yields 1 < LHS.
import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs
import Problems.Minif2f.imo_1974_p5.proofs._strategy_s9488

namespace Problems.Minif2f.imo_1974_p5

def lower_bound_raw := @Problems.Minif2f.imo_1974_p5.s9488

end Problems.Minif2f.imo_1974_p5
