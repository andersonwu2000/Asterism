import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- entry_kind: Builder
-- t_b_e_zero_of_sigma_zero: σ_i = 0 → T(b_E i) = 0, via ⟨T v, T v⟩ = σ²=0 and inner_self_eq_zero
set_option linter.unusedVariables false in
theorem t_b_e_zero_of_sigma_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  ∀ (i : Fin (Module.finrank 𝕜 E)),
    (T.singularValues i : ℝ) = 0 → T (b_E i) = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner _h_zero i hi
  apply (inner_self_eq_zero (𝕜 := 𝕜)).mp
  have h := h_inner i i
  simp only [] at h
  rw [h, hi]
  norm_num

end Problems.LinearAlgebra.svd
