import Mathlib

namespace Library.LinearAlgebra.SVD.AdjointSelf

-- t_adjoint_t_is_symmetric: T†∘T is symmetric via adjoint_inner_left/right chain
-- entry_kind: Builder
theorem t_adjoint_t_is_symmetric : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F),
  (T.adjoint ∘ₗ T).IsSymmetric := by
  intro 𝕜 _ E F _ _ _ _ _ _ T x y
  simp [LinearMap.comp_apply, LinearMap.adjoint_inner_left, LinearMap.adjoint_inner_right]

-- Direct: apply `IsSymmetric.apply_eigenvectorBasis` (eigenvalue scalar form),
-- then identify the eigenvalue with `(T.singularValues i)^2` via `sq_singularValues_fin`.
theorem eigenbasis_apply_eq_sq_singular_values : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F) (h_sym : (T.adjoint ∘ₗ T).IsSymmetric),
  ∀ i, (T.adjoint ∘ₗ T) (h_sym.eigenvectorBasis rfl i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • h_sym.eigenvectorBasis rfl i  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T h_sym i
  rw [h_sym.apply_eigenvectorBasis rfl i]
  congr 1
  have h := T.sq_singularValues_fin (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
  rw [← h]
  push_cast
  ring

-- Decompose into: (1) T†T is symmetric, and (2) the eigenvector basis of
-- T†T (from IsSymmetric.eigenvectorBasis) has eigenvalues equal to
-- (T.singularValues i)^2 — the spectral-theorem identification step.
-- The combinator threads (1) into IsSymmetric.eigenvectorBasis to produce
-- the witness, then applies (2) for the diagonalisation property.
theorem eigenbasis_t_adjoint_t : ∀ {𝕜 : Type*} [RCLike 𝕜]
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

end Library.LinearAlgebra.SVD.AdjointSelf
