-- `iSupIndep` of the kernels reduces (via `iSupIndep_def`) to per-`i` disjointness
-- of `ker (aeval T (q i))` from the join of the others. The join is bounded above
-- by `ker (aeval T (∏_{j≠i} q j))` (h_le), and `q i` is coprime to that product
-- (h_cop, from pairwise coprimality); `disjoint_ker_aeval_of_isCoprime` + `mono_right`
-- then close it. Both sub-goals are single-`i` facts, strictly simpler than the n-fold
-- independence.
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11559

namespace Problems.LinearAlgebra.primary_decomposition

def ker_aeval_isupindep_of_pairwise_coprime := @Problems.LinearAlgebra.primary_decomposition.s11559

end Problems.LinearAlgebra.primary_decomposition
