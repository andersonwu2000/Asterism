import Library.LinearAlgebra.SVD.BasisConstruction
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.InnerProductSpace.SingularValues
import Mathlib.Analysis.RCLike.Basic
import Mathlib.Data.Finsupp.Basic
import Mathlib.Data.Matrix.Basic
import Mathlib.LinearAlgebra.Basis.Basic
import Mathlib.LinearAlgebra.FiniteDimensional.Basic
import Mathlib.LinearAlgebra.Matrix.ToLin

/-!
# Matrix form of singular value decomposition

This file establishes that any linear map between finite-dimensional inner product spaces over an
`RCLike` field admits an orthonormal basis of the codomain with respect to which its matrix
representation is "diagonal" with singular values on the diagonal.

## Main statements

- `matrix_eq_of_apply_eq`: If an orthonormal input basis maps under `T` to scalar multiples of
  an orthonormal output basis (with the $i$-th singular value as the scalar), then the matrix of
  `T` in those bases is the diagonal-like matrix with singular values.
- `exists_orthonormalBasis_toMatrix_diag`: For any linear map `T` and orthonormal input basis
  satisfying an inner-product condition on singular values, there exists an orthonormal output
  basis making the matrix of `T` diagonal with singular values.
-/

open Library.LinearAlgebra.SVD.BasisConstruction

namespace Library.LinearAlgebra.SVD.MatrixForm

/-- If `T` maps each basis vector `b_E i` to a scalar multiple of `b_F j` (with the $i$-th
singular value as the scalar when `j = i`), then the matrix of `T` with respect to `b_E` and
`b_F` equals the "diagonal" matrix whose `(j, i)` entry is `T.singularValues i` when
`(j : ℕ) = (i : ℕ)` and `0` otherwise. -/
theorem matrix_eq_of_apply_eq : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F)
  (_h_apply : ∀ i, T (b_E i) = ∑ j : Fin (Module.finrank 𝕜 F),
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

/-- **Singular value decomposition (matrix form)**: For any linear map `T : E →ₗ[𝕜] F` and
orthonormal input basis `b_E` satisfying $\langle T(b_E(i)), T(b_E(j))\rangle = \sigma_i^2
\cdot \delta_{ij}$, there exists an orthonormal basis `b_F` of `F` such that the matrix of `T`
in bases `b_E` and `b_F` is diagonal with `T.singularValues i` on the diagonal. -/
theorem exists_orthonormalBasis_toMatrix_diag : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0) := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner
  obtain ⟨b_F, hb_F⟩ := exists_b_f_apply_eq T b_E h_inner
  exact ⟨b_F, matrix_eq_of_apply_eq T b_E b_F hb_F⟩

end Library.LinearAlgebra.SVD.MatrixForm
