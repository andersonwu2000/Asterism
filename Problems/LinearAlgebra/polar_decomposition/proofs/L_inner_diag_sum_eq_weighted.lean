import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs

namespace Problems.LinearAlgebra.polar_decomposition

-- inner_diag_sum_eq_weighted: inner product of the diagonal-operator image against x equals
-- the weighted sum ∑ σ_i * ‖⟪b_E i, x⟫‖², by sum_inner + inner_smul_left + conj_mul.
-- entry_kind: Builder
theorem inner_diag_sum_eq_weighted {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  (inner 𝕜 (∑ i : Fin (Module.finrank 𝕜 E),
          (inner 𝕜 (b_E i) x : 𝕜) • (((T.singularValues (i : ℕ) : ℝ) : 𝕜) • b_E i)) x : 𝕜)
      = ∑ i : Fin (Module.finrank 𝕜 E),
          ((T.singularValues (i : ℕ) : ℝ) : 𝕜) * ((‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 : ℝ) : 𝕜) := by
  simp_rw [sum_inner, smul_smul, inner_smul_left, map_mul, RCLike.conj_ofReal]
  congr 1; ext i
  have hconj := RCLike.conj_mul (inner 𝕜 (b_E i) x : 𝕜)
  calc (starRingEnd 𝕜) (inner 𝕜 (b_E i) x) * ↑(T.singularValues ↑i) * inner 𝕜 (b_E i) x
      = (starRingEnd 𝕜) (inner 𝕜 (b_E i) x) * inner 𝕜 (b_E i) x * ↑(T.singularValues ↑i) := by
        ring
    _ = ↑(T.singularValues ↑i) * ↑(‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 : ℝ) := by
        rw [hconj]; push_cast; ring

end Problems.LinearAlgebra.polar_decomposition