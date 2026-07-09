import Library.LinearAlgebra.SVD.AdjointSelf
import Library.LinearAlgebra.SVD.BasisConstruction
import Library.LinearAlgebra.SVD.MatrixForm
import Mathlib.Analysis.InnerProductSpace.Adjoint
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.InnerProductSpace.SingularValues
import Mathlib.Analysis.RCLike.Basic
import Mathlib.Data.Matrix.Basic
import Mathlib.LinearAlgebra.FiniteDimensional.Basic
import Mathlib.LinearAlgebra.Matrix.ToLin

/-!
# Singular Value Decomposition

This file assembles the **singular value decomposition (SVD)** of a linear map between
finite-dimensional inner product spaces over an `RCLike` scalar field.

## Main statements

- `svd_complete_from_eigenbasis`: given an orthonormal basis `b_E` of `E` that diagonalises
  `T†T` (with eigenvalues equal to the squares of the singular values of `T`), there exists an
  orthonormal basis `b_F` of `F` such that the matrix of `T` with respect to `b_E` and `b_F`
  is diagonal with the singular values on the diagonal.
- `svd_decomposition`: every linear map `T : E →ₗ[𝕜] F` between finite-dimensional inner product
  spaces admits orthonormal bases `b_E` and `b_F` such that the matrix of `T` is diagonal with
  the singular values of `T` on the diagonal.
-/

open Library.LinearAlgebra.SVD.AdjointSelf
open Library.LinearAlgebra.SVD.BasisConstruction
open Library.LinearAlgebra.SVD.MatrixForm

namespace Library.LinearAlgebra.SVD.Basic

/-- Given an orthonormal basis `b_E` of `E` that diagonalises `T†T` with eigenvalues equal to
the squares of the singular values of `T`, there exists an orthonormal basis `b_F` of `F` such
that the matrix of `T` with respect to `b_E` and `b_F` is diagonal, with `T.singularValues i`
in position $(i, i)$. -/
theorem svd_complete_from_eigenbasis : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_eig : ∀ i, (T.adjoint ∘ₗ T) (b_E i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • b_E i),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0) := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_eig
  have h_inner := inner_t_eigenbasis_sq_diag T b_E _h_eig
  exact exists_orthonormalBasis_toMatrix_diag T b_E h_inner

/-- **Singular value decomposition**: every linear map `T : E →ₗ[𝕜] F` between
finite-dimensional inner product spaces over an `RCLike` field `𝕜` admits orthonormal bases
`b_E` of `E` and `b_F` of `F` such that the matrix of `T` with respect to `b_E` and `b_F` is
diagonal, with the singular value `T.singularValues i` appearing in position $(i, i)$. -/
theorem svd_decomposition : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F),
  ∃ (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
    (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0) := by
  intro 𝕜 _ E F _ _ _ _ _ _ T
  have h_eigbasis := exists_eigenbasis_adjoint_comp_self T
  obtain ⟨b_E, h_eig⟩ := h_eigbasis
  have h_complete := svd_complete_from_eigenbasis T b_E h_eig
  obtain ⟨b_F, h_mat⟩ := h_complete
  exact ⟨b_E, b_F, h_mat⟩

end Library.LinearAlgebra.SVD.Basic
