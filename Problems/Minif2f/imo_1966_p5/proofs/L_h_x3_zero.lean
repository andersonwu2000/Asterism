-- Reduce `x 3 = 0` to two linear identities derivable from the equation pairs.
-- `h_sum_x12_x34`: from Eq2 - Eq3 (using a₂ > a₃ > 0) yields x 1 + x 2 = x 3 + x 4.
-- `h_x4_eq_sum_123`: from Eq3 - Eq4 (using a₃ > a₄ > 0) yields x 4 = x 1 + x 2 + x 3.
-- Combining both via linarith gives 2·x 3 = 0, hence x 3 = 0.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9643

namespace Problems.Minif2f.imo_1966_p5

def h_x3_zero := @Problems.Minif2f.imo_1966_p5.s9643

end Problems.Minif2f.imo_1966_p5
