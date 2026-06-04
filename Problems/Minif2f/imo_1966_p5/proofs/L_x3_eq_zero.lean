-- Reduce `x 3 = 0` to two linear identities derivable from the equation pairs.
-- `h_sum`: from Eq2 - Eq3 (using a₂ > a₃) yields x 1 + x 2 = x 3 + x 4.
-- `h_x4`: from Eq3 - Eq4 (using a₃ > a₄) yields x 4 = x 1 + x 2 + x 3.
-- Combining both via linarith gives 2·x 3 = 0, hence x 3 = 0.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9374

namespace Problems.Minif2f.imo_1966_p5

def x3_eq_zero := @Problems.Minif2f.imo_1966_p5.s9374

end Problems.Minif2f.imo_1966_p5
