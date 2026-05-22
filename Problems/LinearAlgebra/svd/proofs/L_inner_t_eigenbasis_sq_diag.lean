import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- entry_kind: Builder
-- inner_t_eigenbasis_sq_diag: ⟨T(b_E i), T(b_E j)⟩ = σ_i² δ_ij via adjoint rewrite + orthonormality
theorem inner_t_eigenbasis_sq_diag : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_eig : ∀ i, (T.adjoint ∘ₗ T) (b_E i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • b_E i),
  ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_eig i j
  simp only [LinearMap.comp_apply] at h_eig
  rw [← LinearMap.adjoint_inner_left, h_eig i, inner_smul_left]
  have hconj : starRingEnd 𝕜 (((T.singularValues i : ℝ)^2 : 𝕜)) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) := by
    simp [RCLike.conj_ofReal]
  rw [hconj]
  have horth := orthonormal_iff_ite.mp b_E.orthonormal i j
  split_ifs with h
  · subst h
    simp
  · simp [horth, if_neg h]



end Problems.LinearAlgebra.svd
