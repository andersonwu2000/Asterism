-- Inline 3-real pigeonhole on the parameters {0, 1, t_s} (for p, q, s along
-- line pq) against the foot-of-perpendicular parameter t_f, yielding three
-- cases of a same-side pair. In each case dispatch to the abstract single
-- sub-lemma `kelly_smaller_two_same_side`, which encapsulates Kelly's
-- closer-of-two construction + ratio comparison via
-- `perp_numerator_sq_param_factor`. Strictly simpler than the parent: the
-- sub-lemma's pair (a, b) is generic, so the proof handles one symmetric case
-- rather than three intertwined ones.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10214

namespace Problems.sylvester_gallai

def kelly_smaller_with_param := @Problems.sylvester_gallai.s10214

end Problems.sylvester_gallai
