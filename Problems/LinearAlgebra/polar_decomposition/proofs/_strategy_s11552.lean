import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs.L_p_matrix_hermitian

namespace Problems.LinearAlgebra.polar_decomposition

-- `P.IsSymmetric ↔ (P.toMatrix b_E b_E).IsHermitian` for an orthonormal basis
-- (`LinearMap.isHermitian_toMatrix_iff`); rewrite into the concrete matrix world,
-- where the matrix of the diagonal map P : b_E i ↦ σ_i • b_E i is diagonal with real
-- entries σ_i, hence Hermitian — a finite, computational `ext`-check, strictly more
-- concrete than the inner-product symmetry statement.
theorem s11552 {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E) :
  (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).IsSymmetric  := by
  rw [← LinearMap.isHermitian_toMatrix_iff b_E]
  exact p_matrix_hermitian T b_E

end Problems.LinearAlgebra.polar_decomposition
