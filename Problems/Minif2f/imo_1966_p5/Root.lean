-- Split the 4-way conjunction `x 2 = 0 ∧ x 3 = 0 ∧ x 1 = 1/|a₁-a₄| ∧ x 4 = 1/|a₁-a₄|`
-- into four independent sub-goals, each re-using all binders (x, a) and all 13 hypotheses.
-- Combinator: `⟨hx2, hx3, hx1, hx4⟩` after `intro`.
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9288

namespace Problems.Minif2f.imo_1966_p5

def main := @Problems.Minif2f.imo_1966_p5.s9288

end Problems.Minif2f.imo_1966_p5
