-- σ₀ is attained on a unit vector: the top eigenvector of the Gram operator A†A.
-- Sub-goal `top_eigenvector_witness` produces a unit `v` with `A†A v = σ₀² • v`
-- (eigenvector existence, isolated from norms); sub-goal `norm_apply_eq_of_eigenvector`
-- turns that eigen-equation into `‖A v‖ = σ₀` (pure inner-product computation, σ₀ ≥ 0).
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11640

namespace Problems.LinearAlgebra.eckart_young

def exists_unit_vector_norm_eq_singularvalue_zero := @Problems.LinearAlgebra.eckart_young.s11640

end Problems.LinearAlgebra.eckart_young
