import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_truncation_norm_le_singularvalue
import Problems.LinearAlgebra.eckart_young.proofs.L_singularvalue_mem_lowerbounds

namespace Problems.LinearAlgebra.eckart_young

-- Membership = the upper-bound construction half. Build a rank-≤k truncation `S`
-- with ‖T−S‖ ≤ σ_k (`exists_truncation_norm_le_singularvalue`); the re-declared
-- lower-bound sub-goal gives σ_k ≤ ‖T−S‖ for that same S (`singularvalue_mem_lowerbounds`,
-- dedupe-aliases the lower-bound sibling), so antisymmetry pins ‖T−S‖ = σ_k.
theorem s11645 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)  := by
  obtain ⟨S, hrank, hle⟩ := exists_truncation_norm_le_singularvalue T k
  refine ⟨S, hrank, ?_⟩
  have hge : T.singularValues k ≤ ‖LinearMap.toContinuousLinearMap (T - S)‖ :=
    singularvalue_mem_lowerbounds T k ⟨S, hrank, rfl⟩
  exact le_antisymm hge hle

end Problems.LinearAlgebra.eckart_young
