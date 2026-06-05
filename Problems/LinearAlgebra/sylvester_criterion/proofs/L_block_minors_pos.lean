-- Each leading block-minor equals a leading minor of M, hence positive.
-- The top-left n×n block B = M.submatrix (castAdd 1) (castAdd 1); its leading
-- (k+1)-minor reindexes to M's leading minor at k.castSucc (val-preserving Fin
-- maps coincide), so `congr 1` after unfolding closes the equality; positivity
-- then follows from hMinors at k.castSucc. No sub-goals needed.
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11608

namespace Problems.LinearAlgebra.sylvester_criterion

def block_minors_pos := @Problems.LinearAlgebra.sylvester_criterion.s11608

end Problems.LinearAlgebra.sylvester_criterion
