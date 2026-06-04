-- Drop the trivial (out-of-range) summands, then reindex the surviving subtype onto `J`.
-- `drop_subsingleton_subtype` collapses `⨁ I, M` onto the sub-index `{i // i ∈ range f}`
--   (every dropped summand is `Subsingleton`), and `DirectSum.lequivCongrLeft` reindexes
--   that subtype back to `J` via `Equiv.ofInjective f hf`.  The drop lemma is the only real
--   work; the reindex is a direct mathlib citation.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11583

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def reindex_drop_subsingleton := @Problems.LinearAlgebra.invariant_factor_decomposition.s11583

end Problems.LinearAlgebra.invariant_factor_decomposition
