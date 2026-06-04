-- Cite Library SVD (specialised at F := E): obtain the orthonormal eigenbasis
-- b_E of T†∘ₗT, the diagonal inner-product relation, and the columns b_F with
-- T (b_E i) = σ_i • b_F i. Take U := b_E.equiv b_F (carrying b_E ↦ b_F) and
-- P := constr sending b_E i ↦ σ_i • b_E i. Three independent sub-goals:
--  • p_is_positive: P is positive (σ_i ≥ 0, diagonal in orthonormal basis);
--  • u_isometry: U preserves norm (it is a LinearIsometryEquiv);
--  • t_factorization: T = U ∘ₗ P (check on the basis b_E via h_col).
import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs._strategy_s11548

namespace Problems.LinearAlgebra.polar_decomposition

def main := @Problems.LinearAlgebra.polar_decomposition.s11548

end Problems.LinearAlgebra.polar_decomposition
