import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- entry_kind: Builder
-- t_apply_zero_of_singular_zero: if σ_i = 0 then T(b_E i) = 0, via ‖T(b_E i)‖² = σ_i² = 0
theorem t_apply_zero_of_singular_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (i : Fin (Module.finrank 𝕜 E)),
  T.singularValues (i : ℕ) = 0 → T (b_E i) = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner i h_zero
  have hii := h_inner i i
  simp only [↓reduceIte] at hii
  rw [h_zero] at hii
  simp only [ne_eq, OfNat.ofNat_ne_zero, not_false_eq_true, zero_pow, RCLike.ofReal_zero] at hii
  exact inner_self_eq_zero.mp hii

end Problems.LinearAlgebra.svd
