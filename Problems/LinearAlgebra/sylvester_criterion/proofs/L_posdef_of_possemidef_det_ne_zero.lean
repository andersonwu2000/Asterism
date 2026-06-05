-- A PosSemidef matrix with nonzero determinant is PosDef, via the eigenvalue criterion.
-- PosDef ↔ all eigenvalues > 0; each eigenvalue is ≥ 0 (PosSemidef), and none is 0 since
-- det = ∏ eigenvalues ≠ 0 (a zero eigenvalue would force the product to vanish).
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11601

namespace Problems.LinearAlgebra.sylvester_criterion

def posdef_of_possemidef_det_ne_zero := @Problems.LinearAlgebra.sylvester_criterion.s11601

end Problems.LinearAlgebra.sylvester_criterion
