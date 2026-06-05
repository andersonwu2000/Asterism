import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- top_eigenvector_witness: uses hasEigenvalue_adjoint_comp_self_sq_singularValues to extract a
-- unit eigenvector of A†A with eigenvalue σ₀²; normalizes the raw eigenvector by ‖v₀‖⁻¹.
theorem top_eigenvector_witness {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (h : 0 < Module.finrank 𝕜 E) :
    ∃ v : E, ‖v‖ = 1 ∧
      (LinearMap.adjoint A ∘ₗ A) v = ((A.singularValues 0 ^ 2 : ℝ) : 𝕜) • v := by
  obtain ⟨v₀, hv₀⟩ :=
    (A.hasEigenvalue_adjoint_comp_self_sq_singularValues h).exists_hasEigenvector
  have hv₀ne : v₀ ≠ 0 := hv₀.2
  have hn : (‖v₀‖ : ℝ) ≠ 0 := norm_ne_zero_iff.mpr hv₀ne
  refine ⟨(‖v₀‖⁻¹ : 𝕜) • v₀, ?_, ?_⟩
  · rw [norm_smul, norm_inv, RCLike.norm_ofReal, abs_of_nonneg (norm_nonneg _),
        inv_mul_cancel₀ hn]
  · have heq := hv₀.apply_eq_smul
    rw [map_smul, heq]
    rw [smul_comm]
    congr 1
    simp [RCLike.ofReal_pow]

end Problems.LinearAlgebra.eckart_young