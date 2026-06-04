-- Reindex the Finset `s` of distinct monic irreducibles to `Fin s.card` via `s.equivFin`.
-- Witness: n = s.card, p i = ↑(s.equivFin.symm i), e' i = e (p i). Each predicate transfers
-- from membership `(s.equivFin.symm i).property`; injectivity/coprimality use that the
-- composite `val ∘ equivFin.symm` is injective; the product equality is `Equiv.prod_comp`
-- over the attach reindexing of `s`. Pure bookkeeping — closes directly, no sub-goals.
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11556

namespace Problems.LinearAlgebra.primary_decomposition

def fin_of_finset := @Problems.LinearAlgebra.primary_decomposition.s11556

end Problems.LinearAlgebra.primary_decomposition
