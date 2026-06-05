-- Reduce the operator-norm membership bound to a *pointwise* truncation bound.
-- Sub-goal `exists_truncation_pointwise_le_singularvalue` builds the rank-≤k
-- truncation S with the elementary pointwise estimate ‖(T−S) x‖ ≤ σ_k‖x‖; the
-- operator norm bound then follows by `opNorm_le_bound` (real work, no opNorm/CLM
-- machinery in the sub-goal).
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11648

namespace Problems.LinearAlgebra.eckart_young

def exists_truncation_norm_le_singularvalue := @Problems.LinearAlgebra.eckart_young.s11648

end Problems.LinearAlgebra.eckart_young
