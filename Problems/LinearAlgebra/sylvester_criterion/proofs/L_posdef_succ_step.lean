-- Schur-complement upgrade, factored into: M PosSemidef, M.det ≠ 0, and the
-- generic upgrade lemma (PosSemidef + det ≠ 0 ⇒ PosDef). The upgrade is
-- re-declared as our own sub-goal (a proven sibling exists but lives in another
-- strategy module and is not auto-imported; Tier-1 dedup aliases this to it).
-- PosSemidef carries the (n×n block PosDef ⇒ Schur ≥ 0) argument; det ≠ 0 is the
-- top leading minor being positive. Both strictly weaker than the parent PosDef goal.
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11604

namespace Problems.LinearAlgebra.sylvester_criterion

def posdef_succ_step := @Problems.LinearAlgebra.sylvester_criterion.s11604

end Problems.LinearAlgebra.sylvester_criterion
