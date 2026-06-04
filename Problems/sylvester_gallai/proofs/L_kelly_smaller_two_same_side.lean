-- WLOG on which of {a, b} is closer to the foot of perpendicular (parameter
-- t_f), by case-splitting on the comparison of squared parameter distances
-- to t_f. In each case dispatch to the asymmetric helper
-- `kelly_smaller_two_same_side_ordered`, which assumes `(t_a - t_f)^2 ≤
-- (t_b - t_f)^2` (a is the closer point) and constructs the new triple
-- (b, r, a) whose squared perpendicular distance is strictly less than the
-- original, via `perp_numerator_sq_param_factor` for the numerator factor
-- (t_b - t_a)^2 and the parameter-bound argument for the denominator.
-- Strictly simpler than the parent: the helper handles a single ordered
-- pair rather than an unordered same-side pair.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10215

namespace Problems.sylvester_gallai

def kelly_smaller_two_same_side := @Problems.sylvester_gallai.s10215

end Problems.sylvester_gallai
