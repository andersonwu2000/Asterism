-- Kelly's proof: pick (p,q,r) ∈ P³ with p≠q, ¬Collinear p q r, minimising the
-- squared perpendicular distance from r to line pq; then (p,q) is an ordinary pair.
-- Sub-goal 1: existence of such a minimum (finite-image min over P×P×P).
-- Sub-goal 2: the geometric core — at the minimum, no third P-point lies on line pq.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10205

namespace Problems.sylvester_gallai

def main := @Problems.sylvester_gallai.s10205

end Problems.sylvester_gallai
