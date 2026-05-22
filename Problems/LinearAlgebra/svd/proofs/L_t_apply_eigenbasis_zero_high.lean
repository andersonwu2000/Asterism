-- Split into (A) `singular_values_zero_high`: a pure singular-value fact —
-- T.singularValues i = 0 once i ≥ finrank F (rank ≤ codim + antitone),
-- independent of b_E / h_inner; and (B) `t_apply_zero_of_singular_zero`:
-- given that σ_i = 0 and the diagonal inner-product identity from h_inner,
-- conclude T (b_E i) = 0 via ‖T (b_E i)‖² = σ_i² = 0.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10857

namespace Problems.LinearAlgebra.svd

def t_apply_eigenbasis_zero_high := @Problems.LinearAlgebra.svd.s10857

end Problems.LinearAlgebra.svd
