import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_kernel_witness_singularvalue
import Problems.LinearAlgebra.eckart_young.proofs.L_opnorm_ge_of_pointwise_bound

namespace Problems.LinearAlgebra.eckart_young

-- Lower bound: σ_k ≤ ‖T−S‖ for every rank-≤k S. Unfold the lowerBounds set,
-- split on whether k indexes a real singular value.
-- Sub-goal `kernel_witness_singularvalue`: rank-nullity + top-(k+1) right-singular
-- span ∩ ker S yields a nonzero x with S x = 0 and σ_k‖x‖ ≤ ‖T x‖.
-- Sub-goal `opnorm_ge_of_pointwise_bound`: a pointwise lower bound on a unit-direction
-- lifts to the operator norm. Degenerate branch (finrank E ≤ k): σ_k = 0 ≤ ‖·‖.
theorem s11649 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ lowerBounds (setOf fun r : ℝ =>
      ∃ S : E →ₗ[𝕜] F, Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)  := by
  intro r hr
  obtain ⟨S, hrank, rfl⟩ := hr
  by_cases hk : k < Module.finrank 𝕜 E
  · obtain ⟨x, hx, hSx, hbound⟩ := kernel_witness_singularvalue T k S hrank hk
    have key : T.singularValues k * ‖x‖ ≤ ‖(T - S) x‖ := by
      rw [LinearMap.sub_apply, hSx, sub_zero]; exact hbound
    exact opnorm_ge_of_pointwise_bound (T - S) x (T.singularValues k) hx key
  · rw [T.singularValues_of_finrank_le (not_lt.mp hk)]
    exact norm_nonneg _

end Problems.LinearAlgebra.eckart_young
