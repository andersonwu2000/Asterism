import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_truncation_pointwise_le_singularvalue

namespace Problems.LinearAlgebra.eckart_young

-- Reduce the operator-norm membership bound to a *pointwise* truncation bound.
-- Sub-goal `exists_truncation_pointwise_le_singularvalue` builds the rank-≤k
-- truncation S with the elementary pointwise estimate ‖(T−S) x‖ ≤ σ_k‖x‖; the
-- operator norm bound then follows by `opNorm_le_bound` (real work, no opNorm/CLM
-- machinery in the sub-goal).
theorem s11648 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    ∃ S : E →ₗ[𝕜] F,
      Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
      ‖LinearMap.toContinuousLinearMap (T - S)‖ ≤ T.singularValues k  := by
  obtain ⟨S, hrank, hpt⟩ := exists_truncation_pointwise_le_singularvalue T k
  refine ⟨S, hrank, ?_⟩
  apply ContinuousLinearMap.opNorm_le_bound _ (T.singularValues_nonneg k)
  intro x
  have hpt' := hpt x
  rwa [LinearMap.coe_toContinuousLinearMap']


end Problems.LinearAlgebra.eckart_young
