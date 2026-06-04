-- Reduce `x 4 = 1/|a₁-a₄|` to two simpler facts: x 2 = 0 and x 3 = 0.
-- With these, h₉ becomes |a₁-a₄|·x₄ = 1 (after abs unfolding via a₁>a₄),
-- and division yields the goal.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9428

namespace Problems.Minif2f.imo_1966_p5

def x4_eq_inv := @Problems.Minif2f.imo_1966_p5.s9428

end Problems.Minif2f.imo_1966_p5
