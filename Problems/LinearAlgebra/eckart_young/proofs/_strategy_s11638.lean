import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_unit_vector_norm_eq_singularvalue_zero

namespace Problems.LinearAlgebra.eckart_young

-- σ₀ ≤ ‖A‖: the top singular value is attained on a unit vector, so it is a lower bound for ‖A‖.
-- Case split on dim E. If dim E = 0 then σ₀ = 0 ≤ ‖A‖ (norm_nonneg). If dim E > 0, sub-goal
-- `exists_unit_vector_norm_eq_singularvalue_zero` produces a unit v with ‖A v‖ = σ₀; then
-- `le_opNorm` gives σ₀ = ‖A v‖ ≤ ‖A‖·‖v‖ = ‖A‖. The sub-goal isolates the eigenvector existence.
theorem s11638 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) :
    A.singularValues 0 ≤ ‖A.toContinuousLinearMap‖  := by
  by_cases h : 0 < Module.finrank 𝕜 E
  · obtain ⟨v, hv1, hv2⟩ := exists_unit_vector_norm_eq_singularvalue_zero A h
    calc A.singularValues 0 = ‖A.toContinuousLinearMap v‖ := hv2.symm
      _ ≤ ‖A.toContinuousLinearMap‖ * ‖v‖ := A.toContinuousLinearMap.le_opNorm v
      _ = ‖A.toContinuousLinearMap‖ := by rw [hv1, mul_one]
  · rw [A.singularValues_of_finrank_le (by omega)]
    exact norm_nonneg _

end Problems.LinearAlgebra.eckart_young
