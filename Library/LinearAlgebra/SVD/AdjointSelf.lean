import Mathlib.Analysis.InnerProductSpace.Adjoint
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.InnerProductSpace.SingularValues
import Mathlib.Analysis.InnerProductSpace.Spectrum
import Mathlib.Analysis.RCLike.Basic

/-!
# Adjoint self-composition and eigenbases for singular value decomposition

This file collects basic facts about the self-adjoint operator `T.adjoint ∘ₗ T` associated
to a linear map `T : E →ₗ[𝕜] F` between finite-dimensional inner-product spaces.

## Main statements

- `adjoint_comp_self_isSymmetric`: `T.adjoint ∘ₗ T` is symmetric.
- `eigenbasis_apply_eq_sq_singular_values`: the eigenvectors of `T.adjoint ∘ₗ T` are scaled
  by the squared singular values.
- `exists_eigenbasis_adjoint_comp_self`: there exists an orthonormal eigenbasis for
  `T.adjoint ∘ₗ T` whose eigenvalues are the squared singular values of `T`.
-/

namespace Library.LinearAlgebra.SVD.AdjointSelf

/-- `T.adjoint ∘ₗ T` is a symmetric linear map for any `T : E →ₗ[𝕜] F`. -/
theorem adjoint_comp_self_isSymmetric : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F),
    (T.adjoint ∘ₗ T).IsSymmetric := fun T => LinearMap.isSymmetric_adjoint_comp_self T

/-- Each eigenvector of `T.adjoint ∘ₗ T` (from the eigenvector basis of `h_sym`) is scaled by
`((T.singularValues i : ℝ) ^ 2 : 𝕜)`, the $i$-th squared singular value of `T`. -/
theorem eigenbasis_apply_eq_sq_singular_values : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (h_sym : (T.adjoint ∘ₗ T).IsSymmetric),
    ∀ i, (T.adjoint ∘ₗ T) (h_sym.eigenvectorBasis rfl i) =
        (((T.singularValues i : ℝ) ^ 2 : 𝕜)) • h_sym.eigenvectorBasis rfl i := by
  intro 𝕜 _ E F _ _ _ _ _ _ T h_sym i
  rw [h_sym.apply_eigenvectorBasis rfl i]
  congr 1
  have h := T.sq_singularValues_fin (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
  rw [← h]
  push_cast
  ring

/-- **Existence of an orthonormal eigenbasis for `T.adjoint ∘ₗ T`**: for any linear map
`T : E →ₗ[𝕜] F` between finite-dimensional inner-product spaces, there exists an orthonormal
basis `b_E` of `E` such that `T.adjoint ∘ₗ T` acts on each `b_E i` by scaling by
`((T.singularValues i : ℝ) ^ 2 : 𝕜)`. This is the spectral theorem applied to the symmetric
operator `T.adjoint ∘ₗ T`. -/
theorem exists_eigenbasis_adjoint_comp_self : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F),
    ∃ (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E),
      ∀ i, (T.adjoint ∘ₗ T) (b_E i) =
        (((T.singularValues i : ℝ) ^ 2 : 𝕜)) • b_E i := by
  intro 𝕜 _ E F _ _ _ _ _ _ T
  have h_sym := adjoint_comp_self_isSymmetric T
  have h_eig := eigenbasis_apply_eq_sq_singular_values T h_sym
  exact ⟨h_sym.eigenvectorBasis rfl, h_eig⟩

end Library.LinearAlgebra.SVD.AdjointSelf
