-- Two-step packaging: (1) `saturated_one_step_extension` lifts the rank-constrained
-- one-step extension hypothesis to all T-invariant subspaces (returning U itself
-- when U is full rank), giving `finrank U' = min (finrank U + 1) (finrank V)`.
-- (2) `iterate_extension_to_flag` recursively iterates that saturated extension
-- from ⊥ to build the flag W : ℕ → Submodule K V and verify the four properties.
-- Both sub-goals are pure linear algebra over a Field; the alg-closed input was
-- already consumed by the parent in producing h_ext.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10840

namespace Problems.LinearAlgebra.schur_triangularization

def build_flag_by_iterated_extension := @Problems.LinearAlgebra.schur_triangularization.s10840

end Problems.LinearAlgebra.schur_triangularization
