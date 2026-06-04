-- Reindex the prime-power direct sum onto the invariant-factor grid in four moves.
-- `reindex_drop_subsingleton` (applied twice) bijects a direct sum onto an injective
--   sub-index, discarding summands outside the image (here the e i = 0 / padded c = 0
--   cells, which are trivial K[X]/(unit) quotients).  `assoc_quot_lequiv` matches each
--   surviving summand via `hassoc`; `directsum_prod_uncurry` flattens the Fin r × Fin s
--   grid.  Each sub-goal is witness-independent and strictly smaller than the bundle.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11578

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def reindex_iso := @Problems.LinearAlgebra.invariant_factor_decomposition.s11578

end Problems.LinearAlgebra.invariant_factor_decomposition
