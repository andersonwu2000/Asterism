-- Decompose `x 2 = 0` into two abs-free linear identities derivable from the four equations.
-- `x1_sum_x234`: from h₉ - h₁₀ (factor out a₁-a₂ > 0) yields x 1 = x 2 + x 3 + x 4.
-- `x1_plus_x2_eq_x3_plus_x4`: from h₁₁ - h₁₀ (factor out a₂-a₃ > 0) yields x 1 + x 2 = x 3 + x 4.
-- Substituting the first into the second gives 2·x 2 = 0; `linarith` closes the goal.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9485

namespace Problems.Minif2f.imo_1966_p5

def hx2_is_zero := @Problems.Minif2f.imo_1966_p5.s9485

end Problems.Minif2f.imo_1966_p5
