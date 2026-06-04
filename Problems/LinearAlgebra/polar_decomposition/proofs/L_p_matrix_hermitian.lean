import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs

namespace Problems.LinearAlgebra.polar_decomposition

-- entry_kind: Builder
-- p_matrix_hermitian: the matrix of the diagonal operator b_E i ↦ σ_i • b_E i equals
-- Matrix.diagonal with real entries σ_i, which is Hermitian since real scalars are self-adjoint.
theorem p_matrix_hermitian {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E) :
  ((b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).toMatrix
    b_E.toBasis b_E.toBasis).IsHermitian := by
  have hM : (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).toMatrix
      b_E.toBasis b_E.toBasis =
      Matrix.diagonal (fun i : Fin (Module.finrank 𝕜 E) =>
        ((T.singularValues (i : ℕ) : ℝ) : 𝕜)) := by
    ext i j
    simp only [LinearMap.toMatrix_apply, OrthonormalBasis.coe_toBasis, Matrix.diagonal_apply]
    have hcb : ((b_E.toBasis.constr 𝕜) fun i => ((T.singularValues (i : ℕ) : ℝ) : 𝕜) • b_E i)
        (b_E j) = ((T.singularValues (j : ℕ) : ℝ) : 𝕜) • b_E j :=
      b_E.toBasis.constr_basis 𝕜 _ j
    rw [hcb, map_smul]
    rw [show b_E.toBasis.repr (b_E j) = Finsupp.single j 1 from by
      rw [← OrthonormalBasis.coe_toBasis]; exact b_E.toBasis.repr_self j]
    simp only [Finsupp.smul_apply, Finsupp.single_apply, smul_eq_mul, mul_ite,
               mul_one, mul_zero]
    simp only [eq_comm (a := j)]
    split_ifs with h
    · subst h; rfl
    · rfl
  rw [hM]
  apply Matrix.isHermitian_diagonal_iff.mpr
  intro i
  unfold IsSelfAdjoint
  simp [RCLike.star_def, RCLike.conj_ofReal]

end Problems.LinearAlgebra.polar_decomposition

