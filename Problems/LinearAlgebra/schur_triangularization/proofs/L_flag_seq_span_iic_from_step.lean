-- Induct on j.val to lift the per-index chain equation `W j.val ⊔ span {v j} = W (j.val+1)`
-- into the running span equality.  Two simpler sub-goals:
--   * `flag_span_iic_zero` — base case j.val = 0: with `W 0 = ⊥` and the chain step at index 0,
--     `span (v '' Set.Iic 0) = span {v 0} = W 1`.
--   * `flag_span_iic_succ` — step case: given `span (v '' Set.Iic ⟨n,_⟩) = W (n+1)`, the chain
--     step at index n+1 promotes it to `span (v '' Set.Iic ⟨n+1,_⟩) = W (n+2)`.
-- Combinator: `Nat.rec` on the underlying ℕ of `j.val`, then apply at `j.val, j.isLt`.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10849

namespace Problems.LinearAlgebra.schur_triangularization

def flag_seq_span_iic_from_step := @Problems.LinearAlgebra.schur_triangularization.s10849

end Problems.LinearAlgebra.schur_triangularization
