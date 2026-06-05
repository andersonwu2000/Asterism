import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_apply_eq_of_eigenvector
import Problems.LinearAlgebra.eckart_young.proofs.L_top_eigenvector_witness

namespace Problems.LinearAlgebra.eckart_young

-- σ₀ is attained on a unit vector: the top eigenvector of the Gram operator A†A.
-- Sub-goal `top_eigenvector_witness` produces a unit `v` with `A†A v = σ₀² • v`
-- (eigenvector existence, isolated from norms); sub-goal `norm_apply_eq_of_eigenvector`
-- turns that eigen-equation into `‖A v‖ = σ₀` (pure inner-product computation, σ₀ ≥ 0).
theorem s11640 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (h : 0 < Module.finrank 𝕜 E) :
    ∃ v : E, ‖v‖ = 1 ∧ ‖A.toContinuousLinearMap v‖ = A.singularValues 0  := by
  obtain ⟨v, hv1, hveig⟩ := top_eigenvector_witness A h
  exact ⟨v, hv1,
    norm_apply_eq_of_eigenvector A v (A.singularValues 0) (A.singularValues_nonneg 0) hv1 hveig⟩

end Problems.LinearAlgebra.eckart_young
