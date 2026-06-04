-- Internal-direct-sum decomposition V = ⊕ ker(aeval T (q i)) for pairwise
-- coprime qᵢ, reduced via `isInternal_submodule_of_iSupIndep_of_iSup_eq_top`
-- to its two premises:
--   • h_indep : the kernels are `iSupIndep` (n-factor independence built from
--     pairwise coprimality of the qᵢ);
--   • h_sup   : their join equals ker(aeval T (∏ qᵢ)) (n-factor coprime
--     kernel-decomposition), which is ⊤ by `htop`.
-- Both sub-goals are strictly simpler n-factor inductions; the parent is then
-- a pure two-premise assembly via the combinator.
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11555

namespace Problems.LinearAlgebra.primary_decomposition

def is_internal_ker_aeval_of_pairwise_coprime := @Problems.LinearAlgebra.primary_decomposition.s11555

end Problems.LinearAlgebra.primary_decomposition
