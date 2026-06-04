-- Decompose `P.IsPositive` for the diagonal operator P : b_E i ↦ σ_i • b_E i.
-- `LinearMap.IsPositive` unfolds to `IsSymmetric P ∧ ∀ x, 0 ≤ re ⟪P x, x⟫`; split into
-- the two independent halves and recombine with the anonymous constructor ⟨·, ·⟩.
-- Both sub-goals are strictly simpler than positivity:
--  • p_symmetric: ⟪P x, y⟫ = ⟪x, P y⟫ — the diagonal entries σ_i are real, so P is
--    self-adjoint; reduces to a basis-coordinate computation.
--  • p_inner_nonneg: 0 ≤ re ⟪P x, x⟫ — expands to ∑ σ_i ‖⟪x, b_E i⟫‖² ≥ 0 using
--    σ_i ≥ 0 (LinearMap.singularValues_nonneg).
import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs._strategy_s11550

namespace Problems.LinearAlgebra.polar_decomposition

def p_is_positive := @Problems.LinearAlgebra.polar_decomposition.s11550

end Problems.LinearAlgebra.polar_decomposition
