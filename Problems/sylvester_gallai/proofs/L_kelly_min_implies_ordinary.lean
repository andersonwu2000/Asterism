-- By contradiction: if s ∈ P with Collinear p q s, s ≠ p, s ≠ q, then we can produce
-- a strictly closer triple in P³, contradicting the minimality hmin.
-- Sub-goal: given a third collinear P-point off {p,q}, exhibit a strict-smaller-D triple.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10207

namespace Problems.sylvester_gallai

def kelly_min_implies_ordinary := @Problems.sylvester_gallai.s10207

end Problems.sylvester_gallai
