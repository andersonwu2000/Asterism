import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_eckart_young_lower_bound
import Problems.LinearAlgebra.eckart_young.proofs.L_eckart_young_membership

namespace Problems.LinearAlgebra.eckart_young

-- Eckart–Young: split `IsLeast S (σ_k)` into its two defining conjuncts —
-- (A) membership: σ_k is attained by some rank-≤k S, and
-- (B) lower bound: every rank-≤k S has error ≥ σ_k. `⟨_, _⟩` reassembles IsLeast.
theorem s11644 : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ),
    IsLeast
      (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)
      (T.singularValues k)  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T k
  have h_mem := eckart_young_membership T k
  have h_lb := eckart_young_lower_bound T k
  exact ⟨h_mem, h_lb⟩

end Problems.LinearAlgebra.eckart_young
