-- 3-way decomposition: extract `z^4 = -1`, extract `z ≠ 0`, then prove product=36 given those two
-- abstract hypotheses. Math: k^2 mod 8 over k=1..12 gives 6×1 + 3×4 + 3×0, so the two sums each
-- collapse to 6z resp. 6/z (using z^4 = -1 ⇒ z^8 = 1), product = 36.
import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs._strategy_s9364

namespace Problems.Minif2f.amc12a_2019_p21

def main := @Problems.Minif2f.amc12a_2019_p21.s9364

end Problems.Minif2f.amc12a_2019_p21
