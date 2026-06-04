-- Split the conclusion at the `1/k = k/k²` rewrite (a Builder leaf) before
-- invoking a pure Abel summation inequality against weight `1/k²` (Backward)
-- that consumes the prefix-sum bound. `linarith` closes from the equality + ≤.
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9492

namespace Problems.Minif2f.imo_1978_p5

def abel_inequality_from_prefix_bound := @Problems.Minif2f.imo_1978_p5.s9492

end Problems.Minif2f.imo_1978_p5
