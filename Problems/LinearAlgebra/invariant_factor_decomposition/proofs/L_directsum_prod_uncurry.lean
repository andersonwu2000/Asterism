-- Flatten the nested direct sum into a product-indexed one (direct proof, no sub-goals).
-- `sigmaLcurryEquiv.symm` curries `⨁ a ⨁ b N a b` back to the sigma-indexed `⨁ (Σ a, β) N`,
-- then `lequivCongrLeft (Equiv.sigmaEquivProd α β)` reindexes `Σ a:α, β` onto `α × β`;
-- the reindexed family `N (h.symm k).1 (h.symm k).2` is defeq to `N k.1 k.2`.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11582

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def directsum_prod_uncurry := @Problems.LinearAlgebra.invariant_factor_decomposition.s11582

end Problems.LinearAlgebra.invariant_factor_decomposition
