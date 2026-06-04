import Library.LinearAlgebra.SVD.BasisConstruction
import Mathlib

open Library.LinearAlgebra.SVD.BasisConstruction

namespace Library.LinearAlgebra.SVD.MatrixForm

-- entry_kind: Builder
-- matrix_eq_of_apply_eq: LinearMap.toMatrix equals Matrix.of when each T(b_E i) expands
-- as the i-th column of the target matrix in b_F. Proved by ext + Basis.repr_self unfolding.
theorem matrix_eq_of_apply_eq : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F)
  (h_apply : ∀ i, T (b_E i) = ∑ j : Fin (Module.finrank 𝕜 F),
    (if (j : ℕ) = (i : ℕ) then ((T.singularValues i : ℝ) : 𝕜) else 0) • b_F j),
  LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
    Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
      if (j : ℕ) = (i : ℕ)
      then ((T.singularValues i : ℝ) : 𝕜)
      else 0) := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E b_F h_apply
  ext j i
  simp only [LinearMap.toMatrix_apply, Matrix.of_apply, OrthonormalBasis.coe_toBasis]
  rw [h_apply i]
  have repr_basis : ∀ k : Fin (Module.finrank 𝕜 F),
      b_F.toBasis.repr (b_F k) = Finsupp.single k 1 := fun k => by
    rw [show b_F k = b_F.toBasis k from
      (congr_fun (OrthonormalBasis.coe_toBasis b_F) k).symm]
    exact b_F.toBasis.repr_self k
  simp only [map_sum, map_smul, repr_basis, Finsupp.coe_finsetSum, Finset.sum_apply,
    Finsupp.smul_apply, Finsupp.single_apply, smul_eq_mul, mul_ite, mul_one, mul_zero,
    Finset.sum_ite_eq', Finset.mem_univ, if_true]

-- Decompose into (A) existence of an orthonormal basis b_F of F such that
-- T(b_E i) expands as the i-th column of the target diagonal matrix in b_F
-- (the orthonormal-extension construction, using h_inner), and (B) a purely
-- mechanical translation from the column-expansion characterisation to the
-- toMatrix equality. (B) is a basis-representation unfolding free of any
-- geometry; (A) absorbs the construction work without needing the matrix
-- machinery, so each sub-goal is strictly simpler than the parent.
theorem exists_b_f_with_matrix_diag : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0)  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner
  obtain ⟨b_F, hb_F⟩ := exists_b_f_apply_eq T b_E h_inner
  exact ⟨b_F, matrix_eq_of_apply_eq T b_E b_F hb_F⟩

end Library.LinearAlgebra.SVD.MatrixForm
