-- Decompose into (1) inner products ⟨T(b_E i), T(b_E j)⟩ = σ_i² δ_ij
-- (orthogonality + norm computation from h_eig via ⟨T u, T v⟩ = ⟨u, T†T v⟩
-- and orthonormality of b_E), and (2) construction of b_F with the matrix
-- equation given the inner-product diagonal as a black box. Sub-goal 1 is
-- a pure inner-product algebra step; sub-goal 2 is the construction of u_i
-- via scaling by σ_i⁻¹ and orthonormal completion — strictly simpler than
-- the parent since h_eig is no longer needed once h_inner is established.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10852

namespace Problems.LinearAlgebra.svd

def svd_complete_from_eigenbasis := @Problems.LinearAlgebra.svd.s10852

end Problems.LinearAlgebra.svd
