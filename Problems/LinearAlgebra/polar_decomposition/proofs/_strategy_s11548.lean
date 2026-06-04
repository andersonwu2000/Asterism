import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Library.LinearAlgebra.SVD.AdjointSelf
import Library.LinearAlgebra.SVD.BasisConstruction
import Problems.LinearAlgebra.polar_decomposition.proofs.L_p_is_positive
import Problems.LinearAlgebra.polar_decomposition.proofs.L_t_factorization
import Problems.LinearAlgebra.polar_decomposition.proofs.L_u_isometry

namespace Problems.LinearAlgebra.polar_decomposition

-- Cite Library SVD (specialised at F := E): obtain the orthonormal eigenbasis
-- b_E of T†∘ₗT, the diagonal inner-product relation, and the columns b_F with
-- T (b_E i) = σ_i • b_F i. Take U := b_E.equiv b_F (carrying b_E ↦ b_F) and
-- P := constr sending b_E i ↦ σ_i • b_E i. Three independent sub-goals:
--  • p_is_positive: P is positive (σ_i ≥ 0, diagonal in orthonormal basis);
--  • u_isometry: U preserves norm (it is a LinearIsometryEquiv);
--  • t_factorization: T = U ∘ₗ P (check on the basis b_E via h_col).
theorem s11548 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E),
  ∃ (U P : E →ₗ[𝕜] E),
    P.IsPositive ∧
    (∀ x, ‖U x‖ = ‖x‖) ∧
    T = U ∘ₗ P  := by
  intro 𝕜 _ E _ _ _ T
  obtain ⟨b_E, h_eig⟩ := Library.LinearAlgebra.SVD.AdjointSelf.eigenbasis_t_adjoint_t T
  have h_inner := Library.LinearAlgebra.SVD.BasisConstruction.inner_t_eigenbasis_sq_diag T b_E h_eig
  obtain ⟨b_F, h_col⟩ := Library.LinearAlgebra.SVD.BasisConstruction.b_f_apply_eq_dite T b_E h_inner
  refine ⟨(b_E.equiv b_F (Equiv.refl _)).toLinearMap,
    b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i), ?_, ?_, ?_⟩
  · exact p_is_positive T b_E
  · exact u_isometry b_E b_F
  · exact t_factorization T b_E b_F h_col



end Problems.LinearAlgebra.polar_decomposition
