-- Decompose `x 2 = 0` into two linear identities derivable from the equation pairs.
-- `h_sum`: from Eq2 - Eq3 (factoring out a₂ - a₃ > 0) yields x 1 + x 2 = x 3 + x 4.
-- `h_x1_sum`: from Eq1 - Eq2 (factoring out a₁ - a₂ > 0) yields x 1 = x 2 + x 3 + x 4.
-- Combining: substituting x 1 in `h_sum` gives 2·x 2 = 0, closed by `linarith`.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9427

namespace Problems.Minif2f.imo_1966_p5

def x2_eq_zero := @Problems.Minif2f.imo_1966_p5.s9427

end Problems.Minif2f.imo_1966_p5
