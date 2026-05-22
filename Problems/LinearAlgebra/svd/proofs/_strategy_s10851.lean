import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_eigenbasis_apply_eq_sq_singular_values
import Problems.LinearAlgebra.svd.proofs.L_t_adjoint_t_is_symmetric

namespace Problems.LinearAlgebra.svd

-- Decompose into: (1) T†T is symmetric, and (2) the eigenvector basis of
-- T†T (from IsSymmetric.eigenvectorBasis) has eigenvalues equal to
-- (T.singularValues i)^2 — the spectral-theorem identification step.
-- The combinator threads (1) into IsSymmetric.eigenvectorBasis to produce
-- the witness, then applies (2) for the diagonalisation property.
theorem s10851 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F),
  ∃ (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E),
    ∀ i, (T.adjoint ∘ₗ T) (b_E i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • b_E i  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T
  have h_sym := t_adjoint_t_is_symmetric T
  have h_eig := eigenbasis_apply_eq_sq_singular_values T h_sym
  exact ⟨h_sym.eigenvectorBasis rfl, h_eig⟩

end Problems.LinearAlgebra.svd
