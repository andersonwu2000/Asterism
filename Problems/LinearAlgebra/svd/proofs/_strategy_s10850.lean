import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_eigenbasis_t_adjoint_t
import Problems.LinearAlgebra.svd.proofs.L_svd_complete_from_eigenbasis

namespace Problems.LinearAlgebra.svd

-- Decompose SVD into (1) existence of an eigenbasis `b_E` of E diagonalising
-- `T.adjoint ∘ₗ T` with eigenvalues `(T.singularValues i)^2`, and (2) the
-- construction of `b_F` and the diagonal-matrix equation from such a `b_E`.
-- Sub-goal 1 is the spectral-theorem step on the positive self-adjoint
-- operator `T†T`; sub-goal 2 builds `u_i := σ_i⁻¹ • T (b_E i)` for the
-- σ_i > 0 indices, completes to an orthonormal basis of F, then verifies
-- the matrix entries — both strictly simpler than the joint SVD claim.
theorem s10850 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F),
  ∃ (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
    (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0)  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T
  have h_eigbasis := eigenbasis_t_adjoint_t T
  obtain ⟨b_E, h_eig⟩ := h_eigbasis
  have h_complete := svd_complete_from_eigenbasis T b_E h_eig
  obtain ⟨b_F, h_mat⟩ := h_complete
  exact ⟨b_E, b_F, h_mat⟩

end Problems.LinearAlgebra.svd
