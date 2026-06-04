-- Decompose `x 3 = 0` via two linear identities derivable from the 4 equations.
-- `h_sum_eq`: from Eq2 - Eq3 (using a₂ > a₃) yields x 1 + x 2 = x 3 + x 4.
-- `h_x4_eq`: from Eq3 - Eq4 (using a₃ > a₄) yields x 4 = x 1 + x 2 + x 3.
-- Combining via linarith gives 2·x 3 = 0, hence x 3 = 0.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9486

namespace Problems.Minif2f.imo_1966_p5

def hx3_is_zero := @Problems.Minif2f.imo_1966_p5.s9486

end Problems.Minif2f.imo_1966_p5
