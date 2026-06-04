-- Factor f as a finite product over a Finset of distinct monic irreducibles
-- (`finset_factorization`), then reindex that Finset to `Fin n` preserving every
-- predicate (`fin_of_finset`). The Finset version carries all the UFD math; the
-- reindexing is pure bookkeeping via `Finset.equivFin`.
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11554

namespace Problems.LinearAlgebra.primary_decomposition

def exists_finpow_factorization := @Problems.LinearAlgebra.primary_decomposition.s11554

end Problems.LinearAlgebra.primary_decomposition
