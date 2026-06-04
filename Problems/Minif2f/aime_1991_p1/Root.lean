-- Split parent into 1 Backward sub-goal capturing the Diophantine fact
-- `x + y = 16 ∧ x * y = 55`. Parent closer uses `(x + y)^2 = x^2 + 2*(x*y) + y^2`
-- ring identity, rewrites with the sum / product values, then `omega` to
-- conclude `x^2 + y^2 = 146`. The sub-goal is strictly simpler: it lifts the
-- algebraic substitution `x*y*(x+y) = 880` combined with `s + p = 71` to the
-- closed-form values `s = 16, p = 55`, isolating the Diophantine reasoning.
import Mathlib
import Problems.Minif2f.aime_1991_p1.Defs
import Problems.Minif2f.aime_1991_p1.proofs._strategy_s761

namespace Problems.Minif2f.aime_1991_p1

def main := @Problems.Minif2f.aime_1991_p1.s761

end Problems.Minif2f.aime_1991_p1
