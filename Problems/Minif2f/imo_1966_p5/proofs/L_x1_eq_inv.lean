-- Decompose `x 1 = 1/|a₁-a₄|` via x 2 = 0 and x 3 = 0; then read off h₁₂.
-- Sub-goals: `h_x2_zero` (x 2 = 0) and `h_x3_zero` (x 3 = 0); both inherit full parent signature.
-- Combinator: substitute zeros into h₁₂, rewrite |a₄-a₁| = |a₁-a₄| via abs_sub_comm, divide.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9484

namespace Problems.Minif2f.imo_1966_p5

def x1_eq_inv := @Problems.Minif2f.imo_1966_p5.s9484

end Problems.Minif2f.imo_1966_p5
