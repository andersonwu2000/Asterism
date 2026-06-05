import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_kernel_vector_norm_lower
import Problems.LinearAlgebra.eckart_young.proofs.L_opnorm_ge_of_vector_bound

namespace Problems.LinearAlgebra.eckart_young

-- Decompose `σ_k ∈ lowerBounds {‖T-S‖ : rank S ≤ k}` into two pieces.
-- After unfolding to `σ_k ≤ ‖T-S‖`, split on `k < finrank E`:
--  • main case: `exists_kernel_vector_norm_lower` gives `x ≠ 0` with `S x = 0`
--    and `σ_k‖x‖ ≤ ‖T x‖`; on `x`, `(T-S) x = T x`, so `opnorm_ge_of_vector_bound`
--    lifts the pointwise bound to the operator norm.
--  • degenerate case `finrank E ≤ k`: `σ_k = 0 ≤ ‖T-S‖`.
theorem s11646 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ lowerBounds (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)  := by
  intro r hr
  obtain ⟨S, hrank, hr⟩ := hr
  subst hr
  by_cases hk : k < Module.finrank 𝕜 E
  · obtain ⟨x, hx0, hSx, hbound⟩ := exists_kernel_vector_norm_lower T S k hk hrank
    have key : T.singularValues k * ‖x‖ ≤ ‖(T - S) x‖ := by
      rw [LinearMap.sub_apply, hSx, sub_zero]; exact hbound
    exact opnorm_ge_of_vector_bound (T - S) x (T.singularValues k) hx0 key
  · rw [T.singularValues_of_finrank_le (not_lt.mp hk)]
    exact norm_nonneg _

end Problems.LinearAlgebra.eckart_young
